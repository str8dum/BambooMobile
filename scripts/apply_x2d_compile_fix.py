from pathlib import Path

# This script is also part of the full-audit trigger set; touching it here
# ensures the audited run includes the final Android camera/compile fixes.
lib_path = Path("src-tauri/src/lib.rs")
s = lib_path.read_text()

# apply_x2d_final.py intentionally removed the now-unused curr_tray lookup from
# filament loading, but the original broad cleanup also removed the copy that
# unload_filament still needs to derive the AMS unit. Repair the two functions
# independently so Clippy stays clean and unload still has its tray context.
load_start = s.index("async fn load_filament")
unload_start = s.index("async fn unload_filament", load_start)
load = s[load_start:unload_start]
status_line = "        let status = c.status.lock().await;\n"
if status_line not in load:
    raise SystemExit("load_filament unused status marker not found")
load = load.replace(status_line, "", 1)
s = s[:load_start] + load + s[unload_start:]

# Recompute unload_start because the preceding edit changed offsets.
unload_start = s.index("async fn unload_filament")
needle = "        let ams_id: u8 = if curr_tray == 255 || curr_tray == 254 {"
if needle not in s[unload_start:]:
    raise SystemExit("unload_filament ams_id marker not found")
replacement = "        let curr_tray = status.tray_now;\n" + needle
before = s[:unload_start]
after = s[unload_start:].replace(needle, replacement, 1)
s = before + after

lib_path.write_text(s)

# Keep camera-only pinch zoom in the same exact production patch stack used by
# both test and audited APKs. The zoom patch is idempotent, so workflows that
# invoke it explicitly after this step remain safe.
zoom_patch = Path("scripts/apply_x2d_camera_zoom.py")
namespace = {"__name__": "__main__", "__file__": str(zoom_patch)}
exec(compile(zoom_patch.read_text(), str(zoom_patch), "exec"), namespace)

print("X2D final compile regression fixed")
