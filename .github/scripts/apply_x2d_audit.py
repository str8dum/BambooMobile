from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one anchor, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Rust backend: X2D-aware status, dual nozzle, skip-object command, camera gate
# ---------------------------------------------------------------------------

replace_once(
    "src-tauri/src/lib.rs",
    "#[derive(Debug, Clone, Serialize, Default)]\npub struct PrinterStatus {\n    pub nozzle_temp: f64,\n    pub nozzle_target: f64,",
    "#[derive(Debug, Clone, Serialize, Default)]\npub struct NozzleStatus {\n    pub id: u8,\n    pub current_temp: f64,\n    pub target_temp: f64,\n}\n\n#[derive(Debug, Clone, Serialize, Default)]\npub struct PrinterStatus {\n    pub nozzle_temp: f64,\n    pub nozzle_target: f64,\n    /// Per-tool temperature state. X2D/H2-class printers report two entries.\n    pub nozzles: Vec<NozzleStatus>,\n    pub active_nozzle: u8,\n    pub chamber_temp: f64,\n    pub chamber_target: f64,"
)

replace_once(
    "src-tauri/src/lib.rs",
    "    pub device_name: String,\n    /// Global slot ID of the tray currently loaded in the nozzle.",
    "    pub device_name: String,\n    /// Object instance IDs already skipped by the running print (print.s_obj).\n    pub skipped_objects: Vec<u32>,\n    /// Global slot ID of the tray currently loaded in the nozzle."
)

replace_once(
    "src-tauri/src/lib.rs",
    "    f64_field!(status.nozzle_temp, \"nozzle_temper\");\n    f64_field!(status.nozzle_target, \"nozzle_target_temper\");\n    f64_field!(status.bed_temp, \"bed_temper\");\n    f64_field!(status.bed_target, \"bed_target_temper\");",
    "    f64_field!(status.nozzle_temp, \"nozzle_temper\");\n    f64_field!(status.nozzle_target, \"nozzle_target_temper\");\n    f64_field!(status.bed_temp, \"bed_temper\");\n    f64_field!(status.bed_target, \"bed_target_temper\");\n    f64_field!(status.chamber_temp, \"chamber_temper\");\n    f64_field!(status.chamber_target, \"ctt\");\n\n    // X2D/H2-family printers expose the two hotends in device.extruder.info[].\n    // The temp field is normally packed as (target << 16) | current. Older or\n    // transitional firmware can also expose nozzle_temper_2 / *_target_*_2, so\n    // keep both paths and preserve the previous value across partial deltas.\n    let number = |value: Option<&serde_json::Value>| -> Option<f64> {\n        value.and_then(|v| {\n            v.as_f64()\n                .or_else(|| v.as_i64().map(|n| n as f64))\n                .or_else(|| v.as_u64().map(|n| n as f64))\n                .or_else(|| v.as_str().and_then(|s| s.parse::<f64>().ok()))\n        })\n    };\n    let prev0 = status\n        .nozzles\n        .iter()\n        .find(|n| n.id == 0)\n        .cloned()\n        .unwrap_or_else(|| NozzleStatus {\n            id: 0,\n            current_temp: status.nozzle_temp,\n            target_temp: status.nozzle_target,\n        });\n    let prev1 = status\n        .nozzles\n        .iter()\n        .find(|n| n.id == 1)\n        .cloned()\n        .unwrap_or_else(|| NozzleStatus { id: 1, ..Default::default() });\n\n    let mut n0_current = number(p.get(\"nozzle_temper\")).unwrap_or(prev0.current_temp);\n    let mut n0_target = number(p.get(\"nozzle_target_temper\")).unwrap_or(prev0.target_temp);\n    let mut n1_current = number(p.get(\"nozzle_temper_2\")).unwrap_or(prev1.current_temp);\n    let mut n1_target = number(p.get(\"nozzle_target_temper_2\")).unwrap_or(prev1.target_temp);\n    let mut has_second_nozzle = p.get(\"nozzle_temper_2\").is_some()\n        || p.get(\"nozzle_target_temper_2\").is_some()\n        || status.nozzles.iter().any(|n| n.id == 1);\n\n    if let Some(info) = p\n        .get(\"device\")\n        .and_then(|v| v.get(\"extruder\"))\n        .and_then(|v| v.get(\"info\"))\n        .and_then(|v| v.as_array())\n    {\n        for (index, entry) in info.iter().enumerate() {\n            let id = entry\n                .get(\"id\")\n                .and_then(|v| {\n                    v.as_u64()\n                        .or_else(|| v.as_str().and_then(|s| s.parse::<u64>().ok()))\n                })\n                .unwrap_or(index as u64) as u8;\n            if id > 1 {\n                continue;\n            }\n\n            let (mut current, mut target) = if id == 0 {\n                (n0_current, n0_target)\n            } else {\n                (n1_current, n1_target)\n            };\n            if let Some(v) = number(entry.get(\"current_temp\")) {\n                current = v;\n            }\n            if let Some(v) = number(entry.get(\"target_temp\")) {\n                target = v;\n            }\n            if let Some(raw) = number(entry.get(\"temp\")) {\n                if raw > 500.0 {\n                    let packed = raw.round() as u64;\n                    current = (packed & 0xffff) as f64;\n                    target = ((packed >> 16) & 0xffff) as f64;\n                } else {\n                    current = raw;\n                }\n            }\n\n            if id == 0 {\n                n0_current = current;\n                n0_target = target;\n            } else {\n                n1_current = current;\n                n1_target = target;\n                has_second_nozzle = true;\n            }\n        }\n    }\n\n    status.nozzle_temp = n0_current;\n    status.nozzle_target = n0_target;\n    status.nozzles = vec![NozzleStatus {\n        id: 0,\n        current_temp: n0_current,\n        target_temp: n0_target,\n    }];\n    if has_second_nozzle {\n        status.nozzles.push(NozzleStatus {\n            id: 1,\n            current_temp: n1_current,\n            target_temp: n1_target,\n        });\n    }\n\n    // Newer machines can pack chamber current/target into device.ctc.info.temp.\n    if let Some(raw) = p\n        .get(\"device\")\n        .and_then(|v| v.get(\"ctc\"))\n        .and_then(|v| v.get(\"info\"))\n        .and_then(|v| number(v.get(\"temp\")))\n    {\n        let packed = raw.round() as u64;\n        if packed > 0xffff {\n            status.chamber_temp = (packed & 0xffff) as f64;\n            status.chamber_target = ((packed >> 16) & 0xffff) as f64;\n        } else {\n            status.chamber_temp = raw;\n        }\n    }"
)

