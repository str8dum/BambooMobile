from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"{label} marker not found")
    return text.replace(old, new, 1)


# ── Branded startup splash ───────────────────────────────────────────────────
# App already connects to the printer while ConnectingScreen is mounted. Make
# that screen an intentional SCD X2D splash and keep it visible for at least
# 1.5 s on the first launch so the dashboard normally appears already populated.
connecting = Path('src/pages/ConnectingScreen.tsx')
connecting.write_text(r'''export default function ConnectingScreen({ ip: _ip }: { ip: string }) {
  return (
    <div
      className='relative min-h-screen overflow-hidden bg-[#030812] text-white'
      style={{
        paddingTop: 'env(safe-area-inset-top, 0px)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}>
      <div className='absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(34,211,238,0.12),transparent_34%),radial-gradient(circle_at_50%_50%,rgba(37,99,235,0.08),transparent_55%)]' />
      <div className='relative flex min-h-screen flex-col items-center justify-center px-8'>
        <div className='relative'>
          <div className='absolute -inset-8 rounded-full bg-cyan-400/10 blur-3xl animate-pulse' />
          <img
            src='/scd-x2d-icon.png'
            alt='SCD X2D'
            className='relative h-40 w-40 rounded-[36px] border border-cyan-300/30 shadow-[0_0_48px_rgba(34,211,238,0.24),0_24px_70px_rgba(0,0,0,0.55)]'
          />
        </div>

        <div className='mt-8 flex items-baseline gap-2.5 leading-none'>
          <span className='text-3xl font-extrabold tracking-[0.12em] text-slate-100'>SCD</span>
          <span className='text-4xl font-black tracking-tight text-cyan-300'>X2D</span>
        </div>
        <div className='mt-3 text-xs font-semibold uppercase tracking-[0.30em] text-slate-500'>Printer Control</div>

        <div className='mt-12 flex items-center gap-3 rounded-full border border-cyan-400/15 bg-[#07111d]/80 px-5 py-3 shadow-lg'>
          <span className='h-2.5 w-2.5 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(103,232,249,0.9)] animate-pulse' />
          <span className='text-sm font-semibold tracking-wide text-slate-300'>Connecting…</span>
        </div>
      </div>
    </div>
  );
}
''')

app_path = Path('src/App.tsx')
a = app_path.read_text()
a = replace_once(
    a,
    "  const skipNextArmRef = useRef(false);\n",
    "  const skipNextArmRef = useRef(false);\n  const launchSplashAtRef = useRef(Date.now());\n  const initialSplashDoneRef = useRef(false);\n",
    'startup splash refs',
)
a = replace_once(
    a,
    """      await invoke('connect_printer', {
        ip: printer.ip,
        accessCode: printer.accessCode,
        serial: printer.serial,
      });
      setActivePrinterId(printer.id);""",
    """      await invoke('connect_printer', {
        ip: printer.ip,
        accessCode: printer.accessCode,
        serial: printer.serial,
      });
      if (!initialSplashDoneRef.current) {
        const elapsed = Date.now() - launchSplashAtRef.current;
        const remaining = Math.max(0, 1500 - elapsed);
        if (remaining > 0) {
          await new Promise<void>((resolve) => window.setTimeout(resolve, remaining));
        }
        initialSplashDoneRef.current = true;
      }
      setActivePrinterId(printer.id);""",
    'minimum startup splash duration',
)
app_path.write_text(a)


# ── Fan telemetry ─────────────────────────────────────────────────────────────
# X2D reports fan state both through the legacy flat fields and through
# device.airduct.parts. The latter is needed for the second auxiliary fan.
lib_path = Path('src-tauri/src/lib.rs')
s = lib_path.read_text()
s = replace_once(
    s,
    """    // True when the printer reports a LAN RTSP/RTSPS liveview URL.
    pub camera_rtsp_enabled: bool,
    pub bed_temp: f64,""",
    """    // True when the printer reports a LAN RTSP/RTSPS liveview URL.
    pub camera_rtsp_enabled: bool,
    // X2D fan telemetry, normalized to 0-100 percent.
    pub part_fan_percent: u8,
    pub aux_left_fan_percent: u8,
    pub aux_right_fan_percent: u8,
    pub exhaust_fan_percent: u8,
    pub bed_temp: f64,""",
    'fan status fields',
)

