#!/usr/bin/env python3
import json
import os
from pathlib import Path

v = os.environ.get('BAMBOO_X2D_VERSION_CODE', '').strip()
if not v.isdigit():
    raise SystemExit('BAMBOO_X2D_VERSION_CODE is missing or invalid')

p = Path('src-tauri/tauri.conf.json')
if not p.exists():
    raise SystemExit(f'Missing {p}')

data = json.loads(p.read_text(encoding='utf-8'))
bundle = data.setdefault('bundle', {})
android = bundle.setdefault('android', {})
android['versionCode'] = int(v)
p.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
print(f'Set Tauri Android versionCode={v}')
