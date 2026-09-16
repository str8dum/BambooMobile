from pathlib import Path
import base64


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# Rebuild the memorial photo from small text chunks kept in the repository.
parts = []
for i in range(4):
    p = Path(f'.github/silkie-memorial-{i}.b64')
    if not p.exists():
        raise SystemExit(f'Missing {p}')
    parts.append(p.read_text().strip())

public = Path('public')
public.mkdir(exist_ok=True)
(public / 'silkie-memorial.jpg').write_bytes(base64.b64decode(''.join(parts)))


# Make the Silkie branding in the settings/sidebar larger and tappable.
sidebar_path = Path('src/pages/Sidebar.tsx')
s = sidebar_path.read_text()

if "import { useState } from 'react';" not in s:
    s = "import { useState } from 'react';\n" + s

s = replace_once(
    s,
    "}) {\n  const model = activePrinter ? serialToModel(activePrinter.serial) : null;",
    "}) {\n  const [showSilkies, setShowSilkies] = useState(false);\n  const model = activePrinter ? serialToModel(activePrinter.serial) : null;",
    'sidebar memorial state',
)

s = s.replace(
    "<div className='flex items-center justify-between px-4 py-4 border-b border-cyan-400/15'>",
    "<div className='flex items-center justify-between px-3 py-[18px] border-b border-cyan-400/15'>",
    1,
)

old_icon = """            <img
              src='/scd-x2d-icon.png'
              alt='SCD X2D'
              className='h-14 w-14 shrink-0 rounded-2xl border border-cyan-300/30 shadow-[0_0_20px_rgba(34,211,238,0.22)]'
            />"""
new_icon = """            <button
              type='button'
              onClick={() => setShowSilkies(true)}
              aria-label='Open Silkie memorial photo'
              className='shrink-0 rounded-2xl transition active:scale-95'>
              <img
                src='/scd-x2d-icon.png'
                alt='SCD X2D'
                className='h-16 w-16 rounded-2xl border border-cyan-300/35 shadow-[0_0_24px_rgba(34,211,238,0.28)]'
              />
            </button>"""
s = replace_once(s, old_icon, new_icon, 'tappable larger Silkie icon')

s = s.replace(
    "<span className='text-lg font-extrabold tracking-[0.10em] text-slate-100'>SCD</span>",
    "<span className='text-xl font-extrabold tracking-[0.09em] text-slate-100'>SCD</span>",
    1,
)
s = s.replace(
    "<span className='text-2xl font-black tracking-tight text-cyan-300'>X2D</span>",
    "<span className='text-[28px] font-black tracking-tight text-cyan-300'>X2D</span>",
    1,
)
s = s.replace(
    "<div className='mt-1.5 text-[10px] font-semibold uppercase tracking-[0.17em] text-slate-500'>Printer Control</div>",
    "<div className='mt-1.5 text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500'>Printer Control</div>",
    1,
)

overlay = r'''

      {showSilkies && (
        <div
          className='fixed inset-0 z-[100] flex items-center justify-center bg-black/95 backdrop-blur-sm'
          style={{
            paddingTop: 'max(12px, env(safe-area-inset-top, 0px))',
            paddingRight: 'max(12px, env(safe-area-inset-right, 0px))',
            paddingBottom: 'max(12px, env(safe-area-inset-bottom, 0px))',
            paddingLeft: 'max(12px, env(safe-area-inset-left, 0px))',
          }}
          onClick={() => setShowSilkies(false)}>
          <button
            type='button'
            onClick={() => setShowSilkies(false)}
            aria-label='Close Silkie photo'
            className='absolute right-4 top-4 z-[101] flex h-12 w-12 items-center justify-center rounded-full border border-white/20 bg-black/65 text-white shadow-lg backdrop-blur active:scale-95'
            style={{
              top: 'max(16px, env(safe-area-inset-top, 0px))',
              right: 'max(16px, env(safe-area-inset-right, 0px))',
            }}>
            <svg className='h-7 w-7' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={2.25}>
              <path strokeLinecap='round' strokeLinejoin='round' d='M6 18L18 6M6 6l12 12' />
            </svg>
          </button>

          <img
            src='/silkie-memorial.jpg'
            alt='Silkie memorial'
            className='max-h-full max-w-full select-none rounded-2xl object-contain shadow-[0_24px_80px_rgba(0,0,0,0.65)]'
            style={{ touchAction: 'pinch-zoom' }}
            draggable={false}
            onClick={(event) => event.stopPropagation()}
          />
        </div>
      )}
'''

closing = "    </>\n  );\n}"
if closing not in s:
    raise SystemExit('Sidebar closing fragment marker not found')
s = s.replace(closing, overlay + "\n" + closing, 1)

sidebar_path.write_text(s)
print('Silkie memorial photo popup + larger sidebar branding applied')