fan_parser = r'''

    // Fan telemetry. Older flat fields are usually 0-15; newer airduct state
    // values are reported as percent in the high 16 bits (range = 100 << 16).
    let fan_percent = |raw: u64| -> u8 {
        if raw > 255 {
            ((raw >> 16).min(100)) as u8
        } else if raw <= 15 {
            ((raw * 100 + 7) / 15).min(100) as u8
        } else if raw <= 100 {
            raw as u8
        } else {
            ((raw * 100 + 127) / 255).min(100) as u8
        }
    };
    let fan_raw = |key: &str| -> Option<u64> {
        p.get(key).and_then(|v| {
            v.as_u64().or_else(|| v.as_str().and_then(|s| s.parse().ok()))
        })
    };
    if let Some(raw) = fan_raw("cooling_fan_speed") {
        status.part_fan_percent = fan_percent(raw);
    }
    if let Some(raw) = fan_raw("big_fan1_speed") {
        status.aux_left_fan_percent = fan_percent(raw);
    }
    if let Some(raw) = fan_raw("big_fan2_speed") {
        status.exhaust_fan_percent = fan_percent(raw);
    }

    if let Some(parts) = p
        .get("device")
        .and_then(|v| v.get("airduct"))
        .and_then(|v| v.get("parts"))
        .and_then(|v| v.as_array())
    {
        for part in parts {
            let id = part
                .get("id")
                .and_then(|v| v.as_u64().or_else(|| v.as_str().and_then(|s| s.parse().ok())));
            let raw = part
                .get("state")
                .and_then(|v| v.as_u64().or_else(|| v.as_str().and_then(|s| s.parse().ok())));
            let (Some(id), Some(raw)) = (id, raw) else { continue };
            let pct = fan_percent(raw);
            match id {
                16 => status.part_fan_percent = pct,      // M106 P1
                32 => status.aux_left_fan_percent = pct, // M106 P2
                160 => status.aux_right_fan_percent = pct, // M106 P10
                48 => status.exhaust_fan_percent = pct,  // M106 P3
                _ => {}
            }
        }
    }
'''

s = replace_once(
    s,
    '    f64_field!(status.bed_temp, "bed_temper");',
    fan_parser + '\n    f64_field!(status.bed_temp, "bed_temper");',
    'fan telemetry parser',
)
lib_path.write_text(s)

vite_path = Path('src/vite-env.d.ts')
v = vite_path.read_text()
v = replace_once(
    v,
    """  camera_rtsp_enabled: boolean;
  bed_temp: number;""",
    """  camera_rtsp_enabled: boolean;
  part_fan_percent: number;
  aux_left_fan_percent: number;
  aux_right_fan_percent: number;
  exhaust_fan_percent: number;
  bed_temp: number;""",
    'TypeScript fan status fields',
)
vite_path.write_text(v)


