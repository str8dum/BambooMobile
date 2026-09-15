from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# ── Rust: dual-nozzle parsing + camera capability + Android camera plugin ─────
lib = Path("src-tauri/src/lib.rs")
s = lib.read_text()

s = replace_once(
    s,
    '''    pub nozzle_temp: f64,
    pub nozzle_target: f64,
    pub bed_temp: f64,''',
    '''    pub nozzle_temp: f64,
    pub nozzle_target: f64,
    // X2D dual-nozzle telemetry. Bambu encodes right nozzle as extruder id 0
    // and left nozzle as extruder id 1. `active_nozzle` uses the same ids.
    pub dual_nozzle: bool,
    pub active_nozzle: u8,
    pub left_nozzle_temp: f64,
    pub left_nozzle_target: f64,
    pub right_nozzle_temp: f64,
    pub right_nozzle_target: f64,
    // True when the printer reports a LAN RTSP/RTSPS liveview URL.
    pub camera_rtsp_enabled: bool,
    pub bed_temp: f64,''',
    "PrinterStatus X2D fields",
)

s = replace_once(
    s,
    '''    f64_field!(status.nozzle_temp, "nozzle_temper");
    f64_field!(status.nozzle_target, "nozzle_target_temper");
    f64_field!(status.bed_temp, "bed_temper");''',
    '''    // Legacy/single-nozzle fields remain the fallback and also represent the
    // active nozzle on X2D. The X2D device.extruder block below gives us both
    // physical nozzles and overrides these active-nozzle values when available.
    f64_field!(status.nozzle_temp, "nozzle_temper");
    f64_field!(status.nozzle_target, "nozzle_target_temper");

    if let Some(extruder) = p.get("device").and_then(|v| v.get("extruder")) {
        let mut saw_right = false;
        let mut saw_left = false;
        if let Some(entries) = extruder.get("info").and_then(|v| v.as_array()) {
            for entry in entries {
                let id = entry
                    .get("id")
                    .and_then(|v| v.as_u64().or_else(|| v.as_str().and_then(|s| s.parse().ok())));
                let packed = entry
                    .get("temp")
                    .and_then(|v| v.as_u64().or_else(|| v.as_str().and_then(|s| s.parse().ok())));
                let (Some(id), Some(packed)) = (id, packed) else { continue };
                let current = (packed & 0xFFFF) as f64;
                let target = ((packed >> 16) & 0xFFFF) as f64;
                match id {
                    0 => {
                        status.right_nozzle_temp = current;
                        status.right_nozzle_target = target;
                        saw_right = true;
                    }
                    1 => {
                        status.left_nozzle_temp = current;
                        status.left_nozzle_target = target;
                        saw_left = true;
                    }
                    _ => {}
                }
            }
        }

        if saw_right && saw_left {
            status.dual_nozzle = true;
            if let Some(state) = extruder
                .get("state")
                .and_then(|v| v.as_u64().or_else(|| v.as_str().and_then(|s| s.parse().ok())))
            {
                // Low nibble = extruder count, next nibble = active extruder id.
                let active = ((state >> 4) & 0x0F) as u8;
                if active <= 1 {
                    status.active_nozzle = active;
                }
            }

            match status.active_nozzle {
                0 => {
                    status.nozzle_temp = status.right_nozzle_temp;
                    status.nozzle_target = status.right_nozzle_target;
                }
                1 => {
                    status.nozzle_temp = status.left_nozzle_temp;
                    status.nozzle_target = status.left_nozzle_target;
                }
                _ => {}
            }
        }
    }

    if let Some(url) = p
        .get("ipcam")
        .and_then(|v| v.get("rtsp_url"))
        .and_then(|v| v.as_str())
    {
        status.camera_rtsp_enabled = url.starts_with("rtsp://") || url.starts_with("rtsps://");
    }

    f64_field!(status.bed_temp, "bed_temper");''',
    "X2D dual nozzle parser",
)

# Register native Android camera plugin alongside the existing notification plugin.
s = replace_once(
    s,
    '''    builder
        .plugin(tauri_plugin_deep_link::init())''',
    '''    #[cfg(target_os = "android")]
    let builder = builder.plugin(
        tauri::plugin::Builder::<tauri::Wry, ()>::new("x2dCamera")
            .setup(|_app, api| {
                if let Err(e) = api.register_android_plugin(
                    "com.joelsgc.bamboomobile",
                    "X2dCameraPlugin",
                ) {
                    eprintln!("[X2dCamera] register_android_plugin failed: {:?}", e);
                }
                Ok(())
            })
            .build(),
    );

    builder
        .plugin(tauri_plugin_deep_link::init())''',
    "X2D camera plugin registration",
)

