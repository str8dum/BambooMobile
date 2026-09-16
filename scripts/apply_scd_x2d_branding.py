from pathlib import Path
import base64
import json
import re


ROOT = Path('.')


CARD = r'''import type { PrinterStatus } from '../vite-env';
import { gcodeLabel } from '../utils/printer';

function formatRemaining(minutes: number) {
  if (!minutes || minutes <= 0) return '—';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h > 0 && m > 0) return `${h}h ${m}m`;
  if (h > 0) return `${h}h`;
  return `${m}m`;
}

function finishAt(minutes: number) {
  if (!minutes || minutes <= 0) return '—';
  const when = new Date(Date.now() + minutes * 60_000);
  return when.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function ProgressBar({ percent }: { percent: number }) {
  const bounded = Math.max(0, Math.min(100, percent || 0));
  return (
    <div className='h-2.5 w-full overflow-hidden rounded-full bg-slate-800 ring-1 ring-white/5'>
      <div
        className='h-full rounded-full bg-gradient-to-r from-cyan-500 via-sky-400 to-blue-500 transition-all duration-500 shadow-[0_0_14px_rgba(34,211,238,0.45)]'
        style={{ width: `${bounded}%` }}
      />
    </div>
  );
}

function Metric({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className='min-w-0 rounded-xl border border-cyan-400/10 bg-slate-950/55 px-3 py-2.5'>
      <div className='text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500'>{label}</div>
      <div className={`mt-1 truncate text-base font-bold tabular-nums ${accent ? 'text-cyan-300' : 'text-slate-100'}`}>
        {value}
      </div>
    </div>
  );
}

export default function PrintStatusCard({
  status,
  printPreview,
  onCommand,
  onSkipObject,
  lightOn,
  toggleLight,
}: {
  status: PrinterStatus;
  printPreview: string | null;
  onCommand: (cmd: string) => void;
  onSkipObject: (objectId: number) => Promise<void>;
  lightOn: boolean;
  toggleLight: () => void;
}) {
  const { text: stateLabel, dot: stateDot } = gcodeLabel(status.gcode_state);
  const isPrinting = status.gcode_state === 'RUNNING';
  const isPaused = status.gcode_state === 'PAUSE';
  const isActive = isPrinting || isPaused;
  const isFinished = status.gcode_state === 'FINISH';
  const isFailed = status.gcode_state === 'FAILED';
  const name = status.subtask_name || 'No active print';
  const fileSize =
    name.length > 72 ? 'text-[11px]' :
    name.length > 52 ? 'text-xs' :
    name.length > 34 ? 'text-sm' : 'text-[15px]';
  const layers = status.total_layer_num > 0
    ? `${status.layer_num} / ${status.total_layer_num}`
    : '— / —';

  async function skipObject() {
    const raw = window.prompt('Object ID to skip (from the slicer object list):');
    if (raw === null) return;
    const objectId = Number(raw.trim());
    if (!Number.isInteger(objectId) || objectId < 0) {
      window.alert('Enter a valid numeric object ID.');
      return;
    }
    if ((status.skipped_objects ?? []).includes(objectId)) {
      window.alert(`Object ${objectId} is already skipped.`);
      return;
    }
    if (!window.confirm(`Skip object ${objectId}? The X2D will finish the current layer before the skip takes effect.`)) return;
    try {
      await onSkipObject(objectId);
      window.alert('Skip queued. It will take effect after the current layer.');
    } catch (e) {
      window.alert(`Could not queue skip: ${String(e)}`);
    }
  }

  return (
    <div className='overflow-hidden rounded-2xl border border-cyan-400/20 bg-[#091523] shadow-[0_12px_36px_rgba(0,0,0,0.30),0_0_24px_rgba(34,211,238,0.05)]'>
      <div className='h-1 bg-gradient-to-r from-cyan-500 via-sky-400 to-blue-600' />
      <div className='flex flex-col gap-3 p-3.5'>
        <div className='flex min-w-0 items-start justify-between gap-3'>
          <div className='min-w-0 flex-1'>
            <div className='mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-400/70'>Current Print</div>
            <div
              className={`${fileSize} max-w-full font-semibold leading-tight text-slate-100`}
              style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
              {name}
            </div>
          </div>
          <div className='flex shrink-0 items-center gap-1.5 rounded-full border border-cyan-400/15 bg-slate-950/60 px-2.5 py-1.5'>
            <span className={`h-2 w-2 rounded-full ${stateDot}`} />
            <span className='text-[11px] font-semibold text-slate-300'>{stateLabel}</span>
          </div>
        </div>

        {(isActive || isFinished || isFailed) && (
          <div className={`grid min-w-0 gap-3 ${printPreview ? 'grid-cols-[88px_minmax(0,1fr)]' : 'grid-cols-1'}`}>
            {printPreview && (
              <div className='h-[88px] w-[88px] overflow-hidden rounded-xl border border-cyan-400/15 bg-slate-950/70'>
                <img src={printPreview} className='h-full w-full object-cover' alt='Print preview' />
              </div>
            )}
            <div className='grid min-w-0 grid-cols-2 gap-2'>
              <Metric label='Progress' value={`${status.progress || 0}%`} accent />
              <Metric label='Layers' value={layers} />
              <Metric label='Remaining' value={formatRemaining(status.remaining_mins)} />
              <Metric label='Finish' value={finishAt(status.remaining_mins)} accent />
            </div>
          </div>
        )}

        {isActive && (
          <div className='flex flex-col gap-2'>
            <div className='flex items-center justify-between text-[11px] text-slate-500'>
              <span>{status.stage && status.stage !== 'Idle' ? status.stage : 'Printing'}</span>
              <span className='font-semibold text-cyan-300'>{status.progress || 0}%</span>
            </div>
            <ProgressBar percent={status.progress} />
          </div>
        )}

        {!isActive && !isFinished && !isFailed && status.stage && status.stage !== 'Idle' && (
          <div className='rounded-xl border border-cyan-400/10 bg-slate-950/45 px-3 py-2 text-sm text-slate-400'>
            {status.stage}
          </div>
        )}

        {(status.skipped_objects ?? []).length > 0 && (
          <div className='text-[11px] text-amber-300/80'>Skipped objects: {status.skipped_objects.join(', ')}</div>
        )}

        <div className='grid grid-cols-2 gap-2 border-t border-cyan-400/10 pt-3'>
          <button
            onClick={toggleLight}
            className={`rounded-xl border px-3 py-2.5 text-sm font-semibold transition ${lightOn ? 'border-cyan-300/40 bg-cyan-400/15 text-cyan-200' : 'border-slate-700 bg-slate-950/55 text-slate-400'}`}>
            {lightOn ? 'Light On' : 'Light'}
          </button>

          {isActive ? (
            <button
              onClick={() => onCommand(isPaused ? 'resume' : 'pause')}
              className={`rounded-xl border px-3 py-2.5 text-sm font-semibold ${isPaused ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' : 'border-amber-400/30 bg-amber-400/10 text-amber-300'}`}>
              {isPaused ? 'Resume' : 'Pause'}
            </button>
          ) : (
            <div className='rounded-xl border border-slate-800 bg-slate-950/30 px-3 py-2.5 text-center text-sm text-slate-600'>No active print</div>
          )}

          {isActive && (
            <>
              <button
                onClick={skipObject}
                className='rounded-xl border border-cyan-400/25 bg-cyan-400/10 px-3 py-2.5 text-sm font-semibold text-cyan-300'>
                Skip Object
              </button>
              <button
                onClick={() => onCommand('stop')}
                className='rounded-xl border border-red-400/25 bg-red-500/10 px-3 py-2.5 text-sm font-semibold text-red-300'>
                Stop Print
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
'''


