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
      className={`min-w-0 rounded-xl border px-3 py-3 flex flex-col gap-2 transition-colors ${
        active
          ? 'border-cyan-400/70 bg-cyan-950/30 shadow-[0_0_18px_rgba(34,211,238,0.08)]'
          : 'border-zinc-700 bg-zinc-900/45'
      }`}>
      <div className='flex min-w-0 flex-col items-start gap-1.5'>
        <span className='text-zinc-400 text-xs font-semibold uppercase tracking-wide leading-tight'>
          {label} nozzle
        </span>
        {active && (
          <span className='inline-flex self-start rounded-full border border-cyan-300/30 bg-cyan-400/10 px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.14em] text-cyan-300'>
            Active
          </span>
        )}
      </div>
      <div className='flex min-w-0 items-end justify-between gap-2'>
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
    </div>
  );
}