replace_once(
    "src-tauri/src/lib.rs",
    "    u64_field!(status.spd_lvl, \"spd_lvl\");\n    str_field!(status.gcode_state, \"gcode_state\");",
    "    u64_field!(status.spd_lvl, \"spd_lvl\");\n    u64_field!(status.active_nozzle, \"active_tool\");\n    str_field!(status.gcode_state, \"gcode_state\");\n    // X2D/newer firmware may publish print_status instead of gcode_state.\n    if let Some(s) = p.get(\"print_status\").and_then(|v| v.as_str()) {\n        if !s.is_empty() {\n            status.gcode_state = s.to_owned();\n        }\n    }"
)

replace_once(
    "src-tauri/src/lib.rs",
    "    if let Some(n) = p.get(\"stg_cur\").and_then(|v| v.as_u64()) {\n        status.stage = stage_name(n);\n    }",
    "    if let Some(n) = p\n        .get(\"stg_cur\")\n        .or_else(|| p.get(\"stage_curr\"))\n        .and_then(|v| v.as_u64().or_else(|| v.as_str().and_then(|s| s.parse().ok())))\n    {\n        status.stage = stage_name(n);\n    }\n\n    if let Some(objects) = p.get(\"s_obj\").and_then(|v| v.as_array()) {\n        status.skipped_objects = objects\n            .iter()\n            .filter_map(|v| {\n                v.as_u64()\n                    .or_else(|| v.as_str().and_then(|s| s.parse::<u64>().ok()))\n                    .map(|n| n as u32)\n            })\n            .collect();\n    }"
)

