from pathlib import Path
import re


card_path = Path('src/components/PrintStatusCard.tsx')
pc = card_path.read_text()

old = """  lightOn,\n  toggleLight,\n}: {"""
new = """  speedLevel,\n  onSetSpeed,\n}: {"""
if old not in pc:
    raise SystemExit('Print card light props marker not found')
pc = pc.replace(old, new, 1)

old = """  lightOn: boolean;\n  toggleLight: () => void;"""
new = """  speedLevel: number;\n  onSetSpeed: (level: number) => void;"""
if old not in pc:
    raise SystemExit('Print card light prop types marker not found')
pc = pc.replace(old, new, 1)

pattern = re.compile(
    r"          <button\n            onClick=\{toggleLight\}.*?\n          </button>",
    re.S,
)
replacement = """          <button
            onClick={() => onSetSpeed(speedLevel >= 4 ? 1 : Math.max(1, speedLevel + 1))}
            className='rounded-xl border border-cyan-400/25 bg-cyan-400/10 px-3 py-2.5 text-sm font-semibold text-cyan-300 transition active:scale-[0.98]'>
            {(['', 'Silent', 'Standard', 'Sport', 'Ludicrous'] as const)[Math.min(4, Math.max(1, speedLevel || 2))]}
          </button>"""
pc, count = pattern.subn(replacement, pc, count=1)
if count != 1:
    raise SystemExit(f'Expected one print-card light button, replaced {count}')

card_path.write_text(pc)


dash_path = Path('src/pages/Dashboard.tsx')
d = dash_path.read_text()
old = """              lightOn={lightOn}\n              toggleLight={toggleLight}"""
new = """              speedLevel={speedLevel}\n              onSetSpeed={setSpeed}"""
if old not in d:
    raise SystemExit('Dashboard PrintStatusCard light props marker not found')
d = d.replace(old, new, 1)
dash_path.write_text(d)

print('Print card Light button replaced with print-speed control')
