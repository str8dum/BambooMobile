from pathlib import Path
import os, re
p = Path('src-tauri/gen/android/app/build.gradle.kts')
v = os.environ['BAMBOO_X2D_VERSION_CODE']
s = p.read_text()
s, n = re.subn(r'versionCode\s*=\s*\d+', f'versionCode = {v}', s, count=1)
if n != 1:
    raise SystemExit('Could not patch Android versionCode')
p.write_text(s)
print(f'Forced Android versionCode={v}')
