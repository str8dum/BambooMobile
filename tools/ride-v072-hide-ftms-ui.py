#!/usr/bin/env python3
"""v0.7.2: remove obsolete FTMS debugging from the rider-facing UI.

Keep the real-grade readout, live Hill Boost, minimum power floor, and all
FTMS GATT/control functionality. Only rider-visible diagnostics are removed.
"""
from pathlib import Path
import re

p=Path("ridesim/app/src/main/java/com/ridesim/zwift/MainActivity.java")
s=p.read_text()
print("Before cleanup, FTMS diagnostic UI references:")
for i,l in enumerate(s.splitlines(),1):
    if re.search(r"ftmsDiagnostics|txtFtms|FTMS CTRL|FTMS DIAG|ftmsDiagnostic", l, re.I):
        print(f"  {i:4}: {l.strip()}")

# The diagnostic TextView was introduced in v0.6.6. Discover its identifier
# from the declaration or creation code instead of assuming a fixed name.
names=set()
for m in re.finditer(r'(?m)^\s*(?:private\s+)?(?:TextView\s+)?([A-Za-z_$][\w$]*)\s*=\s*text\s*\(\s*"FTMS[^"\n]*"',s):
    names.add(m.group(1))
for m in re.finditer(r'(?m)^\s*if\s*\(\s*([A-Za-z_$][\w$]*)\s*!=\s*null\s*\)\s*\1\.setText\s*\([\s\S]{0,350}?ftmsDiagnostics\s*\(',s):
    names.add(m.group(1))
for m in re.finditer(r'(?m)^\s*(?:private\s+)?TextView\s+([A-Za-z_$][\w$]*ftms[A-Za-z_$\w]*)',s,re.I):
    names.add(m.group(1))
print("Detected diagnostic view IDs:",sorted(names))
if not names:
    raise SystemExit("Did not locate the diagnostics view; refusing to silently produce unchanged APK")

for name in names:
    n=re.escape(name)
    # Remove a UI refresh statement that renders the diagnostic call; allow
    # multiline expressions, stopping at the first statement-ending semicolon.
    s, updates=re.subn(
        r'(?m)^\s*if\s*\(\s*'+n+r'\s*!=\s*null\s*\)\s*'
        +n+r'\.setText\s*\([\s\S]{0,650}?\);\s*\n',
        '',s)
    # Remove the diagnostic text-view creation and insertion into a panel.
    s, creates=re.subn(
        r'(?m)^\s*'+n+r'\s*=\s*text\s*\([\s\S]{0,350}?\);\s*\n',
        '',s)
    s, inserts=re.subn(
        r'(?m)^\s*\w+\.addView\s*\(\s*'+n+r'\s*\);\s*\n',
        '',s)
    print(f"Cleaned {name}: {updates} live updates, {creates} view creation, {inserts} panel additions")
    if updates < 1 or creates < 1 or inserts < 1:
        raise SystemExit("Incomplete removal of "+name)

if re.search(r'FTMS CTRL|FTMS DIAG|\.ftmsDiagnostics\s*\(',s,re.I):
    raise SystemExit("FTMS diagnostics would still be visible on main page")
assert 'ZWIFT GRADE  ' in s
assert 'HILL BOOST  ' in s
assert 'showExactPowerDialog' in s
p.write_text(s)

g=Path("ridesim/app/build.gradle")
v=g.read_text()
assert v.count("versionCode 21")==1 and v.count("versionName '0.7.1'")==1
v=v.replace("versionCode 21","versionCode 22")
v=v.replace("versionName '0.7.1'","versionName '0.7.2'")
g.write_text(v)
print("v0.7.2: Diagnostics UI removed; terrain grade, hill boost and numeric watts preserved")
