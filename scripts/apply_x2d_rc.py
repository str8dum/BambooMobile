from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


lib = Path("src-tauri/src/lib.rs")
s = lib.read_text()

# Normalize credentials/topic inputs in the backend.
s = replace_once(
    s,
    '''    if conn.is_some() {
        return Err("Already connected".into());
    }

    // MQTT with TLS''',
    '''    if conn.is_some() {
        return Err("Already connected".into());
    }

    let ip = ip.trim().to_string();
    let access_code = access_code.trim().to_string();
    let serial = serial.trim().to_uppercase();
    if ip.is_empty() || access_code.is_empty() || serial.is_empty() {
        return Err("Printer IP, access code and serial are required".into());
    }

    // MQTT with TLS''',
    "connect input",
)

# Use a fresh short MQTT client id and remove rumqttc's tiny default packet ceiling.
s = replace_once(
    s,
    '''    let mut opts = MqttOptions::new("bamboo-mobile", &ip, 8883);
    opts.set_credentials("bblp", &access_code);
    opts.set_keep_alive(std::time::Duration::from_secs(10));''',
    '''    let client_id = format!(
        "bm-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() % 10_000_000_000u128
    );
    let mut opts = MqttOptions::new(client_id, &ip, 8883);
    opts.set_credentials("bblp", &access_code);
    opts.set_keep_alive(std::time::Duration::from_secs(10));
    opts.set_clean_session(true);
    opts.set_max_packet_size(256 * 1024, 256 * 1024);''',
    "MqttOptions",
)

# Match current Studio pushall payload. Pushall stays QoS 0; get_version becomes QoS 1.
s = replace_once(
    s,
    '''        let pushall = serde_json::json!({
            "pushing": {"sequence_id": "0", "command": "pushall", "version": 1}
        })
        .to_string();
        let get_version = serde_json::json!({
            "info": {"sequence_id": "0", "command": "get_version"}
        })''',
    '''        let pushall = serde_json::json!({
            "pushing": {
                "sequence_id": "20000",
                "command": "pushall",
                "version": 1,
                "push_target": 1
            }
        })
        .to_string();
        let get_version = serde_json::json!({
            "info": {"sequence_id": "20001", "command": "get_version"}
        })''',
    "pushall/get_version",
)

s = replace_once(
    s,
    '.publish(&req_topic, QoS::AtMostOnce, false, get_version.clone())',
    '.publish(&req_topic, QoS::AtLeastOnce, false, get_version.clone())',
    "get_version QoS",
)

# parse_status returns whether this was actually a print/status message.
s = replace_once(
    s,
    '''fn parse_status(payload: &[u8], status: &mut PrinterStatus) {
    let Ok(v) = serde_json::from_slice::<serde_json::Value>(payload) else {
        return;
    };

    // device_name is set via SSDP discovery (DevName.bambu.com), not MQTT.

    let Some(p) = v.get("print") else { return };''',
    '''fn parse_status(payload: &[u8], status: &mut PrinterStatus) -> bool {
    let Ok(v) = serde_json::from_slice::<serde_json::Value>(payload) else {
        return false;
    };

    // device_name is set via SSDP discovery (DevName.bambu.com), not MQTT.

    let Some(p) = v.get("print") else { return false };''',
    "parse_status header",
)

s = replace_once(
    s,
    '''            .unwrap_or_default();
    }
}

fn stage_name''',
    '''            .unwrap_or_default();
    }

    true
}

fn stage_name''',
    "parse_status end",
)

s = replace_once(
    s,
    '                    parse_status(&msg.payload, &mut st);',
    '''                    if !parse_status(&msg.payload, &mut st) {
                        continue;
                    }''',
    "parse_status call",
)

# Surface all event-loop errors in the existing MQTT Debug stream.
s = replace_once(
    s,
    '''                Err(_) => {
                    tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                }''',
    '''                Err(e) => {
                    let _ = app_c.emit(
                        "mqtt-raw",
                        serde_json::json!({"_mqtt_error": e.to_string()}).to_string(),
                    );
                    tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                }''',
    "eventloop error",
)

# Regression tests for X2D-compatible status fields and non-status info packets.
s += r'''

#[cfg(test)]
mod x2d_compat_tests {
    use super::*;

    #[test]
    fn x2d_compat_parse_status_fields() {
        let payload = serde_json::json!({
            "print": {
                "command": "push_status",
                "nozzle_temper": 250.0,
                "nozzle_target_temper": "255.0",
                "bed_temper": 70.0,
                "bed_target_temper": "72.0",
                "mc_percent": 98,
                "mc_remaining_time": "2",
                "layer_num": 129,
                "total_layer_num": "140",
                "spd_lvl": 2,
                "gcode_state": "RUNNING",
                "subtask_name": "X2D parser test",
                "task_id": "123",
                "stg_cur": 17,
                "device": {
                    "extruder": {"info": [{"id": 0}, {"id": 1}]},
                    "nozzle": {"exist": 3, "info": [{"id": 0}, {"id": 1}]}
                },
                "3D": {"layer_num": 129, "total_layer_num": 140}
            }
        });
        let bytes = serde_json::to_vec(&payload).unwrap();
        let mut st = PrinterStatus::default();
        assert!(parse_status(&bytes, &mut st));
        assert_eq!(st.nozzle_temp, 250.0);
        assert_eq!(st.nozzle_target, 255.0);
        assert_eq!(st.bed_temp, 70.0);
        assert_eq!(st.bed_target, 72.0);
        assert_eq!(st.progress, 98);
        assert_eq!(st.remaining_mins, 2);
        assert_eq!(st.layer_num, 129);
        assert_eq!(st.total_layer_num, 140);
        assert_eq!(st.gcode_state, "RUNNING");
    }

    #[test]
    fn x2d_info_message_is_not_status() {
        let bytes = br#"{"info":{"command":"get_version","sequence_id":"0"}}"#;
        let mut st = PrinterStatus::default();
        assert!(!parse_status(bytes, &mut st));
        assert_eq!(st.nozzle_temp, 0.0);
    }
}
'''
lib.write_text(s)

# Keep Android's standalone MQTT fallback consistent. Paho already uses QoS 0.
svc = Path("src-tauri/gen/android/app/src/main/java/com/joelsgc/bamboomobile/PrinterForegroundService.kt")
k = svc.read_text()
k = replace_once(
    k,
    '"""{"pushing":{"sequence_id":"0","command":"pushall","version":1}}"""',
    '"""{"pushing":{"sequence_id":"20000","command":"pushall","version":1,"push_target":1}}"""',
    "Kotlin pushall",
)
svc.write_text(k)

# Manual Debug Pushall must exercise the same wire payload as startup.
dbg = Path("src/pages/DebugPage.tsx")
d = dbg.read_text()
d, n = re.subn(r"MQTT Debug — X2D\.\d+", "MQTT Debug — X2D RC1", d, count=1)
if n != 1:
    raise SystemExit("Debug heading marker not found")
d, n = re.subn(
    r"sendRequest\(\{ pushing: \{ sequence_id: '[^']+', command: 'pushall'(?:, version: 1, push_target: 1)? \} \}\)",
    "sendRequest({ pushing: { sequence_id: '20000', command: 'pushall', version: 1, push_target: 1 } })",
    d,
    count=1,
)
if n != 1:
    raise SystemExit("Debug pushall marker not found")
dbg.write_text(d)

print("Consolidated X2D RC patch applied")
