from pathlib import Path
import json, re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)

# ── Tauri ACL: declare and grant the native X2D camera plugin ─────────────────
build = Path("src-tauri/build.rs")
build.write_text('''fn main() {
    // Declare mobile plugins so Tauri v2 generates ACL permissions for frontend invokes.
    let attrs = tauri_build::Attributes::new()
        .plugin(
            "printNotification",
            tauri_build::InlinedPlugin::new()
                .commands(&["start_notification", "update_notification", "stop_notification"])
                .default_permission(tauri_build::DefaultPermissionRule::AllowAllCommands),
        )
        .plugin(
            "x2dCamera",
            tauri_build::InlinedPlugin::new()
                .commands(&["show_camera", "update_bounds", "hide_camera"])
                .default_permission(tauri_build::DefaultPermissionRule::AllowAllCommands),
        );
    tauri_build::try_build(attrs).expect("failed to run tauri-build");
}
''')

caps_path = Path("src-tauri/capabilities/default.json")
caps = json.loads(caps_path.read_text())
perms = caps.setdefault("permissions", [])
if "x2dCamera:default" not in perms:
    perms.append("x2dCamera:default")
caps_path.write_text(json.dumps(caps, indent=2) + "\n")

# ── Android foreground service: stored credentials belong to the connection,
# not one print. Keep them across an idle/finished standalone-service session.
svc_path = Path("src-tauri/gen/android/app/src/main/java/com/joelsgc/bamboomobile/PrinterForegroundService.kt")
svc = svc_path.read_text()
svc = re.sub(r'\n\s*clearStoredCredentials\(\)\n(\s*)stopSelf\(\)', r'\n\1stopSelf()', svc)
svc_path.write_text(svc)

# ── Rust backend hardening ────────────────────────────────────────────────────
lib_path = Path("src-tauri/src/lib.rs")
s = lib_path.read_text()

# Abort child tasks when their parent worker is aborted.
s = replace_once(
    s,
    '''struct ConnectionHandles {
    ip: String,''',
    '''struct AbortOnDrop(AbortHandle);

impl Drop for AbortOnDrop {
    fn drop(&mut self) {
        self.0.abort();
    }
}

struct ConnectionHandles {
    ip: String,''',
    "AbortOnDrop type",
)

# Make debug truncation UTF-8 safe.
s = replace_once(
    s,
    '''// ── SSDP: retrieve DevName.bambu.com via unicast M-SEARCH + multicast NOTIFY ──''',
    '''fn truncate_for_log(s: &str, max_chars: usize) -> String {
    s.chars().take(max_chars).collect()
}

// ── SSDP: retrieve DevName.bambu.com via unicast M-SEARCH + multicast NOTIFY ──''',
    "truncate helper",
)
s = s.replace('&text[..text.len().min(400)]', 'truncate_for_log(&text, 400)')
s = s.replace('&msg[..msg.len().min(300)]', 'truncate_for_log(&msg, 300)')
s = s.replace('&msg[..msg.len().min(200)]', 'truncate_for_log(&msg, 200)')

# Preserve abort handles for SSDP child listener tasks through RAII guards.
s = replace_once(
    s,
    '''        tokio::spawn(async move {
            ssdp_multicast_listen(su, st, ap).await;
        });
    }
    // Listener on port 2021 (Bambu direct broadcast port)
    {
        let su = serial_upper.clone();
        let st = status.clone();
        let ap = app.clone();
        tokio::spawn(async move {
            ssdp_port_listen(2021, su, st, ap).await;
        });
    }''',
    '''        let h = tokio::spawn(async move {
            ssdp_multicast_listen(su, st, ap).await;
        });
        let _multicast_guard = AbortOnDrop(h.abort_handle());
        drop(h);

        // Listener on port 2021 (Bambu direct broadcast port)
        let su = serial_upper.clone();
        let st = status.clone();
        let ap = app.clone();
        let h = tokio::spawn(async move {
            ssdp_port_listen(2021, su, st, ap).await;
        });
        let _port2021_guard = AbortOnDrop(h.abort_handle());
        drop(h);

        // Keep both guards alive for the lifetime of this parent future.
        let _listener_guards = (_multicast_guard, _port2021_guard);
    }''',
    "SSDP child guards",
)

# Reject CR/LF in every FTP command line. This blocks path/filename command injection
# regardless of whether the value came from UI input or a printer directory listing.
s = replace_once(
    s,
    '''fn ftp_writeln(s: &mut impl Write, cmd: &str) -> Result<(), String> {
    s.write_all(format!("{}\\r\\n", cmd).as_bytes())
        .map_err(|e| e.to_string())
}''',
    '''fn ftp_writeln(s: &mut impl Write, cmd: &str) -> Result<(), String> {
    if cmd.contains('\\r') || cmd.contains('\\n') {
        return Err("Invalid FTP command argument".to_string());
    }
    s.write_all(format!("{}\\r\\n", cmd).as_bytes())
        .map_err(|e| e.to_string())
}''',
    "FTP command injection guard",
)