# Replace the final post-patch print card with the compact SCD X2D design.
Path('src/components/PrintStatusCard.tsx').write_text(CARD)

# Branded dashboard shell/header while leaving all X2D camera/telemetry logic intact.
dash_path = Path('src/pages/Dashboard.tsx')
d = dash_path.read_text()
d = d.replace(
    "<div className='min-h-screen bg-zinc-950 text-white flex flex-col relative'>",
    "<div className='min-h-screen bg-[#030812] text-white flex flex-col relative'>",
)
d = d.replace(
    "className='sticky top-0 z-10 flex items-center justify-between px-4 pb-3 bg-zinc-900 border-b border-zinc-800 shrink-0'",
    "className='sticky top-0 z-10 flex items-center justify-start gap-3 px-4 pb-3 bg-[#07111d]/95 border-b border-cyan-400/20 shadow-[0_6px_24px_rgba(0,0,0,0.28)] backdrop-blur shrink-0'",
)
d = d.replace(
    "<div className='flex flex-col items-center'>\n          <h1 className='font-semibold text-lg'>BambooMobile</h1>\n        </div>",
    "<div className='flex min-w-0 items-center gap-2.5'>\n          <img src='/scd-x2d-icon.png' alt='SCD X2D' className='h-9 w-9 shrink-0 rounded-xl border border-cyan-300/25 shadow-[0_0_14px_rgba(34,211,238,0.16)]' />\n          <div className='min-w-0 leading-none'>\n            <div className='flex items-baseline gap-1.5'>\n              <span className='text-sm font-extrabold tracking-[0.12em] text-slate-100'>SCD</span>\n              <span className='text-lg font-black tracking-tight text-cyan-300'>X2D</span>\n            </div>\n            <div className='mt-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500'>Printer Control</div>\n          </div>\n        </div>",
)
d = d.replace(
    "className='rounded-xl overflow-hidden bg-zinc-900 aspect-video flex items-center justify-center shrink-0'",
    "className='rounded-2xl overflow-hidden bg-[#07111d] border border-cyan-400/20 aspect-video flex items-center justify-center shrink-0 shadow-[0_10px_30px_rgba(0,0,0,0.30),0_0_18px_rgba(34,211,238,0.04)]'",
)
d = d.replace(
    "className='flex flex-col bg-zinc-800 rounded-xl overflow-hidden'",
    "className='flex flex-col bg-[#091523] rounded-2xl overflow-hidden border border-cyan-400/15 shadow-[0_8px_26px_rgba(0,0,0,0.22)]'",
)
dash_path.write_text(d)

