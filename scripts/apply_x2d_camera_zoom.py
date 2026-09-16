from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# The X2D video is a native Android SurfaceView layered above the Tauri WebView.
# Browser/page pinch zoom therefore cannot scale the actual video. Intercept pinch
# gestures only inside the camera card and forward a camera-only zoom transform to
# the native X2D camera plugin. Keep one-finger vertical panning available so the
# dashboard still scrolls naturally.
dash_path = Path("src/pages/Dashboard.tsx")
d = dash_path.read_text()

marker = "  }, [status?.dual_nozzle, ip, accessCode, cameraVisible]);\n"
zoom_effect = r'''

  // Camera-only pinch zoom for X2D. The native SurfaceView is outside the
  // WebView transform tree, so browser pinch zoom would enlarge the dashboard
  // behind the video without enlarging the video itself.
  useEffect(() => {
    if (!status?.dual_nozzle || !cameraVisible) return;

    const el = cameraRef.current;
    if (!el) return;

    const pointers = new Map<number, { x: number; y: number }>();
    let zoom = 1;
    let pinchStartDistance = 0;
    let pinchStartZoom = 1;
    let zoomRaf = 0;
    let pendingZoom = 1;
    let pendingFocusX = 0.5;
    let pendingFocusY = 0.5;

    const clamp = (value: number, min: number, max: number) =>
      Math.min(max, Math.max(min, value));

    const queueNativeZoom = (nextZoom: number, focusX: number, focusY: number) => {
      zoom = clamp(nextZoom, 1, 4);
      pendingZoom = zoom;
      pendingFocusX = clamp(focusX, 0, 1);
      pendingFocusY = clamp(focusY, 0, 1);
      if (zoomRaf) return;
      zoomRaf = requestAnimationFrame(() => {
        zoomRaf = 0;
        invoke('plugin:x2dCamera|set_zoom', {
          zoom: pendingZoom,
          focusX: pendingFocusX,
          focusY: pendingFocusY,
        }).catch(() => {});
      });
    };

    const beginPinchIfReady = () => {
      if (pointers.size !== 2) return;
      const [a, b] = Array.from(pointers.values());
      pinchStartDistance = Math.hypot(b.x - a.x, b.y - a.y);
      pinchStartZoom = zoom;
    };

    const onPointerDown = (event: PointerEvent) => {
      if (event.pointerType !== 'touch') return;
      pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      beginPinchIfReady();
    };

    const onPointerMove = (event: PointerEvent) => {
      if (!pointers.has(event.pointerId)) return;
      pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (pointers.size !== 2 || pinchStartDistance <= 0) return;

      event.preventDefault();
      const [a, b] = Array.from(pointers.values());
      const distance = Math.hypot(b.x - a.x, b.y - a.y);
      if (distance <= 0) return;

      const rect = el.getBoundingClientRect();
      const midpointX = (a.x + b.x) / 2;
      const midpointY = (a.y + b.y) / 2;
      const focusX = rect.width > 0 ? (midpointX - rect.left) / rect.width : 0.5;
      const focusY = rect.height > 0 ? (midpointY - rect.top) / rect.height : 0.5;
      queueNativeZoom(
        pinchStartZoom * (distance / pinchStartDistance),
        focusX,
        focusY,
      );
    };

    const onPointerEnd = (event: PointerEvent) => {
      pointers.delete(event.pointerId);
      if (pointers.size < 2) {
        pinchStartDistance = 0;
        pinchStartZoom = zoom;
      } else {
        beginPinchIfReady();
      }
    };

    const previousTouchAction = el.style.touchAction;
    el.style.touchAction = 'pan-y';
    el.addEventListener('pointerdown', onPointerDown, { passive: false });
    el.addEventListener('pointermove', onPointerMove, { passive: false });
    el.addEventListener('pointerup', onPointerEnd, { passive: false });
    el.addEventListener('pointercancel', onPointerEnd, { passive: false });

    return () => {
      if (zoomRaf) cancelAnimationFrame(zoomRaf);
      el.style.touchAction = previousTouchAction;
      el.removeEventListener('pointerdown', onPointerDown);
      el.removeEventListener('pointermove', onPointerMove);
      el.removeEventListener('pointerup', onPointerEnd);
      el.removeEventListener('pointercancel', onPointerEnd);
    };
  }, [status?.dual_nozzle, cameraVisible]);
'''

d = replace_once(d, marker, marker + zoom_effect, "X2D camera effect")
dash_path.write_text(d)

print("X2D camera-only pinch zoom patch applied")