replace_once(
    "src-tauri/src/lib.rs",
    "    // Camera: MJPG over TLS on port 6000\n    let camera_handle = tokio::spawn(camera_loop(ip.clone(), access_code.clone(), app.clone()));\n    abort_handles.push(camera_handle.abort_handle());\n    drop(camera_handle);",
    "    // Legacy A/P-family camera: MJPEG over TLS on port 6000. X2D uses\n    // RTSPS/H.264 on port 322 and is rendered by the native Android camera\n    // activity instead, so do not keep a dead 6000 retry loop running there.\n    if !serial.to_ascii_uppercase().starts_with(\"20P\") {\n        let camera_handle = tokio::spawn(camera_loop(ip.clone(), access_code.clone(), app.clone()));\n        abort_handles.push(camera_handle.abort_handle());\n        drop(camera_handle);\n    }"
)

replace_once(
    "src-tauri/src/lib.rs",
    "#[tauri::command]\nasync fn printer_command(command: String, state: TauriState<'_, AppState>) -> Result<(), String> {",
    "#[tauri::command]\nasync fn set_nozzle_temperature(\n    nozzle_id: u8,\n    temp: u16,\n    state: TauriState<'_, AppState>,\n) -> Result<(), String> {\n    if nozzle_id > 1 {\n        return Err(\"Nozzle ID must be 0 or 1\".into());\n    }\n    if temp > 350 {\n        return Err(\"Nozzle temperature must be 350 C or lower\".into());\n    }\n    let conn = state.connection.lock().await;\n    let c = conn.as_ref().ok_or(\"Not connected\")?;\n    let topic = format!(\"device/{}/request\", c.serial);\n    // Bambu dual-tool G-code uses T0/T1 to address the individual hotend.\n    let payload = serde_json::json!({\n        \"print\": {\n            \"sequence_id\": \"0\",\n            \"command\": \"gcode_line\",\n            \"param\": format!(\"M104 T{} S{}\\n\", nozzle_id, temp)\n        }\n    });\n    c.mqtt_client\n        .publish(&topic, QoS::AtLeastOnce, false, payload.to_string())\n        .await\n        .map_err(|e| e.to_string())\n}\n\n#[tauri::command]\nasync fn skip_objects(\n    object_ids: Vec<u32>,\n    state: TauriState<'_, AppState>,\n) -> Result<(), String> {\n    let (mqtt_client, topic, payload) = {\n        let conn = state.connection.lock().await;\n        let c = conn.as_ref().ok_or(\"Not connected\")?;\n        let status = c.status.lock().await;\n        if status.gcode_state != \"RUNNING\" {\n            return Err(\"Skip Object is only available while printing\".into());\n        }\n        if status.layer_num < 2 {\n            return Err(\"Skip Object becomes available at layer 2\".into());\n        }\n\n        // skip_objects is cumulative: include IDs already echoed by print.s_obj.\n        let mut ids = status.skipped_objects.clone();\n        ids.extend(object_ids.into_iter().filter(|id| *id > 0));\n        ids.sort_unstable();\n        ids.dedup();\n        if ids.is_empty() {\n            return Err(\"Enter at least one valid object ID\".into());\n        }\n\n        let topic = format!(\"device/{}/request\", c.serial);\n        let payload = serde_json::json!({\n            \"print\": {\n                \"sequence_id\": \"0\",\n                \"command\": \"skip_objects\",\n                \"obj_list\": ids\n            }\n        });\n        (c.mqtt_client.clone(), topic, payload)\n    };\n\n    mqtt_client\n        .publish(&topic, QoS::AtLeastOnce, false, payload.to_string())\n        .await\n        .map_err(|e| e.to_string())\n}\n\n#[tauri::command]\nasync fn printer_command(command: String, state: TauriState<'_, AppState>) -> Result<(), String> {"
)

replace_once(
    "src-tauri/src/lib.rs",
    "    #[cfg(mobile)]\n    let builder = builder.plugin(\n        tauri::plugin::Builder::<tauri::Wry, ()>::new(\"printNotification\")",
    "    #[cfg(mobile)]\n    let builder = builder.plugin(\n        tauri::plugin::Builder::<tauri::Wry, ()>::new(\"printNotification\")"
)