# Add independent regression coverage for the packed X2D extruder temperatures.
s += r'''

#[cfg(test)]
mod x2d_dual_nozzle_tests {
    use super::*;

    #[test]
    fn decodes_x2d_dual_nozzle_temperatures_and_active_tool() {
        let payload = serde_json::json!({
            "print": {
                "command": "push_status",
                "nozzle_temper": 999.0,
                "nozzle_target_temper": 999.0,
                "ipcam": {
                    "rtsp_url": "rtsps://192.0.2.1:322/streaming/live/1"
                },
                "device": {
                    "extruder": {
                        "info": [
                            {"id": 0, "temp": ((220u64 << 16) | 210u64)},
                            {"id": 1, "temp": ((255u64 << 16) | 250u64)}
                        ],
                        "state": 0x12
                    }
                }
            }
        });
        let bytes = serde_json::to_vec(&payload).unwrap();
        let mut st = PrinterStatus::default();
        assert!(parse_status(&bytes, &mut st));
        assert!(st.dual_nozzle);
        assert_eq!(st.active_nozzle, 1);
        assert_eq!(st.right_nozzle_temp, 210.0);
        assert_eq!(st.right_nozzle_target, 220.0);
        assert_eq!(st.left_nozzle_temp, 250.0);
        assert_eq!(st.left_nozzle_target, 255.0);
        // Legacy active-nozzle fields should now follow the selected physical nozzle.
        assert_eq!(st.nozzle_temp, 250.0);
        assert_eq!(st.nozzle_target, 255.0);
        assert!(st.camera_rtsp_enabled);
    }
}
'''
lib.write_text(s)

# ── Android: Media3 RTSPS dependencies ────────────────────────────────────────
gradle = Path("src-tauri/gen/android/app/build.gradle.kts")
g = gradle.read_text()
g = replace_once(
    g,
    '    implementation("androidx.lifecycle:lifecycle-process:2.10.0")',
    '''    implementation("androidx.lifecycle:lifecycle-process:2.10.0")
    // X2D liveview: H.264 over RTSPS (TLS) on port 322.
    implementation("androidx.media3:media3-exoplayer:1.11.0")
    implementation("androidx.media3:media3-exoplayer-rtsp:1.11.0")''',
    "Media3 dependencies",
)
gradle.write_text(g)

# ── TypeScript status model ────────────────────────────────────────────────────
vite = Path("src/vite-env.d.ts")
v = vite.read_text()
v = replace_once(
    v,
    '''  nozzle_temp: number;
  nozzle_target: number;
  bed_temp: number;''',
    '''  nozzle_temp: number;
  nozzle_target: number;
  dual_nozzle: boolean;
  /** X2D: 0 = right, 1 = left. */
  active_nozzle: number;
  left_nozzle_temp: number;
  left_nozzle_target: number;
  right_nozzle_temp: number;
  right_nozzle_target: number;
  camera_rtsp_enabled: boolean;
  bed_temp: number;''',
    "TypeScript X2D fields",
)
vite.write_text(v)

# ── ETA: the old UI intentionally prepended a minus sign; show time remaining ─
printer = Path("src/utils/printer.ts")
ptext = printer.read_text()
ptext = replace_once(
    ptext,
    '''  return h > 0 ? `-${h}h${m}m` : `-${m}m`;''',
    '''  return h > 0 ? `${h}h${m}m` : `${m}m`;''',
    "ETA minus sign",
)
printer.write_text(ptext)

# ── Dashboard: native RTSPS overlay + dual-nozzle cards ───────────────────────
dash = Path("src/pages/Dashboard.tsx")
d = dash.read_text()
d = replace_once(
    d,
    "import TempGauge from '../components/TempGauge';",
    "import TempGauge from '../components/TempGauge';\nimport DualNozzleGauge from '../components/DualNozzleGauge';",
    "DualNozzleGauge import",
)

d = replace_once(
    d,
    '''export default function Dashboard({
  onMenuOpen,
  serial,
}: {
  onMenuOpen: () => void;
  serial?: string;
}) {''',
    '''export default function Dashboard({
  onMenuOpen,
  serial,
  ip,
  accessCode,
  cameraVisible = true,
}: {
  onMenuOpen: () => void;
  serial?: string;
  ip?: string;
  accessCode?: string;
  cameraVisible?: boolean;
}) {''',
    "Dashboard camera props",
)

d = replace_once(
    d,
    '''  const prevGcodeStateRef = useRef('');
  // Keep serial in a ref''',
    '''  const prevGcodeStateRef = useRef('');
  const cameraRef = useRef<HTMLDivElement>(null);
  // Keep serial in a ref''',
    "camera ref",
)

