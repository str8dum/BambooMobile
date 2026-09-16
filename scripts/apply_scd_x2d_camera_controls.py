from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


path = Path('src/pages/Dashboard.tsx')
d = path.read_text()

# Dedicated camera fullscreen state. The native X2D SurfaceView follows the
# cameraRef bounds through the existing ResizeObserver, so resizing this card
# also resizes the real H.264 video rather than only the WebView underneath it.
d = replace_once(
    d,
    "  const [filamentBusy, setFilamentBusy] = useState(false);\n",
    "  const [filamentBusy, setFilamentBusy] = useState(false);\n  const [cameraFullscreen, setCameraFullscreen] = useState(false);\n",
    'camera fullscreen state',
)

# Prevent the dashboard behind the fullscreen camera from scrolling. Restore
# the previous setting exactly when fullscreen closes or Dashboard unmounts.
d = replace_once(
    d,
    "  serialRef.current = serial;\n",
    """  serialRef.current = serial;\n\n  useEffect(() => {\n    if (!cameraFullscreen) return;\n    const previousOverflow = document.body.style.overflow;\n    document.body.style.overflow = 'hidden';\n    return () => {\n      document.body.style.overflow = previousOverflow;\n    };\n  }, [cameraFullscreen]);\n""",
    'fullscreen body lock',
)

start = "          <div ref={cameraRef} className='rounded-2xl overflow-hidden bg-[#07111d] border border-cyan-400/20 aspect-video flex items-center justify-center shrink-0 shadow-[0_10px_30px_rgba(0,0,0,0.30),0_0_18px_rgba(34,211,238,0.04)]'>"
end = "\n\n          {status && (\n            <PrintStatusCard"
start_i = d.find(start)
end_i = d.find(end, start_i)
if start_i < 0 or end_i < 0:
    raise SystemExit('branded camera card markers not found')

camera = r'''          <div
            className={cameraFullscreen
              ? 'fixed inset-0 z-40 flex flex-col bg-black'
              : 'overflow-hidden rounded-2xl border border-cyan-400/20 bg-[#07111d] shadow-[0_10px_30px_rgba(0,0,0,0.30),0_0_18px_rgba(34,211,238,0.04)]'}>
            <div
              ref={cameraRef}
              className={cameraFullscreen
                ? 'min-h-0 flex-1 bg-black flex items-center justify-center'
                : 'aspect-video flex items-center justify-center bg-[#07111d]'}>
              {frameData ?
                <img
                  src={frameData}
                  className='w-full h-full object-cover'
                  alt='Live camera'
                />
              : <div className='flex flex-col items-center gap-2 text-center px-6'>
                  <span className='text-3xl'>📷</span>
                  <p className='text-slate-400 text-sm font-medium'>
                    Connecting to camera…
                  </p>
                  <p className='text-slate-600 text-xs'>
                    {status?.dual_nozzle ?
                      status.camera_rtsp_enabled ? 'X2D secure H.264 stream · port 322' : 'Enable LAN Only Liveview on the X2D'
                    : 'Waiting for stream on port 6000'}
                  </p>
                </div>
              }
            </div>

            <div
              className={`grid grid-cols-2 gap-2 border-t border-cyan-400/15 bg-[#07111d] p-2.5 ${cameraFullscreen ? 'shrink-0 pb-[calc(env(safe-area-inset-bottom,0px)+0.625rem)]' : ''}`}>
              <button
                onClick={toggleLight}
                className={`flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-semibold transition ${lightOn ? 'border-cyan-300/40 bg-cyan-400/15 text-cyan-200' : 'border-slate-700 bg-slate-950/70 text-slate-300'}`}>
                <span className={`h-2.5 w-2.5 rounded-full ${lightOn ? 'bg-cyan-300 shadow-[0_0_10px_rgba(103,232,249,0.8)]' : 'bg-slate-600'}`} />
                {lightOn ? 'Light On' : 'Light Off'}
              </button>
              <button
                onClick={() => setCameraFullscreen((value) => !value)}
                className='flex items-center justify-center gap-2 rounded-xl border border-cyan-400/25 bg-slate-950/70 px-3 py-2.5 text-sm font-semibold text-cyan-300'>
                <svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round'>
                  {cameraFullscreen ? (
                    <>
                      <path d='M8 3v5H3' />
                      <path d='M16 3v5h5' />
                      <path d='M8 21v-5H3' />
                      <path d='M16 21v-5h5' />
                    </>
                  ) : (
                    <>
                      <path d='M8 3H3v5' />
                      <path d='M16 3h5v5' />
                      <path d='M8 21H3v-5' />
                      <path d='M16 21h5v-5' />
                    </>
                  )}
                </svg>
                {cameraFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
              </button>
            </div>
          </div>'''

d = d[:start_i] + camera + d[end_i:]
path.write_text(d)
print('SCD X2D camera fullscreen + light controls applied')