# Cache preview files under a sanitized local key; never treat job names as paths.
s = replace_once(
    s,
    '''    // Cache is stored without extension; MIME is detected from magic bytes on read-back.
    let cache_dir = app.path().app_cache_dir().map_err(|e| e.to_string())?;
    let cache_path = cache_dir.join("previews").join(&subtask_name);''',
    '''    // Cache is stored without extension; MIME is detected from magic bytes on read-back.
    // The job name is printer-controlled text, so never use it directly as a local path.
    let cache_key: String = subtask_name
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.') { c } else { '_' })
        .take(120)
        .collect();
    let cache_key = if cache_key.is_empty() { "preview".to_string() } else { cache_key };
    let cache_dir = app.path().app_cache_dir().map_err(|e| e.to_string())?;
    let cache_path = cache_dir.join("previews").join(cache_key);''',
    "preview cache path",
)

# Stream downloads to disk rather than buffering an entire video/timelapse in RAM.
s = replace_once(
    s,
    '''        let mut bytes = Vec::new();
        data.read_to_end(&mut bytes).map_err(|e| e.to_string())?;
        drop(data);
        ftp_read_response(ctrl).ok();

        std::fs::write(&save_path, &bytes).map_err(|e| e.to_string())?;
        Ok(filename)''',
    '''        let mut out = std::fs::File::create(&save_path).map_err(|e| e.to_string())?;
        std::io::copy(&mut data, &mut out).map_err(|e| e.to_string())?;
        out.flush().map_err(|e| e.to_string())?;
        drop(data);
        ftp_read_response(ctrl).ok();
        Ok(filename)''',
    "stream download",
)

# AMS load/unload: do not invent a generic 210/220 C temperature for X2D materials.
# -1 tells current Bambu firmware to use the tray/printer profile temperatures.
s = re.sub(
    r'''\n\s*let curr_tray = status\.tray_now;\n\s*let curr_temp = tray_temperature\(&status, curr_tray\);\n\s*let tar_temp\s*= tray_temperature\(&status, tray_id\);''',
    '\n        let curr_tray = status.tray_now;',
    s,
    count=1,
)
s = replace_once(s, '"curr_temp":   curr_temp,\n                "tar_temp":    tar_temp,', '"curr_temp":   -1,\n                "tar_temp":    -1,', "load filament temperatures")
s = re.sub(
    r'''\n\s*let curr_tray = status\.tray_now;\n\s*let curr_temp = tray_temperature\(&status, curr_tray\);''',
    '\n        let curr_tray = status.tray_now;',
    s,
    count=1,
)
s = replace_once(s, '"curr_temp":   curr_temp,\n                "tar_temp":    curr_temp,', '"curr_temp":   -1,\n                "tar_temp":    -1,', "unload filament temperatures")

# The old tray-temperature helper is no longer used after delegating temperatures to firmware.
s = re.sub(
    r'''// Returns the print temperature for any global slot ID\.\nfn tray_temperature\(.*?\n}\n\n#\[tauri::command\]\nasync fn load_filament''',
    '#[tauri::command]\nasync fn load_filament',
    s,
    count=1,
    flags=re.S,
)

# Strict Clippy findings from the full post-patch audit.
s = s.replace(
    'entries.sort_by(|a, b| b.modified.cmp(&a.modified));',
    'entries.sort_by_key(|a| std::cmp::Reverse(a.modified));',
)
s = s.replace("path.split('/').last()", "path.split('/').next_back()")

lib_path.write_text(s)

# ── UI safety / credential presentation ──────────────────────────────────────
settings = Path("src/pages/SettingsPanel.tsx")
st = settings.read_text()
# Only change the access-code field; leave IP/serial inputs unchanged.
st = re.sub(r'(ACCESS CODE.*?<input\s+)(?![^>]*type=)', r'\1type="password"\n              ', st, count=1, flags=re.S)
settings.write_text(st)

status_card = Path("src/components/PrintStatusCard.tsx")
pc = status_card.read_text()
pc = replace_once(
    pc,
    "onClick={() => onCommand('stop')}",
    "onClick={() => { if (window.confirm('Stop the current print?')) onCommand('stop'); }}",
    "stop confirmation",
)
status_card.write_text(pc)

print("Post-RC2 audit fixes applied")