# Insert a second Android plugin immediately before the common plugin chain.
replace_once(
    "src-tauri/src/lib.rs",
    "    builder\n        .plugin(tauri_plugin_deep_link::init())",
    "    // Native RTSPS/H.264 camera bridge for X2D-class printers.\n    #[cfg(mobile)]\n    let builder = builder.plugin(\n        tauri::plugin::Builder::<tauri::Wry, ()>::new(\"camera\")\n            .setup(|_app, api| {\n                if let Err(e) = api.register_android_plugin(\n                    \"com.joelsgc.bamboomobile\",\n                    \"CameraPlugin\",\n                ) {\n                    eprintln!(\"[Camera] register_android_plugin failed: {:?}\", e);\n                }\n                Ok(())\n            })\n            .build(),\n    );\n\n    builder\n        .plugin(tauri_plugin_deep_link::init())"
)

replace_once(
    "src-tauri/src/lib.rs",
    "            set_print_speed,\n            send_gcode,",
    "            set_print_speed,\n            set_nozzle_temperature,\n            skip_objects,\n            send_gcode,"
)

# ---------------------------------------------------------------------------
# Shared TS types
# ---------------------------------------------------------------------------

replace_once(
    "src/vite-env.d.ts",
    "export interface PrinterStatus {\n  nozzle_temp: number;\n  nozzle_target: number;",
    "export interface NozzleStatus {\n  id: number;\n  current_temp: number;\n  target_temp: number;\n}\n\nexport interface PrinterStatus {\n  nozzle_temp: number;\n  nozzle_target: number;\n  nozzles: NozzleStatus[];\n  active_nozzle: number;\n  chamber_temp: number;\n  chamber_target: number;"
)

replace_once(
    "src/vite-env.d.ts",
    "  device_name: string;\n  /** Global slot ID",
    "  device_name: string;\n  skipped_objects: number[];\n  /** Global slot ID"
)

# ---------------------------------------------------------------------------
# Temp gauge labels (needed to distinguish X2D nozzles)
# ---------------------------------------------------------------------------

replace_once(
    "src/components/TempGauge.tsx",
    "  icon,\n  actual,",
    "  icon,\n  label,\n  actual,"
)
replace_once(
    "src/components/TempGauge.tsx",
    "  icon: React.ReactNode;\n  actual: number;",
    "  icon: React.ReactNode;\n  label?: string;\n  actual: number;"
)
replace_once(
    "src/components/TempGauge.tsx",
    "        <div className='text-center'>\n          <span className='text-white text-xl font-bold tabular-nums'>",
    "        <div className='text-center'>\n          {label && <p className='text-zinc-400 text-xs mb-1'>{label}</p>}\n          <span className='text-white text-xl font-bold tabular-nums'>"
)

# ---------------------------------------------------------------------------
# Skip Object UI
# ---------------------------------------------------------------------------

write(
    "src/components/SkipObjectModal.tsx",
    """import { useMemo, useState } from 'react';

export default function SkipObjectModal({
  skipped,
  layer,
  onSubmit,
  onClose,
}: {
  skipped: number[];
  layer: number;
  onSubmit: (ids: number[]) => Promise<void>;
  onClose: () => void;
}) {
  const [raw, setRaw] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const ids = useMemo(
    () => Array.from(new Set(raw.split(/[\\s,]+/).map((v) => Number(v)).filter((v) => Number.isInteger(v) && v > 0))),
    [raw],
  );

  async function submit() {
    if (ids.length === 0) {
      setError('Enter one or more object IDs.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await onSubmit(ids);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4' onClick={onClose}>
      <div className='w-full max-w-sm rounded-2xl border border-zinc-700 bg-zinc-850 bg-zinc-900 p-5 shadow-2xl' onClick={(e) => e.stopPropagation()}>
        <h2 className='text-lg font-semibold text-white'>Skip Object</h2>
        <p className='mt-1 text-xs text-zinc-400'>
          Sends Bambu's native <span className='font-mono'>skip_objects</span> command. It is available from layer 2 onward.
        </p>

        {skipped.length > 0 && (
          <p className='mt-3 text-xs text-amber-300'>Already skipped: {skipped.join(', ')}</p>
        )}

        <label className='mt-4 flex flex-col gap-1'>
          <span className='text-xs uppercase tracking-wider text-zinc-500'>Object ID(s)</span>
          <input
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            placeholder='e.g. 2 or 2, 4'
            inputMode='numeric'
            className='rounded-lg bg-zinc-800 px-4 py-3 font-mono text-white outline-none focus:ring-2 focus:ring-teal-500'
            autoFocus
          />
        </label>

        <p className='mt-2 text-xs text-zinc-500'>Current layer: {layer}. Invalid IDs are rejected by the printer.</p>
        {error && <p className='mt-3 text-sm text-red-400'>{error}</p>}

        <div className='mt-5 flex gap-2'>
          <button onClick={onClose} disabled={busy} className='flex-1 rounded-xl bg-zinc-800 py-2.5 text-sm font-medium text-zinc-300'>Cancel</button>
          <button onClick={submit} disabled={busy || layer < 2} className='flex-1 rounded-xl bg-amber-700 py-2.5 text-sm font-semibold text-white disabled:opacity-40'>
            {busy ? 'Sending…' : 'Skip selected'}
          </button>
        </div>
      </div>
    </div>
  );
}
"""
)