camera_effect = r'''

  // X2D uses H.264 over RTSPS rather than the legacy MJPEG/TLS stream.
  // A native Media3 TextureView is positioned over this page's camera card.
  useEffect(() => {
    if (!status?.dual_nozzle || !ip || !accessCode || !cameraVisible) {
      invoke('plugin:x2dCamera|hide_camera').catch(() => {});
      return;
    }

    const el = cameraRef.current;
    if (!el) return;

    let disposed = false;
    let started = false;
    let raf = 0;

    const syncBounds = async () => {
      if (disposed || !cameraRef.current) return;
      const r = cameraRef.current.getBoundingClientRect();
      const visible =
        document.visibilityState === 'visible' &&
        r.width > 1 &&
        r.height > 1 &&
        r.bottom > 0 &&
        r.top < window.innerHeight;
      const args = {
        ip,
        accessCode,
        x: r.left,
        y: r.top,
        width: r.width,
        height: r.height,
        scale: window.devicePixelRatio || 1,
        visible,
      };
      try {
        if (!started) {
          await invoke('plugin:x2dCamera|show_camera', args);
          started = true;
        } else {
          await invoke('plugin:x2dCamera|update_bounds', args);
        }
      } catch {
        // Non-Android builds do not register the native camera plugin.
      }
    };

    const scheduleSync = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => void syncBounds());
    };

    scheduleSync();
    window.addEventListener('resize', scheduleSync);
    document.addEventListener('scroll', scheduleSync, true);
    document.addEventListener('visibilitychange', scheduleSync);
    const ro = new ResizeObserver(scheduleSync);
    ro.observe(el);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener('resize', scheduleSync);
      document.removeEventListener('scroll', scheduleSync, true);
      document.removeEventListener('visibilitychange', scheduleSync);
      invoke('plugin:x2dCamera|hide_camera').catch(() => {});
    };
  }, [status?.dual_nozzle, ip, accessCode, cameraVisible]);
'''

d = replace_once(
    d,
    '''  serialRef.current = serial;

  // React to every status update''',
    '''  serialRef.current = serial;''' + camera_effect + '''

  // React to every status update''',
    "native camera effect",
)

d = replace_once(
    d,
    "          <div className='rounded-xl overflow-hidden bg-zinc-900 aspect-video flex items-center justify-center shrink-0'>",
    "          <div ref={cameraRef} className='rounded-xl overflow-hidden bg-zinc-900 aspect-video flex items-center justify-center shrink-0'>",
    "camera card ref",
)

d = replace_once(
    d,
    '''                  Waiting for stream on port 6000''',
    '''                  {status?.dual_nozzle ?
                    status.camera_rtsp_enabled ? 'X2D secure H.264 stream · port 322' : 'Enable LAN Only Liveview on the X2D'
                  : 'Waiting for stream on port 6000'}''',
    "camera placeholder",
)

# Put a dedicated left/right readout above the existing active-nozzle/bed/speed row.
d = replace_once(
    d,
    "                <div className='grid grid-cols-3 w-full gap-3'>",
    '''                <div className='flex flex-col w-full gap-4'>
                  {status.dual_nozzle && (
                    <div className='grid grid-cols-2 w-full gap-3'>
                      <DualNozzleGauge
                        label='Left'
                        actual={status.left_nozzle_temp}
                        target={status.left_nozzle_target}
                        active={status.active_nozzle === 1}
                      />
                      <DualNozzleGauge
                        label='Right'
                        actual={status.right_nozzle_temp}
                        target={status.right_nozzle_target}
                        active={status.active_nozzle === 0}
                      />
                    </div>
                  )}
                  <div className='grid grid-cols-3 w-full gap-3'>''',
    "dual nozzle row",
)
# Close the extra flex wrapper around the temperature section. The first matching
# Section close is the printer-temperature section.
d = replace_once(
    d,
    '''                </div>
              </Section>''',
    '''                  </div>
                </div>
              </Section>''',
    "temperature wrapper close",
)
dash.write_text(d)

# App passes active printer credentials to the native camera plugin through Dashboard.
app = Path("src/App.tsx")
a = app.read_text()
a = replace_once(
    a,
    '''          onMenuOpen={() => setSidebarOpen(true)}
          serial={activePrinter?.serial}
        />''',
    '''          onMenuOpen={() => setSidebarOpen(true)}
          serial={activePrinter?.serial}
          ip={activePrinter?.ip}
          accessCode={activePrinter?.accessCode}
          cameraVisible={!sidebarOpen}
        />''',
    "Dashboard camera props in App",
)
app.write_text(a)

print("X2D RC2 camera + dual-nozzle patch applied")
