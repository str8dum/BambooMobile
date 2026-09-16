from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# The X2D video is a native Android SurfaceView layered above the Tauri WebView.
# Keep the browser-side gesture bridge as a fallback for non-native targets, but
# the Android plugin below owns the real camera pinch/pan interaction.
dash_path = Path("src/pages/Dashboard.tsx")
d = dash_path.read_text()

if "plugin:x2dCamera|set_zoom" not in d:
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
    print("X2D camera-only browser zoom bridge applied")
else:
    print("X2D camera-only browser zoom bridge already applied")


# Native Android gesture handling. Zoom must stay visually clipped to the camera
# card and, once zoomed, a single finger should pan around the magnified frame.
plugin_path = Path(
    "src-tauri/gen/android/app/src/main/java/com/joelsgc/bamboomobile/X2dCameraPlugin.kt"
)
k = plugin_path.read_text()

if "private var videoPanX" not in k:
    k = replace_once(
        k,
        "import android.graphics.Color\n",
        "import android.graphics.Color\nimport android.graphics.Rect\n",
        "Rect import",
    )

    k = replace_once(
        k,
        '''    private var videoZoom = ZOOM_MIN
    private var zoomFocusX = 0.5f
    private var zoomFocusY = 0.5f
''',
        '''    private var videoZoom = ZOOM_MIN
    private var videoPanX = 0.0f
    private var videoPanY = 0.0f
    private var lastPanX = 0.0f
    private var lastPanY = 0.0f
''',
        "native zoom state",
    )

    old_set_zoom = r'''    @Command
    fun setZoom(invoke: Invoke) {
        val args = invoke.getArgs()
        val requestedZoom = args.optDouble("zoom", ZOOM_MIN.toDouble())
        val requestedFocusX = args.optDouble("focusX", 0.5)
        val requestedFocusY = args.optDouble("focusY", 0.5)
        activity.runOnUiThread {
            videoZoom = if (requestedZoom.isFinite()) requestedZoom.toFloat().coerceIn(ZOOM_MIN, ZOOM_MAX) else ZOOM_MIN
            zoomFocusX = if (requestedFocusX.isFinite()) requestedFocusX.toFloat().coerceIn(0.0f, 1.0f) else 0.5f
            zoomFocusY = if (requestedFocusY.isFinite()) requestedFocusY.toFloat().coerceIn(0.0f, 1.0f) else 0.5f
            applyVideoZoom()
            invoke.resolve()
        }
    }
'''
    new_set_zoom = r'''    @Command
    fun setZoom(invoke: Invoke) {
        val args = invoke.getArgs()
        val requestedZoom = args.optDouble("zoom", ZOOM_MIN.toDouble())
        val requestedFocusX = args.optDouble("focusX", 0.5)
        val requestedFocusY = args.optDouble("focusY", 0.5)
        activity.runOnUiThread {
            val surface = rtspView
            val oldZoom = videoZoom
            val nextZoom = if (requestedZoom.isFinite()) {
                requestedZoom.toFloat().coerceIn(ZOOM_MIN, ZOOM_MAX)
            } else {
                ZOOM_MIN
            }
            if (surface != null && surface.width > 0 && surface.height > 0) {
                val focusX = if (requestedFocusX.isFinite()) requestedFocusX.toFloat().coerceIn(0.0f, 1.0f) else 0.5f
                val focusY = if (requestedFocusY.isFinite()) requestedFocusY.toFloat().coerceIn(0.0f, 1.0f) else 0.5f
                val fx = focusX * surface.width.toFloat() - surface.width.toFloat() / 2.0f
                val fy = focusY * surface.height.toFloat() - surface.height.toFloat() / 2.0f
                videoPanX += fx * (oldZoom - nextZoom)
                videoPanY += fy * (oldZoom - nextZoom)
            }
            videoZoom = nextZoom
            if (videoZoom <= ZOOM_MIN + 0.001f) {
                videoPanX = 0.0f
                videoPanY = 0.0f
            }
            clampVideoPan()
            applyVideoZoom()
            invoke.resolve()
        }
    }
'''
    k = replace_once(k, old_set_zoom, new_set_zoom, "native setZoom")

    old_detector = r'''        val detector = ScaleGestureDetector(activity, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
            override fun onScaleBegin(detector: ScaleGestureDetector): Boolean = true
            override fun onScale(detector: ScaleGestureDetector): Boolean {
                val w = box.width.toFloat().coerceAtLeast(1f)
                val h = box.height.toFloat().coerceAtLeast(1f)
                videoZoom = (videoZoom * detector.scaleFactor).coerceIn(ZOOM_MIN, ZOOM_MAX)
                zoomFocusX = (detector.focusX / w).coerceIn(0f, 1f)
                zoomFocusY = (detector.focusY / h).coerceIn(0f, 1f)
                applyVideoZoom()
                return true
            }
        })
        scaleDetector = detector
        box.setOnTouchListener { _, event ->
            detector.onTouchEvent(event)
            // The native camera overlay owns multi-touch. Consuming the gesture here
            // is what makes pinch reliable instead of expecting the WebView underneath
            // the SurfaceView to receive the same pointers.
            event.pointerCount > 1 || detector.isInProgress || event.actionMasked == MotionEvent.ACTION_UP
        }
'''
    new_detector = r'''        val detector = ScaleGestureDetector(activity, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
            override fun onScaleBegin(detector: ScaleGestureDetector): Boolean = true
            override fun onScale(detector: ScaleGestureDetector): Boolean {
                val w = box.width.toFloat().coerceAtLeast(1f)
                val h = box.height.toFloat().coerceAtLeast(1f)
                val oldZoom = videoZoom
                val nextZoom = (videoZoom * detector.scaleFactor).coerceIn(ZOOM_MIN, ZOOM_MAX)

                // Keep the point under the user's fingers stationary while the zoom
                // changes, then clamp so dragging can never reveal empty space.
                val fx = detector.focusX - w / 2.0f
                val fy = detector.focusY - h / 2.0f
                videoPanX += fx * (oldZoom - nextZoom)
                videoPanY += fy * (oldZoom - nextZoom)
                videoZoom = nextZoom
                if (videoZoom <= ZOOM_MIN + 0.001f) {
                    videoPanX = 0.0f
                    videoPanY = 0.0f
                }
                clampVideoPan()
                applyVideoZoom()
                return true
            }
        })
        scaleDetector = detector
        box.setOnTouchListener { _, event ->
            detector.onTouchEvent(event)
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    lastPanX = event.x
                    lastPanY = event.y
                    true
                }
                MotionEvent.ACTION_POINTER_DOWN -> true
                MotionEvent.ACTION_MOVE -> {
                    if (!detector.isInProgress && event.pointerCount == 1 && videoZoom > ZOOM_MIN + 0.001f) {
                        val x = event.x
                        val y = event.y
                        videoPanX += x - lastPanX
                        videoPanY += y - lastPanY
                        clampVideoPan()
                        applyVideoZoom()
                        lastPanX = x
                        lastPanY = y
                    }
                    true
                }
                MotionEvent.ACTION_POINTER_UP -> {
                    // Seed the next one-finger drag from the pointer that remains.
                    if (event.pointerCount > 1) {
                        val remaining = if (event.actionIndex == 0) 1 else 0
                        lastPanX = event.getX(remaining)
                        lastPanY = event.getY(remaining)
                    }
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> true
                else -> true
            }
        }
'''
    k = replace_once(k, old_detector, new_detector, "native pinch/pan listener")

    old_apply = r'''    private fun applyVideoZoom() {
        val surface = rtspView ?: return
        if (surface.width <= 0 || surface.height <= 0) return
        surface.pivotX = surface.width.toFloat() * zoomFocusX
        surface.pivotY = surface.height.toFloat() * zoomFocusY
        surface.scaleX = videoZoom
        surface.scaleY = videoZoom
    }
'''
    new_apply = r'''    private fun clampVideoPan() {
        val surface = rtspView ?: return
        if (surface.width <= 0 || surface.height <= 0) return
        val maxX = surface.width.toFloat() * (videoZoom - 1.0f) / 2.0f
        val maxY = surface.height.toFloat() * (videoZoom - 1.0f) / 2.0f
        videoPanX = videoPanX.coerceIn(-maxX, maxX)
        videoPanY = videoPanY.coerceIn(-maxY, maxY)
    }

    private fun applyVideoZoom() {
        val surface = rtspView ?: return
        if (surface.width <= 0 || surface.height <= 0) return

        clampVideoPan()
        val w = surface.width.toFloat()
        val h = surface.height.toFloat()
        val scale = videoZoom.coerceAtLeast(ZOOM_MIN)
        val cx = w / 2.0f
        val cy = h / 2.0f

        surface.pivotX = cx
        surface.pivotY = cy
        surface.scaleX = scale
        surface.scaleY = scale
        surface.translationX = videoPanX
        surface.translationY = videoPanY

        // SurfaceView uses a separate Android surface because it sits above the
        // WebView. Parent overflow clipping alone therefore is not sufficient on
        // every Android version. Clip the SurfaceView itself to the inverse-mapped
        // camera viewport so zoom never paints over the controls/status cards.
        val left = (cx + (0.0f - cx - videoPanX) / scale).coerceIn(0.0f, w)
        val top = (cy + (0.0f - cy - videoPanY) / scale).coerceIn(0.0f, h)
        val right = (cx + (w - cx - videoPanX) / scale).coerceIn(0.0f, w)
        val bottom = (cy + (h - cy - videoPanY) / scale).coerceIn(0.0f, h)
        surface.clipBounds = Rect(
            left.roundToInt(),
            top.roundToInt(),
            right.roundToInt().coerceAtLeast(left.roundToInt() + 1),
            bottom.roundToInt().coerceAtLeast(top.roundToInt() + 1),
        )
    }
'''
    k = replace_once(k, old_apply, new_apply, "native clipped zoom transform")

    k = replace_once(
        k,
        '''        videoZoom = ZOOM_MIN
        zoomFocusX = 0.5f
        zoomFocusY = 0.5f
        scaleDetector = null
''',
        '''        videoZoom = ZOOM_MIN
        videoPanX = 0.0f
        videoPanY = 0.0f
        lastPanX = 0.0f
        lastPanY = 0.0f
        scaleDetector = null
''',
        "native zoom reset",
    )

    plugin_path.write_text(k)
    print("X2D native clipped pinch zoom + one-finger pan applied")
else:
    print("X2D native clipped pinch zoom + one-finger pan already applied")