replace_once(
    "src/components/PrintStatusCard.tsx",
    "  lightOn,\n  toggleLight,\n}: {",
    "  lightOn,\n  toggleLight,\n  onSkipObject,\n}: {"
)
replace_once(
    "src/components/PrintStatusCard.tsx",
    "  lightOn: boolean;\n  toggleLight: () => void;\n}) {",
    "  lightOn: boolean;\n  toggleLight: () => void;\n  onSkipObject: () => void;\n}) {"
)
replace_once(
    "src/components/PrintStatusCard.tsx",
    "      </div>\n    </div>\n  );\n}",
    "      </div>\n\n      {isActive && (\n        <button\n          onClick={onSkipObject}\n          disabled={status.layer_num < 2}\n          className='w-full rounded-xl border border-amber-700/70 bg-amber-950/40 py-2.5 text-sm font-semibold text-amber-300 transition-colors hover:bg-amber-900/50 disabled:cursor-not-allowed disabled:opacity-40'>\n          Skip Object{(status.skipped_objects?.length ?? 0) > 0 ? ` · ${status.skipped_objects.length} skipped` : ''}\n        </button>\n      )}\n    </div>\n  );\n}"
)

# ---------------------------------------------------------------------------
# Dashboard: X2D native camera, dual nozzle gauges, skip modal
# ---------------------------------------------------------------------------

