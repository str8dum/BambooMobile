from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# Remove the old speed gauge from the Printer section. Print speed is already
# available in the Current Print card, so this duplicate control wastes space.
dash_path = Path('src/pages/Dashboard.tsx')
d = dash_path.read_text()
d = d.replace("import SpeedGauge from '../components/SpeedGauge';\n", '', 1)

speed_block = """                  <SpeedGauge
                    level={speedLevel}
                    onSet={setSpeed}
                    icon={
                      <svg
                        xmlns='http://www.w3.org/2000/svg'
                        width='32'
                        height='32'
                        viewBox='0 0 24 24'
                        fill='none'
                        stroke='currentColor'
                        strokeWidth='2'
                        strokeLinecap='round'
                        strokeLinejoin='round'>
                        <path d='m12 14 4-4' />
                        <path d='M3.34 19a10 10 0 1 1 17.32 0' />
                      </svg>
                    }
                  />
"""
d = replace_once(d, speed_block, '', 'bottom SpeedGauge block')

# After the responsive Pixel patch this row is still allowed to expand to three
# columns on wider phones. With only nozzle + bed left, lock it to two columns.
d = d.replace(
    "className='grid grid-cols-2 min-[440px]:grid-cols-3 w-full gap-2.5'",
    "className='grid grid-cols-2 w-full gap-2.5'",
    1,
)
dash_path.write_text(d)


# The X2D left/right nozzle cards were placing the target temperature on the same
# line as the large current temperature. At 255C this could overlap. Stack the
# target underneath so both values remain readable at every phone width.
gauge_path = Path('src/components/DualNozzleGauge.tsx')
g = gauge_path.read_text()
old = """      <div className='flex min-w-0 items-end justify-between gap-2'>
        <div className='min-w-0 whitespace-nowrap'>
          <span className='text-white text-2xl font-bold tabular-nums'>
            {Math.round(actual)}
          </span>
          <span className='text-zinc-400 text-sm'>°C</span>
        </div>
        <span className='shrink-0 text-zinc-500 text-xs tabular-nums pb-1'>
          → {Math.round(target)}°C
        </span>
      </div>
"""
new = """      <div className='flex min-w-0 flex-col gap-1'>
        <div className='min-w-0 whitespace-nowrap leading-none'>
          <span className='text-white text-[28px] font-bold tabular-nums'>
            {Math.round(actual)}
          </span>
          <span className='ml-0.5 text-zinc-400 text-sm'>°C</span>
        </div>
        <span className='text-cyan-400/60 text-[11px] tabular-nums leading-none'>
          → {Math.round(target)}°C
        </span>
      </div>
"""
g = replace_once(g, old, new, 'dual nozzle temperature layout')
gauge_path.write_text(g)

print('Printer panel cleanup applied: removed duplicate speed gauge and fixed dual-nozzle temperature overlap')
