export default function DualNozzleGauge({
  label,
  actual,
  target,
  active,
}: {
  label: 'Left' | 'Right';
  actual: number;
  target: number;
  active: boolean;
}) {
  return (
    <div
      className={`rounded-xl border px-3 py-3 flex flex-col gap-1 transition-colors ${
        active
          ? 'border-teal-400/70 bg-teal-950/35'
          : 'border-zinc-700 bg-zinc-900/45'
      }`}>
      <div className='flex items-center justify-between gap-2'>
        <span className='text-zinc-400 text-xs font-semibold uppercase tracking-wide'>
          {label} nozzle
        </span>
        {active && (
          <span className='text-[10px] font-bold uppercase tracking-wider text-teal-300'>
            Active
          </span>
        )}
      </div>
      <div className='flex items-end justify-between gap-2'>
        <div>
          <span className='text-white text-2xl font-bold tabular-nums'>
            {Math.round(actual)}
          </span>
          <span className='text-zinc-400 text-sm'>°C</span>
        </div>
        <span className='text-zinc-500 text-xs tabular-nums pb-1'>
          → {Math.round(target)}°C
        </span>
      </div>
    </div>
  );
}