replace_once(
    "src/pages/Dashboard.tsx",
    "import ErrorPopup from '../components/ErrorPopup';",
    "import ErrorPopup from '../components/ErrorPopup';\nimport SkipObjectModal from '../components/SkipObjectModal';\nimport { serialToModel } from '../utils/hmsErrors';"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "export default function Dashboard({\n  onMenuOpen,\n  serial,\n}: {\n  onMenuOpen: () => void;\n  serial?: string;\n}) {",
    "export default function Dashboard({\n  onMenuOpen,\n  serial,\n  ip,\n  accessCode,\n}: {\n  onMenuOpen: () => void;\n  serial?: string;\n  ip?: string;\n  accessCode?: string;\n}) {"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "  const { status, frameData, refresh } = usePrinter();\n\n  const [printPreview, setPrintPreview]",
    "  const { status, frameData, refresh } = usePrinter();\n  const model = serialToModel(serial ?? '');\n  const usesNativeRtspsCamera = model === 'X2D';\n\n  const [printPreview, setPrintPreview]"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "  const [filamentBusy, setFilamentBusy] = useState(false);",
    "  const [filamentBusy, setFilamentBusy] = useState(false);\n  const [skipObjectOpen, setSkipObjectOpen] = useState(false);"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "  async function sendGcode(gcode: string) {\n    await invoke('send_gcode', { gcode }).catch(console.error);\n  }",
    "  async function sendGcode(gcode: string) {\n    await invoke('send_gcode', { gcode }).catch(console.error);\n  }\n\n  async function setNozzleTemperature(nozzleId: number, temp: number) {\n    await invoke('set_nozzle_temperature', { nozzleId, temp }).catch(console.error);\n  }\n\n  async function openNativeCamera() {\n    if (!ip || !accessCode) return;\n    await invoke('plugin:camera|open_camera', { ip, accessCode }).catch(console.error);\n  }\n\n  async function skipObjects(objectIds: number[]) {\n    await invoke('skip_objects', { objectIds });\n    await refresh();\n  }"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "            {frameData ?\n              <img\n                src={frameData}\n                className='w-full h-full object-cover'\n                alt='Live camera'\n              />\n            : <div className='flex flex-col items-center gap-2 text-center px-6'>\n                <span className='text-3xl'>📷</span>\n                <p className='text-zinc-400 text-sm font-medium'>\n                  Connecting to camera…\n                </p>\n                <p className='text-zinc-600 text-xs'>\n                  Waiting for stream on port 6000\n                </p>\n              </div>\n            }",
    "            {frameData ?\n              <img\n                src={frameData}\n                className='w-full h-full object-cover'\n                alt='Live camera'\n              />\n            : usesNativeRtspsCamera ?\n              <button onClick={openNativeCamera} className='flex h-full w-full flex-col items-center justify-center gap-2 px-6 text-center hover:bg-zinc-800'>\n                <span className='text-3xl'>📹</span>\n                <p className='text-zinc-200 text-sm font-semibold'>Open X2D live camera</p>\n                <p className='text-zinc-500 text-xs'>RTSPS · H.264 · port 322</p>\n              </button>\n            : <div className='flex flex-col items-center gap-2 text-center px-6'>\n                <span className='text-3xl'>📷</span>\n                <p className='text-zinc-400 text-sm font-medium'>Connecting to camera…</p>\n                <p className='text-zinc-600 text-xs'>Waiting for stream on port 6000</p>\n              </div>\n            }"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "              toggleLight={toggleLight}\n            />",
    "              toggleLight={toggleLight}\n              onSkipObject={() => setSkipObjectOpen(true)}\n            />"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "                <div className='grid grid-cols-3 w-full gap-3'>",
    "                <div className={`grid w-full gap-3 ${(status.nozzles?.length ?? 0) > 1 ? 'grid-cols-2' : 'grid-cols-3'}`}>"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "                    actual={status.nozzle_temp}\n                    target={status.nozzle_target}\n                    max={300}\n                    onSet={(t) => sendGcode(`M104 S${t}`)}\n                  />\n                  <TempGauge",
    "                    label={(status.nozzles?.length ?? 0) > 1 ? 'Nozzle 1' : undefined}\n                    actual={status.nozzle_temp}\n                    target={status.nozzle_target}\n                    max={350}\n                    onSet={(t) => setNozzleTemperature(0, t)}\n                  />\n                  {(status.nozzles?.length ?? 0) > 1 && (\n                    <TempGauge\n                      icon={<div className='flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-600 text-sm font-bold'>N2</div>}\n                      label='Nozzle 2'\n                      actual={status.nozzles.find((n) => n.id === 1)?.current_temp ?? 0}\n                      target={status.nozzles.find((n) => n.id === 1)?.target_temp ?? 0}\n                      max={350}\n                      onSet={(t) => setNozzleTemperature(1, t)}\n                    />\n                  )}\n                  <TempGauge"
)

replace_once(
    "src/pages/Dashboard.tsx",
    "      <ErrorPopup\n        codes={popupCodes}",
    "      {skipObjectOpen && status && (\n        <SkipObjectModal\n          skipped={status.skipped_objects ?? []}\n          layer={status.layer_num}\n          onSubmit={skipObjects}\n          onClose={() => setSkipObjectOpen(false)}\n        />\n      )}\n\n      <ErrorPopup\n        codes={popupCodes}"
)

# App passes current LAN credentials only to the local native-camera bridge.
replace_once(
    "src/App.tsx",
    "          serial={activePrinter?.serial}\n        />",
    "          serial={activePrinter?.serial}\n          ip={activePrinter?.ip}\n          accessCode={activePrinter?.accessCode}\n        />"
)

# ---------------------------------------------------------------------------
# Android native RTSPS camera activity / Tauri plugin
# ---------------------------------------------------------------------------

write(
    "src-tauri/gen/android/app/src/main/java/com/joelsgc/bamboomobile/CameraPlugin.kt",
    """package com.joelsgc.bamboomobile

import android.app.Activity
import android.content.Intent
import app.tauri.annotation.Command
import app.tauri.annotation.TauriPlugin
import app.tauri.plugin.Invoke
import app.tauri.plugin.Plugin

@TauriPlugin
class CameraPlugin(private val activity: Activity) : Plugin(activity) {
    @Command
    fun openCamera(invoke: Invoke) {
        val args = invoke.getArgs()
        val ip = args.optString("ip", "")
        val accessCode = args.optString("accessCode", args.optString("access_code", ""))
        if (ip.isBlank() || accessCode.isBlank()) {
            invoke.reject("Missing printer IP or access code")
            return
        }
        activity.startActivity(Intent(activity, CameraActivity::class.java).apply {
            putExtra(CameraActivity.EXTRA_IP, ip)
            putExtra(CameraActivity.EXTRA_ACCESS_CODE, accessCode)
        })
        invoke.resolve()
    }
}
"""
)

