from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# Final X2D patch applied after RC1 + RC2 + audit hardening.
lib_path = Path("src-tauri/src/lib.rs")
s = lib_path.read_text()

# Audit cleanup: after delegating AMS temperatures to firmware, curr_tray is unused.
s = s.replace("        let curr_tray = status.tray_now;\n", "")

# Track object IDs that the printer confirms as skipped via print.s_obj.
s = replace_once(
    s,
    '''    pub camera_rtsp_enabled: bool,\n    pub bed_temp: f64,''',
    '''    pub camera_rtsp_enabled: bool,\n    pub skipped_objects: Vec<u32>,\n    pub bed_temp: f64,''',
    "Rust skipped_objects field",
)

s = replace_once(
    s,
    '''    f64_field!(status.bed_temp, "bed_temper");''',
    '''    if let Some(skipped) = p.get("s_obj").and_then(|v| v.as_array()) {\n        status.skipped_objects = skipped\n            .iter()\n            .filter_map(|v| {\n                v.as_u64()\n                    .or_else(|| v.as_str().and_then(|s| s.parse().ok()))\n                    .and_then(|n| u32::try_from(n).ok())\n            })\n            .collect();\n    }\n\n    f64_field!(status.bed_temp, "bed_temper");''',
    "parse s_obj",
)

# Pure payload helper makes the wire format regression-testable.
command_block = r'''
fn build_skip_objects_payload(object_ids: &[u32], timestamp: u64) -> serde_json::Value {
    serde_json::json!({
        "print": {
            "sequence_id": "0",
            "command": "skip_objects",
            "timestamp": timestamp,
            "obj_list": object_ids,
        }
    })
}

#[tauri::command]
async fn skip_objects(
    object_ids: Vec<u32>,
    state: TauriState<'_, AppState>,
) -> Result<(), String> {
    if object_ids.is_empty() {
        return Err("Select at least one object to skip".to_string());
    }

    let mut ids = object_ids;
    ids.sort_unstable();
    ids.dedup();
    if ids.len() > 100 {
        return Err("Too many object IDs".to_string());
    }

    let (mqtt_client, topic, status_arc) = {
        let conn = state.connection.lock().await;
        let c = conn.as_ref().ok_or("Not connected")?;
        (
            c.mqtt_client.clone(),
            format!("device/{}/request", c.serial),
            c.status.clone(),
        )
    };

    {
        let st = status_arc.lock().await;
        if st.gcode_state != "RUNNING" && st.gcode_state != "PAUSE" {
            return Err("Skip Object is only available during an active print".to_string());
        }
        if ids.iter().all(|id| st.skipped_objects.contains(id)) {
            return Err("Selected object is already skipped".to_string());
        }
    }

    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_secs();
    let payload = build_skip_objects_payload(&ids, timestamp);

    mqtt_client
        .publish(&topic, QoS::AtLeastOnce, false, payload.to_string())
        .await
        .map_err(|e| e.to_string())
}

'''
s = replace_once(
    s,
    "// ── FTPS file manager (implicit TLS, port 990) ───────────────────────────────",
    command_block + "// ── FTPS file manager (implicit TLS, port 990) ───────────────────────────────",
    "skip command insertion",
)

s = replace_once(
    s,
    "            printer_command,\n",
    "            printer_command,\n            skip_objects,\n",
    "invoke handler skip_objects",
)

# Regression tests for parser acknowledgement and exact MQTT command shape.
s += r'''

#[cfg(test)]
mod x2d_skip_object_tests {
    use super::*;

    #[test]
    fn parses_skipped_object_acknowledgement() {
        let payload = br#"{"print":{"command":"push_status","s_obj":[206,"311"]}}"#;
        let mut st = PrinterStatus::default();
        assert!(parse_status(payload, &mut st));
        assert_eq!(st.skipped_objects, vec![206, 311]);
    }

    #[test]
    fn builds_skip_objects_wire_payload() {
        let payload = build_skip_objects_payload(&[206, 311], 1_700_000_000);
        assert_eq!(payload["print"]["command"], "skip_objects");
        assert_eq!(payload["print"]["sequence_id"], "0");
        assert_eq!(payload["print"]["timestamp"], 1_700_000_000u64);
        assert_eq!(payload["print"]["obj_list"], serde_json::json!([206, 311]));
    }
}
'''
lib_path.write_text(s)