# ── Fan control UI ────────────────────────────────────────────────────────────
fan_component = Path('src/components/FanControl.tsx')
fan_component.write_text(r'''import { useEffect, useState } from 'react';

type FanValues = {
  part: number;
  auxLeft: number;
  auxRight: number;
  exhaust: number;
};

const FAN_ROWS = [
  { key: 'part' as const, label: 'Part Cooling', short: 'PART', p: 1 },
  { key: 'auxLeft' as const, label: 'Aux Left', short: 'AUX L', p: 2 },
  { key: 'auxRight' as const, label: 'Aux Right', short: 'AUX R', p: 10 },
  { key: 'exhaust' as const, label: 'Exhaust', short: 'EXH', p: 3 },
];

function clamp(value: number) {
  return Math.max(0, Math.min(100, Math.round(value || 0)));
}

export default function FanControl({
  part,
  auxLeft,
  auxRight,
  exhaust,
  onSet,
}: FanValues & { onSet: (fanIndex: number, percent: number) => void }) {
  const [open, setOpen] = useState(false);
  const [local, setLocal] = useState<FanValues>({ part, auxLeft, auxRight, exhaust });

  useEffect(() => {
    if (!open) setLocal({ part, auxLeft, auxRight, exhaust });
  }, [part, auxLeft, auxRight, exhaust, open]);

  function setLocalFan(key: keyof FanValues, value: number) {
    setLocal((prev) => ({ ...prev, [key]: clamp(value) }));
  }

  function commit(key: keyof FanValues, p: number, value?: number) {
    const next = clamp(value ?? local[key]);
    setLocalFan(key, next);
    onSet(p, next);
  }

  return (
    <>
      <button
        type='button'
        onClick={() => setOpen(true)}
        className='flex min-w-0 flex-col items-center justify-center gap-2 rounded-xl border border-cyan-400/10 bg-slate-950/35 px-2 py-2.5 text-left transition active:scale-[0.98]'>
        <svg className='h-8 w-8 text-cyan-400/60' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='1.8' strokeLinecap='round' strokeLinejoin='round'>
          <path d='M12 12c-2.7-3.3-2.5-6.4.2-8.4 1.8 2.2 2.1 4.5.8 6.7' />
          <path d='M12 12c3.3-2.7 6.4-2.5 8.4.2-2.2 1.8-4.5 2.1-6.7.8' />
          <path d='M12 12c2.7 3.3 2.5 6.4-.2 8.4-1.8-2.2-2.1-4.5-.8-6.7' />
          <path d='M12 12c-3.3 2.7-6.4 2.5-8.4-.2 2.2-1.8 4.5-2.1 6.7-.8' />
          <circle cx='12' cy='12' r='1.2' />
        </svg>
        <div className='text-lg font-bold text-slate-100'>Fans</div>
        <div className='grid w-full grid-cols-2 gap-x-2 gap-y-0.5 text-[9px] font-semibold tabular-nums text-cyan-400/65'>
          <span>PART {clamp(part)}%</span>
          <span>AUX L {clamp(auxLeft)}%</span>
          <span>AUX R {clamp(auxRight)}%</span>
          <span>EXH {clamp(exhaust)}%</span>
        </div>
      </button>

      {open && (
        <div
          className='fixed inset-0 z-[90] flex items-end justify-center bg-black/75 px-3 pb-[max(12px,env(safe-area-inset-bottom,0px))] pt-[max(12px,env(safe-area-inset-top,0px))] backdrop-blur-sm sm:items-center'
          onClick={() => setOpen(false)}>
          <div
            className='w-full max-w-md rounded-2xl border border-cyan-400/20 bg-[#081522] p-4 shadow-[0_24px_70px_rgba(0,0,0,0.65)]'
            onClick={(event) => event.stopPropagation()}>
            <div className='mb-4 flex items-center justify-between'>
              <div>
                <div className='text-lg font-bold text-slate-100'>X2D Fan Control</div>
                <div className='mt-0.5 text-[11px] text-slate-500'>Manual fan speed · 0–100%</div>
              </div>
              <button
                type='button'
                onClick={() => setOpen(false)}
                className='flex h-10 w-10 items-center justify-center rounded-full border border-slate-700 bg-slate-950/70 text-slate-300'>
                <svg className='h-5 w-5' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2'>
                  <path strokeLinecap='round' d='M6 6l12 12M18 6L6 18' />
                </svg>
              </button>
            </div>

            <div className='flex flex-col gap-3'>
              {FAN_ROWS.map((fan) => (
                <div key={fan.key} className='rounded-xl border border-cyan-400/10 bg-slate-950/45 p-3'>
                  <div className='mb-2 flex items-center justify-between gap-3'>
                    <span className='text-sm font-semibold text-slate-200'>{fan.label}</span>
                    <span className='min-w-[3.5rem] text-right text-base font-bold tabular-nums text-cyan-300'>{clamp(local[fan.key])}%</span>
                  </div>
                  <input
                    type='range'
                    min={0}
                    max={100}
                    step={1}
                    value={clamp(local[fan.key])}
                    onChange={(event) => setLocalFan(fan.key, Number(event.target.value))}
                    onPointerUp={() => commit(fan.key, fan.p)}
                    onKeyUp={() => commit(fan.key, fan.p)}
                    className='h-2 w-full accent-cyan-400'
                  />
                  <div className='mt-2 grid grid-cols-4 gap-1.5'>
                    {[0, 50, 75, 100].map((preset) => (
                      <button
                        key={preset}
                        type='button'
                        onClick={() => commit(fan.key, fan.p, preset)}
                        className={`rounded-lg border py-1.5 text-[11px] font-semibold ${clamp(local[fan.key]) === preset ? 'border-cyan-300/40 bg-cyan-400/15 text-cyan-200' : 'border-slate-700 bg-slate-900/60 text-slate-400'}`}>
                        {preset === 0 ? 'Off' : `${preset}%`}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <button
              type='button'
              onClick={() => setOpen(false)}
              className='mt-4 w-full rounded-xl border border-cyan-400/20 bg-cyan-400/10 py-3 text-sm font-bold text-cyan-200'>
              Done
            </button>
          </div>
        </div>
      )}
    </>
  );
}
''')

dash_path = Path('src/pages/Dashboard.tsx')
d = dash_path.read_text()
d = replace_once(
    d,
    "import TempGauge from '../components/TempGauge';",
    "import TempGauge from '../components/TempGauge';\nimport FanControl from '../components/FanControl';",
    'FanControl import',
)

# Replace the legacy active-nozzle temperature tile below the dual-nozzle row.
marker = "                    actual={status.nozzle_temp}"
marker_i = d.find(marker)
if marker_i < 0:
    raise SystemExit('active nozzle TempGauge marker not found')
start_i = d.rfind("                  <TempGauge", 0, marker_i)
end_marker = "                  />"
end_i = d.find(end_marker, marker_i)
if start_i < 0 or end_i < 0:
    raise SystemExit('active nozzle TempGauge bounds not found')
end_i += len(end_marker)
fan_tile = r'''                  <FanControl
                    part={status.part_fan_percent}
                    auxLeft={status.aux_left_fan_percent}
                    auxRight={status.aux_right_fan_percent}
                    exhaust={status.exhaust_fan_percent}
                    onSet={(fanIndex, percent) =>
                      sendGcode(`M106 P${fanIndex} S${Math.round((percent / 100) * 255)}`)
                    }
                  />'''
d = d[:start_i] + fan_tile + d[end_i:]
dash_path.write_text(d)

print('SCD X2D startup splash + four-fan telemetry/control patch applied')