write(
    "src-tauri/gen/android/app/src/main/java/com/joelsgc/bamboomobile/CameraActivity.kt",
    """package com.joelsgc.bamboomobile

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.TextView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.rtsp.RtspMediaSource
import androidx.media3.ui.PlayerView
import java.net.URLEncoder
import java.security.SecureRandom
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

@androidx.annotation.OptIn(UnstableApi::class)
class CameraActivity : Activity() {
    private var player: ExoPlayer? = null
    private lateinit var errorText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = Color.BLACK
        window.navigationBarColor = Color.BLACK

        val ip = intent.getStringExtra(EXTRA_IP).orEmpty()
        val code = intent.getStringExtra(EXTRA_ACCESS_CODE).orEmpty()

        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        val playerView = PlayerView(this).apply {
            useController = true
            setShowBuffering(PlayerView.SHOW_BUFFERING_ALWAYS)
            setBackgroundColor(Color.BLACK)
        }
        root.addView(playerView, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        errorText = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = 16f
            setPadding(32, 32, 32, 32)
            visibility = TextView.GONE
        }
        root.addView(errorText, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        setContentView(root)

        if (ip.isBlank() || code.isBlank()) {
            showError("Missing X2D camera credentials")
            return
        }

        val trustAll = arrayOf<TrustManager>(object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
        })
        val sslContext = SSLContext.getInstance("TLS")
        sslContext.init(null, trustAll, SecureRandom())

        val encodedCode = URLEncoder.encode(code, Charsets.UTF_8.name()).replace("+", "%20")
        val url = "rtsps://bblp:$encodedCode@$ip:322/streaming/live/1"
        val renderers = DefaultRenderersFactory(this).setEnableDecoderFallback(true)
        val exo = ExoPlayer.Builder(this, renderers).build()
        player = exo
        playerView.player = exo
        exo.addListener(object : Player.Listener {
            override fun onPlayerError(error: PlaybackException) {
                showError("X2D camera error: ${error.errorCodeName}")
            }
        })
        val source = RtspMediaSource.Factory()
            .setSocketFactory(sslContext.socketFactory)
            .setForceUseRtpTcp(true)
            .createMediaSource(MediaItem.fromUri(url))
        exo.setMediaSource(source)
        exo.prepare()
        exo.playWhenReady = true
    }

    private fun showError(message: String) {
        errorText.text = message
        errorText.visibility = TextView.VISIBLE
    }

    override fun onDestroy() {
        player?.release()
        player = null
        super.onDestroy()
    }

    companion object {
        const val EXTRA_IP = "printer_ip"
        const val EXTRA_ACCESS_CODE = "printer_access_code"
    }
}
"""
)

replace_once(
    "src-tauri/gen/android/app/build.gradle.kts",
    "    implementation(\"androidx.lifecycle:lifecycle-process:2.10.0\")",
    "    implementation(\"androidx.lifecycle:lifecycle-process:2.10.0\")\n    // X2D camera is RTSPS/H.264 (port 322), rendered natively with Media3.\n    implementation(\"androidx.media3:media3-exoplayer:1.10.0-rc03\")\n    implementation(\"androidx.media3:media3-exoplayer-rtsp:1.10.0-rc03\")\n    implementation(\"androidx.media3:media3-ui:1.10.0-rc03\")"
)

replace_once(
    "src-tauri/gen/android/app/src/main/AndroidManifest.xml",
    "        <!--\n          PrinterForegroundService keeps the process alive while a print is",
    "        <activity\n            android:name=\".CameraActivity\"\n            android:exported=\"false\"\n            android:screenOrientation=\"sensorLandscape\"\n            android:theme=\"@style/Theme.AppCompat.NoActionBar\" />\n\n        <!--\n          PrinterForegroundService keeps the process alive while a print is"
)

print("X2D audit patch applied successfully")
