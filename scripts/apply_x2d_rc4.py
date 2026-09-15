from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# RC4 fixes the shared root cause seen on a real X2D: model-specific UI/camera
# behavior must not depend on whether a particular incremental MQTT packet
# happens to contain device.extruder.info. The configured X2D serial (20P...)
# is authoritative for capabilities; telemetry still fills the live values.
# This script is intentionally applied after the RC1/RC2 patch scripts in CI.

# ── Rust backend: seed X2D capabilities from the configured serial ────────────
lib = Path("src-tauri/src/lib.rs")
s = lib.read_text()

s = replace_once(
    s,
    '''    let status = Arc::new(Mutex::new(PrinterStatus::default()));''',
    '''    // X2D capability is a property of the configured printer, not of any
    // single MQTT status delta. 20P is the X2D serial prefix. Seed these flags
    // before the first packet so the UI cannot fall back to the single-nozzle
    // / port-6000 path while waiting for device.extruder.info.
    let is_x2d = serial.starts_with("20P");
    let mut initial_status = PrinterStatus::default();
    if is_x2d {
        initial_status.dual_nozzle = true;
        initial_status.camera_rtsp_enabled = true;
    }
    let status = Arc::new(Mutex::new(initial_status));''',
    "seed X2D status capabilities",
)

s = replace_once(
    s,
    '''    // Camera: MJPG over TLS on port 6000
    let camera_handle = tokio::spawn(camera_loop(ip.clone(), access_code.clone(), app.clone()));
    abort_handles.push(camera_handle.abort_handle());
    drop(camera_handle);''',
    '''    // Port 6000 is the legacy Bambu MJPEG/TLS camera protocol. X2D uses
    // H.264 over RTSPS on port 322 through the native Android camera plugin,
    // so never start the legacy camera worker for an X2D.
    if !is_x2d {
        let camera_handle =
            tokio::spawn(camera_loop(ip.clone(), access_code.clone(), app.clone()));
        abort_handles.push(camera_handle.abort_handle());
        drop(camera_handle);
    }''',
    "disable legacy camera worker on X2D",
)

lib.write_text(s)

# ── Frontend: key X2D behavior off both serial and backend capability ─────────
dash = Path("src/pages/Dashboard.tsx")
d = dash.read_text()

d = replace_once(
    d,
    '''  const cameraRef = useRef<HTMLDivElement>(null);
  // Keep serial in a ref''',
    '''  const cameraRef = useRef<HTMLDivElement>(null);
  // Do not infer the printer model from a transient telemetry field. The 20P
  // serial prefix identifies X2D even before the first full status dump arrives.
  const isX2D = serial?.trim().toUpperCase().startsWith('20P') ?? false;
  // Keep serial in a ref''',
    "frontend X2D model flag",
)

d = replace_once(
    d,
    '''    if (!status?.dual_nozzle || !ip || !accessCode || !cameraVisible) {''',
    '''    if (!(status?.dual_nozzle || isX2D) || !ip || !accessCode || !cameraVisible) {''',
    "native camera X2D gate",
)

d = replace_once(
    d,
    '''  }, [status?.dual_nozzle, ip, accessCode, cameraVisible]);''',
    '''  }, [status?.dual_nozzle, isX2D, ip, accessCode, cameraVisible]);''',
    "native camera dependencies",
)

d = replace_once(
    d,
    '''                  {status?.dual_nozzle ?
                    status.camera_rtsp_enabled ? 'X2D secure H.264 stream · port 322' : 'Enable LAN Only Liveview on the X2D'
                  : 'Waiting for stream on port 6000'}''',
    '''                  {(status?.dual_nozzle || isX2D)
                    ? 'X2D secure H.264 stream · port 322'
                    : 'Waiting for stream on port 6000'}''',
    "camera placeholder model gate",
)

d = replace_once(
    d,
    '''                  {status.dual_nozzle && (''',
    '''                  {(status.dual_nozzle || isX2D) && (''',
    "dual-nozzle UI model gate",
)

dash.write_text(d)

# ── Android dependency cleanup ────────────────────────────────────────────────
# RC2 originally injected Media3 while the current native plugin uses the
# dedicated alexeyvasilyev RTSP/RTSPS client. Remove the now-unused Media3 pair
# after RC2 has run, and assert the actual player dependency remains present.
gradle = Path("src-tauri/gen/android/app/build.gradle.kts")
g = gradle.read_text()
g = g.replace(
    '''    // X2D liveview: H.264 over RTSPS (TLS) on port 322.\n    implementation("androidx.media3:media3-exoplayer:1.11.0")\n    implementation("androidx.media3:media3-exoplayer-rtsp:1.11.0")\n''',
    '',
)
if 'implementation("com.github.alexeyvasilyev:rtsp-client-android:5.2.0")' not in g:
    raise SystemExit("dedicated X2D RTSPS client dependency missing")
gradle.write_text(g)

print("X2D RC4 model-gating regression fix applied")
