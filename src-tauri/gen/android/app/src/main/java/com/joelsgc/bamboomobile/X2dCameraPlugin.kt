@file:OptIn(androidx.media3.common.util.UnstableApi::class)

package com.joelsgc.bamboomobile

import android.app.Activity
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.TextureView
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.rtsp.RtspMediaSource
import app.tauri.annotation.Command
import app.tauri.annotation.TauriPlugin
import app.tauri.plugin.Invoke
import app.tauri.plugin.Plugin
import java.security.SecureRandom
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * Native X2D camera player.
 *
 * X2D exposes H.264 over RTSPS at:
 *   rtsps://bblp:<access-code>@<printer-ip>:322/streaming/live/1
 *
 * Media3's RTSP stack is supplied a trust-all SSLSocketFactory because Bambu
 * printers use a self-signed device certificate. RTP is forced over TCP so the
 * complete stream stays inside the TLS/RTSP connection and works reliably on
 * mobile LANs.
 *
 * The player renders into a TextureView layered directly over the WebView's
 * camera card. JavaScript sends the card bounds whenever it moves or resizes.
 */
@TauriPlugin
class X2dCameraPlugin(private val activity: Activity) : Plugin(activity) {
    companion object {
        private const val TAG = "X2dCamera"
        private const val RETRY_MS = 3000L
    }

    private val handler = Handler(Looper.getMainLooper())

    private var container: FrameLayout? = null
    private var textureView: TextureView? = null
    private var player: ExoPlayer? = null
    private var retryRunnable: Runnable? = null

    private var printerIp: String = ""
    private var accessCode: String = ""
    private var requestedVisible = false
    private var hasFirstFrame = false

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

            val samePrinter = printerIp == ip && accessCode == code && player != null
            printerIp = ip
            accessCode = code

            ensureView()
            updateBoundsNative(x, y, width, height, scale, visible)

            if (!samePrinter) {
                releasePlayerOnly()
                startPlayer()
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
        if (container != null && textureView != null) return

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
            visibility = View.INVISIBLE
            elevation = 100f
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                setColor(Color.BLACK)
                cornerRadius = 12f * density
            }
            clipToOutline = true
        }
        val texture = TextureView(activity).apply {
            isClickable = false
            isFocusable = false
        }
        box.addView(
            texture,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT,
            ),
        )
        root.addView(box, FrameLayout.LayoutParams(1, 1))

        container = box
        textureView = texture
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
        applyVisibility()
    }

    private fun applyVisibility() {
        container?.visibility = if (hasFirstFrame && requestedVisible) {
            View.VISIBLE
        } else {
            View.INVISIBLE
        }
    }

    @androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
    private fun startPlayer() {
        val texture = textureView ?: return
        if (printerIp.isBlank() || accessCode.isBlank()) return

        retryRunnable?.let(handler::removeCallbacks)
        retryRunnable = null
        hasFirstFrame = false
        applyVisibility()

        try {
            val trustAll = arrayOf<TrustManager>(object : X509TrustManager {
                override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
                override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
                override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            })
            val sslContext = SSLContext.getInstance("TLS")
            sslContext.init(null, trustAll, SecureRandom())

            val encodedCode = Uri.encode(accessCode)
            val url = "rtsps://bblp:$encodedCode@$printerIp:322/streaming/live/1"

            val p = ExoPlayer.Builder(activity).build()
            p.setVideoTextureView(texture)
            p.addListener(object : Player.Listener {
                override fun onRenderedFirstFrame() {
                    hasFirstFrame = true
                    applyVisibility()
                    Log.i(TAG, "X2D camera first frame rendered")
                }

                override fun onPlayerError(error: PlaybackException) {
                    Log.w(TAG, "X2D camera playback error: ${error.errorCodeName}")
                    hasFirstFrame = false
                    applyVisibility()
                    scheduleRetry()
                }

                override fun onPlaybackStateChanged(playbackState: Int) {
                    if (playbackState == Player.STATE_ENDED) {
                        scheduleRetry()
                    }
                }
            })

            val mediaSource = RtspMediaSource.Factory()
                .setSocketFactory(sslContext.socketFactory)
                .setForceUseRtpTcp(true)
                .createMediaSource(MediaItem.fromUri(url))

            p.setMediaSource(mediaSource)
            p.prepare()
            p.playWhenReady = true
            player = p
            Log.i(TAG, "Connecting X2D camera on RTSPS port 322")
        } catch (t: Throwable) {
            Log.w(TAG, "Unable to start X2D camera", t)
            scheduleRetry()
        }
    }

    private fun scheduleRetry() {
        if (container == null || printerIp.isBlank() || accessCode.isBlank()) return
        retryRunnable?.let(handler::removeCallbacks)
        val r = Runnable {
            retryRunnable = null
            if (container != null) {
                releasePlayerOnly()
                startPlayer()
            }
        }
        retryRunnable = r
        handler.postDelayed(r, RETRY_MS)
    }

    private fun releasePlayerOnly() {
        retryRunnable?.let(handler::removeCallbacks)
        retryRunnable = null
        player?.let { p ->
            try {
                textureView?.let { p.clearVideoTextureView(it) }
                p.release()
            } catch (_: Throwable) {
            }
        }
        player = null
        hasFirstFrame = false
        applyVisibility()
    }

    private fun stopInternal(removeView: Boolean) {
        releasePlayerOnly()
        requestedVisible = false
        if (removeView) {
            val box = container
            if (box != null) {
                (box.parent as? ViewGroup)?.removeView(box)
            }
            container = null
            textureView = null
        }
        printerIp = ""
        accessCode = ""
    }
}
