package com.joelsgc.bamboomobile

import android.app.Activity
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import com.alexvas.rtsp.widget.RtspStatusListener
import com.alexvas.rtsp.widget.RtspSurfaceView
import app.tauri.annotation.Command
import app.tauri.annotation.TauriPlugin
import app.tauri.plugin.Invoke
import app.tauri.plugin.Plugin
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * Native X2D camera player.
 *
 * X2D exposes H.264 over secure RTSP at:
 *   rtsps://bblp:<access-code>@<printer-ip>:322/streaming/live/1
 *
 * Bambu's camera uses a self-signed TLS certificate and RTSPS-over-TCP. The
 * dedicated rtsp-client-android stack used here explicitly supports RTSPS,
 * Basic/Digest authentication, self-signed TLS, and H.264 MediaCodec rendering.
 *
 * The player renders into a native SurfaceView layered directly over the
 * WebView's camera card. JavaScript sends the card bounds whenever it moves or
 * resizes.
 */
@TauriPlugin
class X2dCameraPlugin(private val activity: Activity) : Plugin(activity) {
    companion object {
        private const val TAG = "X2dCamera"
        private const val FIRST_FRAME_TIMEOUT_MS = 12_000L
        private const val RETRY_INITIAL_MS = 3_000L
        private const val RETRY_MAX_MS = 30_000L
    }

    private val handler = Handler(Looper.getMainLooper())

    private var container: FrameLayout? = null
    private var rtspView: RtspSurfaceView? = null
    private var retryRunnable: Runnable? = null
    private var firstFrameWatchdog: Runnable? = null

    private var printerIp: String = ""
    private var accessCode: String = ""
    private var requestedVisible = false
    private var streamStarted = false
    private var hasFirstFrame = false
    private var retryDelayMs = RETRY_INITIAL_MS

    @Command
    fun showCamera(invoke: Invoke) {
        val args = invoke.getArgs()
        val ip = args.optString("ip", "").trim()
        val code = args.optString("accessCode", "").trim()
        val x = args.optDouble("x", 0.0)
        val y = args.optDouble("y", 0.0)
        val width = args.optDouble("width", 0.0)
        val height = args.optDouble("height", 0.0)
        val scale = args.optDouble("scale", 1.0).coerceAtLeast(0.1)
        val visible = args.optBoolean("visible", true)

        activity.runOnUiThread {
            if (ip.isBlank() || code.isBlank() || width <= 0.0 || height <= 0.0) {
                stopInternal(removeView = true)
                invoke.resolve()
                return@runOnUiThread
            }

            val samePrinter = printerIp == ip && accessCode == code && streamStarted
            printerIp = ip
            accessCode = code

            ensureView()
            updateBoundsNative(x, y, width, height, scale, visible)

            if (!samePrinter) {
                releaseStreamOnly()
                retryDelayMs = RETRY_INITIAL_MS
                startStream()
            }
            invoke.resolve()
        }
    }

    @Command
    fun updateBounds(invoke: Invoke) {
        val args = invoke.getArgs()
        val x = args.optDouble("x", 0.0)
        val y = args.optDouble("y", 0.0)
        val width = args.optDouble("width", 0.0)
        val height = args.optDouble("height", 0.0)
        val scale = args.optDouble("scale", 1.0).coerceAtLeast(0.1)
        val visible = args.optBoolean("visible", true)

        activity.runOnUiThread {
            updateBoundsNative(x, y, width, height, scale, visible)
            invoke.resolve()
        }
    }

    @Command
    fun hideCamera(invoke: Invoke) {
        activity.runOnUiThread {
            stopInternal(removeView = true)
            invoke.resolve()
        }
    }

    private fun ensureView() {
        if (container != null && rtspView != null) return

        val root = activity.findViewById<ViewGroup>(android.R.id.content) as? FrameLayout
        if (root == null) {
            Log.e(TAG, "android.R.id.content is not a FrameLayout")
            return
        }

        val density = activity.resources.displayMetrics.density
        val box = FrameLayout(activity).apply {
            isClickable = false
            isFocusable = false
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            visibility = View.VISIBLE
            elevation = 100f
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                setColor(Color.BLACK)
                cornerRadius = 12f * density
            }
            clipToOutline = true
        }

        val surface = RtspSurfaceView(activity).apply {
            isClickable = false
            isFocusable = false
            // Keep the hardware-decoded video above the Tauri WebView while the
            // parent FrameLayout constrains it to the camera-card bounds.
            setZOrderOnTop(true)
        }