# Shared section styling.
section_path = Path('src/components/Section.tsx')
if section_path.exists():
    s = section_path.read_text()
    s = s.replace("grid grid-cols-[auto_2px_1fr] gap-4 p-4", "grid grid-cols-[auto_1px_minmax(0,1fr)] gap-3 p-3.5")
    s = s.replace("h-full w-0.5 bg-zinc-600", "h-full w-px bg-cyan-400/15")
    s = s.replace("flex gap-4 w-full", "flex gap-3 min-w-0 w-full")
    section_path.write_text(s)

# Temperature controls: tighter cards and matching cyan accent.
temp_path = Path('src/components/TempGauge.tsx')
if temp_path.exists():
    t = temp_path.read_text()
    t = t.replace("className='flex flex-col items-center justify-center gap-4 group'", "className='flex min-w-0 flex-col items-center justify-center gap-2 rounded-xl border border-cyan-400/10 bg-slate-950/35 px-1.5 py-2.5 group'")
    t = t.replace("text-zinc-500 group-hover:text-white", "text-cyan-400/55 group-hover:text-cyan-200")
    t = t.replace("text-white text-xl font-bold", "text-slate-100 text-lg font-bold")
    t = t.replace("text-zinc-400 text-sm", "text-slate-500 text-xs")
    t = t.replace("text-zinc-500 text-xs mt-0.5", "text-cyan-400/60 text-[10px] mt-0.5")
    t = t.replace("bg-teal-700 hover:bg-teal-600", "bg-cyan-700 hover:bg-cyan-600")
    temp_path.write_text(t)

# Visible app name and Tauri product/window title. Package identifier is intentionally untouched.
strings_path = Path('src-tauri/gen/android/app/src/main/res/values/strings.xml')
if strings_path.exists():
    strings = strings_path.read_text()
    strings = strings.replace('>Bamboo Mobile<', '>SCD X2D<')
    strings_path.write_text(strings)

conf_path = Path('src-tauri/tauri.conf.json')
if conf_path.exists():
    conf = json.loads(conf_path.read_text())
    conf['productName'] = 'SCD X2D'
    for window in conf.get('app', {}).get('windows', []):
        window['title'] = 'SCD X2D'
    conf_path.write_text(json.dumps(conf, indent=2) + '\n')

# Decode the approved SCD X2D icon and use it both in the WebView header and launcher resources.
icon_b64_path = Path('.github/scd-x2d-icon-192.png.b64')
if not icon_b64_path.exists():
    raise SystemExit('Missing .github/scd-x2d-icon-192.png.b64')
icon = base64.b64decode(icon_b64_path.read_text().strip())
public = Path('public')
public.mkdir(exist_ok=True)
(public / 'scd-x2d-icon.png').write_bytes(icon)

res = Path('src-tauri/gen/android/app/src/main/res')
for folder in res.glob('mipmap-*dpi'):
    if not folder.is_dir():
        continue
    for name in ('ic_launcher.png', 'ic_launcher_round.png', 'ic_launcher_foreground.png'):
        target = folder / name
        if target.exists():
            target.write_bytes(icon)

print('SCD X2D branding + compact dashboard patch applied')
