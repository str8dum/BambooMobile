from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# Pixel-class portrait layout: design against Android/CSS pixels and the tall
# 20:9 viewport rather than hard-coding the phone's physical 2856x1280 pixels.
dash_path = Path('src/pages/Dashboard.tsx')
d = dash_path.read_text()

d = replace_once(
    d,
    "<div className='flex flex-col gap-3 p-4 pb-8'>",
    "<div className='mx-auto flex w-full max-w-[520px] flex-col gap-3 px-3 py-3 pb-[calc(env(safe-area-inset-bottom,0px)+1.25rem)] min-[430px]:px-4'>",
    'responsive dashboard content width',
)

# The legacy printer row uses three columns. Two columns are much more readable
# on ~400 CSS-pixel portrait screens; wider phones/tablets return to three.
d = d.replace(
    "className='grid grid-cols-3 w-full gap-3'",
    "className='grid grid-cols-2 min-[440px]:grid-cols-3 w-full gap-2.5'",
)

# Fullscreen video preserves a 16:9 camera image. CSS below uses a bottom control
# strip in portrait and a narrow side strip in landscape, which makes much better
# use of a 20:9 Pixel display without stretching the X2D video.
d = replace_once(
    d,
    "? 'fixed inset-0 z-40 flex flex-col bg-black'",
    "? 'scd-camera-fullscreen fixed inset-0 z-40 flex min-h-0 bg-black'",
    'fullscreen camera wrapper',
)
d = replace_once(
    d,
    "? 'min-h-0 flex-1 bg-black flex items-center justify-center'",
    "? 'scd-camera-fullscreen-video min-h-0 bg-black flex items-center justify-center'",
    'fullscreen camera video area',
)
d = replace_once(
    d,
    "className={`grid grid-cols-2 gap-2 border-t border-cyan-400/15 bg-[#07111d] p-2.5 ${cameraFullscreen ? 'shrink-0 pb-[calc(env(safe-area-inset-bottom,0px)+0.625rem)]' : ''}`}",
    "className={`grid grid-cols-2 gap-2 border-t border-cyan-400/15 bg-[#07111d] p-2.5 ${cameraFullscreen ? 'scd-camera-fullscreen-controls shrink-0 pb-[calc(env(safe-area-inset-bottom,0px)+0.625rem)]' : ''}`}",
    'fullscreen camera controls',
)
dash_path.write_text(d)


# Tighten the print card for a narrow portrait viewport without hiding any of
# the four key metrics. It remains a 2x2 grid: progress, layers, remaining, finish.
card_path = Path('src/components/PrintStatusCard.tsx')
pc = card_path.read_text()
pc = replace_once(
    pc,
    "<div className='flex min-w-0 items-start justify-between gap-3'>",
    "<div className='flex min-w-0 flex-wrap items-start justify-between gap-2'>",
    'print card heading wrap',
)
pc = replace_once(
    pc,
    "<div className='flex flex-col gap-3 p-3.5'>",
    "<div className='flex flex-col gap-3 p-3 min-[430px]:p-3.5'>",
    'print card responsive padding',
)
pc = replace_once(
    pc,
    "className={`grid min-w-0 gap-3 ${printPreview ? 'grid-cols-[88px_minmax(0,1fr)]' : 'grid-cols-1'}`}",
    "className={`grid min-w-0 gap-2.5 ${printPreview ? 'grid-cols-[76px_minmax(0,1fr)] min-[390px]:grid-cols-[88px_minmax(0,1fr)]' : 'grid-cols-1'}`}",
    'print preview responsive columns',
)
pc = replace_once(
    pc,
    "<div className='h-[88px] w-[88px] overflow-hidden rounded-xl border border-cyan-400/15 bg-slate-950/70'>",
    "<div className='h-[76px] w-[76px] overflow-hidden rounded-xl border border-cyan-400/15 bg-slate-950/70 min-[390px]:h-[88px] min-[390px]:w-[88px]'>",
    'print preview responsive size',
)
pc = replace_once(
    pc,
    "<div className='min-w-0 rounded-xl border border-cyan-400/10 bg-slate-950/55 px-3 py-2.5'>",
    "<div className='min-w-0 rounded-xl border border-cyan-400/10 bg-slate-950/55 px-2.5 py-2 min-[430px]:px-3 min-[430px]:py-2.5'>",
    'metric responsive padding',
)
pc = replace_once(
    pc,
    "className={`mt-1 truncate text-base font-bold tabular-nums ${accent ? 'text-cyan-300' : 'text-slate-100'}`}",
    "className={`mt-1 truncate text-sm font-bold tabular-nums min-[390px]:text-base ${accent ? 'text-cyan-300' : 'text-slate-100'}`}",
    'metric responsive text',
)
card_path.write_text(pc)


# Orientation-aware fullscreen sizing. The controls stay outside the native
# SurfaceView so Android's on-top camera layer never blocks the exit/light buttons.
css_path = Path('src/App.css')
css = css_path.read_text()
marker = '/* SCD X2D Pixel/20:9 responsive layout */'
if marker not in css:
    css += r'''

/* SCD X2D Pixel/20:9 responsive layout */
.scd-camera-fullscreen {
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.scd-camera-fullscreen-video {
  flex: 0 0 auto;
  width: min(100vw, calc((100dvh - 62px) * 16 / 9));
  height: min(calc(100dvh - 62px), calc(100vw * 9 / 16));
  margin: auto;
  aspect-ratio: 16 / 9;
}

.scd-camera-fullscreen-controls {
  width: 100%;
  flex: 0 0 auto;
}

@media (orientation: landscape) {
  .scd-camera-fullscreen {
    flex-direction: row;
  }

  .scd-camera-fullscreen-video {
    width: min(calc(100vw - 128px), calc(100dvh * 16 / 9));
    height: min(100dvh, calc((100vw - 128px) * 9 / 16));
    margin: auto;
  }

  .scd-camera-fullscreen-controls {
    width: 128px;
    height: 100dvh;
    grid-template-columns: minmax(0, 1fr) !important;
    align-content: center;
    border-top: 0 !important;
    border-left: 1px solid rgba(34, 211, 238, 0.15);
    padding-top: max(0.625rem, env(safe-area-inset-top, 0px));
    padding-right: max(0.5rem, env(safe-area-inset-right, 0px));
    padding-bottom: max(0.625rem, env(safe-area-inset-bottom, 0px));
    padding-left: 0.5rem;
  }

  .scd-camera-fullscreen-controls button {
    min-height: 72px;
    flex-direction: column;
    gap: 0.35rem;
    padding-left: 0.35rem;
    padding-right: 0.35rem;
    font-size: 0.75rem;
    line-height: 1rem;
  }
}
'''
css_path.write_text(css)

# Keep the browser/WebView title consistent with the installed SCD X2D name.
index_path = Path('index.html')
index = index_path.read_text()
index = index.replace('<title>BambooMobile</title>', '<title>SCD X2D</title>')
index_path.write_text(index)

print('SCD X2D Pixel 20:9 responsive layout applied')