        box.addView(
            surface,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT,
            ),
        )
        root.addView(box, FrameLayout.LayoutParams(1, 1))

        container = box
        rtspView = surface
    }

    private fun updateBoundsNative(
        x: Double,
        y: Double,
        width: Double,
        height: Double,
        scale: Double,
        visible: Boolean,
    ) {
        val box = container ?: return
        val lp = box.layoutParams as? FrameLayout.LayoutParams ?: return
        lp.width = max(1, (width * scale).roundToInt())
        lp.height = max(1, (height * scale).roundToInt())
        lp.leftMargin = (x * scale).roundToInt()
        lp.topMargin = (y * scale).roundToInt()
        box.layoutParams = lp
        requestedVisible = visible

        // Do not set a SurfaceView parent to INVISIBLE while streaming. Android
        // destroys its Surface in that state, which would stop the decoder. The
        // element is physically positioned with the web card and is removed when
        // the camera page/sidebar is no longer active.
        box.visibility = View.VISIBLE
    }

    private fun startStream() {
        val surface = rtspView ?: return
        if (printerIp.isBlank() || accessCode.isBlank()) return

        retryRunnable?.let(handler::removeCallbacks)
        retryRunnable = null
        cancelFirstFrameWatchdog()
        hasFirstFrame = false

        try {
            val uri = Uri.parse("rtsps://$printerIp:322/streaming/live/1")
            surface.setStatusListener(object : RtspStatusListener {
                override fun onRtspStatusConnecting() {
                    Log.i(TAG, "Connecting X2D camera on RTSPS port 322")
                }

                override fun onRtspStatusConnected() {
                    Log.i(TAG, "X2D RTSPS session connected")
                }

                override fun onRtspStatusDisconnecting() {
                    Log.i(TAG, "X2D RTSPS session disconnecting")
                }

                override fun onRtspStatusDisconnected() {
                    Log.w(TAG, "X2D RTSPS session disconnected")
                    hasFirstFrame = false
                    cancelFirstFrameWatchdog()
                    if (streamStarted) scheduleRetry()
                }

                override fun onRtspStatusFailedUnauthorized() {
                    Log.e(TAG, "X2D camera authentication failed")
                    hasFirstFrame = false
                    streamStarted = false
                    cancelFirstFrameWatchdog()
                    // The same LAN access code is used by MQTT, so repeated
                    // retries cannot fix an authentication failure.
                }

                override fun onRtspStatusFailed(message: String?) {
                    Log.w(TAG, "X2D RTSPS failure: ${message ?: "unknown error"}")
                    hasFirstFrame = false
                    cancelFirstFrameWatchdog()
                    if (streamStarted) scheduleRetry()
                }

                override fun onRtspFirstFrameRendered() {
                    hasFirstFrame = true
                    cancelFirstFrameWatchdog()
                    retryDelayMs = RETRY_INITIAL_MS
                    Log.i(TAG, "X2D camera first frame rendered; retry backoff reset")
                }
            })

            // Keep credentials separate from the URI so special characters in
            // the LAN access code cannot corrupt URL parsing.
            surface.init(
                uri = uri,
                username = "bblp",
                password = accessCode,
                userAgent = "BambooMobile-X2D",
            )

            // Mark the attempt active before start() so asynchronous failure
            // callbacks can schedule a retry immediately.
            streamStarted = true
            surface.start(
                requestVideo = true,
                requestAudio = false,
                requestApplication = false,
            )
            armFirstFrameWatchdog()
        } catch (t: Throwable) {
            Log.w(TAG, "Unable to start X2D RTSPS camera", t)
            streamStarted = false
            cancelFirstFrameWatchdog()
            scheduleRetry()
        }
    }

    private fun armFirstFrameWatchdog() {
        cancelFirstFrameWatchdog()
        if (!streamStarted || hasFirstFrame || container == null) return

        val watchdog = Runnable {
            firstFrameWatchdog = null
            if (container != null && streamStarted && !hasFirstFrame) {
                Log.w(TAG, "No X2D camera frame within ${FIRST_FRAME_TIMEOUT_MS}ms; restarting stream")
                releaseStreamOnly()
                startStream()
            }
        }
        firstFrameWatchdog = watchdog
        handler.postDelayed(watchdog, FIRST_FRAME_TIMEOUT_MS)
    }

    private fun cancelFirstFrameWatchdog() {
        firstFrameWatchdog?.let(handler::removeCallbacks)
        firstFrameWatchdog = null
    }

    private fun scheduleRetry() {
        if (container == null || printerIp.isBlank() || accessCode.isBlank()) return
        if (retryRunnable != null) return

        cancelFirstFrameWatchdog()
        val delay = retryDelayMs
        retryDelayMs = when {
            retryDelayMs < 5_000L -> 5_000L
            retryDelayMs < 10_000L -> 10_000L
            retryDelayMs < 20_000L -> 20_000L
            else -> RETRY_MAX_MS
        }

        Log.i(TAG, "Scheduling X2D camera retry in ${delay}ms")
        val r = Runnable {
            retryRunnable = null
            if (container != null) {
                releaseStreamOnly()
                startStream()
            }
        }
        retryRunnable = r
        handler.postDelayed(r, delay)
    }

    private fun releaseStreamOnly() {
        retryRunnable?.let(handler::removeCallbacks)
        retryRunnable = null
        cancelFirstFrameWatchdog()
        try {
            rtspView?.stop()
            rtspView?.setStatusListener(null)
        } catch (_: Throwable) {
        }
        streamStarted = false
        hasFirstFrame = false
    }

    private fun stopInternal(removeView: Boolean) {
        releaseStreamOnly()
        retryDelayMs = RETRY_INITIAL_MS
        requestedVisible = false
        if (removeView) {
            val box = container
            if (box != null) {
                (box.parent as? ViewGroup)?.removeView(box)
            }
            container = null
            rtspView = null
        }
        printerIp = ""
        accessCode = ""
    }
}