# TypeScript status model.
vite = Path("src/vite-env.d.ts")
v = vite.read_text()
v = replace_once(
    v,
    '''  camera_rtsp_enabled: boolean;\n  bed_temp: number;''',
    '''  camera_rtsp_enabled: boolean;\n  skipped_objects: number[];\n  bed_temp: number;''',
    "TypeScript skipped_objects field",
)
vite.write_text(v)

# Dashboard command bridge.
dash_path = Path("src/pages/Dashboard.tsx")
d = dash_path.read_text()
d = replace_once(
    d,
    '''  async function sendGcode(gcode: string) {\n    await invoke('send_gcode', { gcode }).catch(console.error);\n  }''',
    '''  async function sendGcode(gcode: string) {\n    await invoke('send_gcode', { gcode }).catch(console.error);\n  }\n\n  async function skipObject(objectId: number) {\n    await invoke('skip_objects', { objectIds: [objectId] });\n  }''',
    "Dashboard skip function",
)
d = replace_once(
    d,
    '''              onCommand={sendCommand}\n              lightOn={lightOn}''',
    '''              onCommand={sendCommand}\n              onSkipObject={skipObject}\n              lightOn={lightOn}''',
    "Dashboard skip prop",
)
dash_path.write_text(d)

# Print card UI. Until slice_info object-name extraction is added, this accepts the
# slicer's object identify_id and still tracks printer-confirmed skipped IDs.
card_path = Path("src/components/PrintStatusCard.tsx")
pc = card_path.read_text()
pc = replace_once(
    pc,
    '''  onCommand,\n  lightOn,''',
    '''  onCommand,\n  onSkipObject,\n  lightOn,''',
    "PrintStatusCard skip prop destructure",
)
pc = replace_once(
    pc,
    '''  onCommand: (cmd: string) => void;\n  lightOn: boolean;''',
    '''  onCommand: (cmd: string) => void;\n  onSkipObject: (objectId: number) => Promise<void>;\n  lightOn: boolean;''',
    "PrintStatusCard skip prop type",
)

skip_ui = r'''      {isActive && (
        <div className='flex flex-col gap-2 border-t border-zinc-700 pt-3'>
          <button
            onClick={async () => {
              const raw = window.prompt('Object ID to skip (from the slicer object list):');
              if (raw === null) return;
              const objectId = Number(raw.trim());
              if (!Number.isInteger(objectId) || objectId < 0) {
                window.alert('Enter a valid numeric object ID.');
                return;
              }
              if ((status.skipped_objects ?? []).includes(objectId)) {
                window.alert(`Object ${objectId} is already skipped.`);
                return;
              }
              if (!window.confirm(`Skip object ${objectId}? The X2D will finish the current layer before the skip takes effect.`)) {
                return;
              }
              try {
                await onSkipObject(objectId);
                window.alert('Skip queued. It will take effect after the current layer.');
              } catch (e) {
                window.alert(`Could not queue skip: ${String(e)}`);
              }
            }}
            className='w-full rounded-lg bg-amber-600/20 border border-amber-500/50 px-3 py-2 text-amber-300 font-semibold'>
            Skip Failed Object
          </button>
          {(status.skipped_objects ?? []).length > 0 && (
            <span className='text-xs text-zinc-400'>
              Skipped objects: {status.skipped_objects.join(', ')}
            </span>
          )}
        </div>
      )}
'''
pc = replace_once(
    pc,
    "      <div className='grid grid-cols-[1fr_2px_1fr_2px_1fr] gap-2 pt-4 text-zinc-400 tracking-wide font-semibold'>",
    skip_ui + "      <div className='grid grid-cols-[1fr_2px_1fr_2px_1fr] gap-2 pt-4 text-zinc-400 tracking-wide font-semibold'>",
    "Skip Object UI",
)
card_path.write_text(pc)

print("Final X2D camera + dual-nozzle + skip-object patch applied")
