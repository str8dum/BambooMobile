from pathlib import Path

path = Path('src-tauri/gen/android/app/src/main/res/values/strings.xml')
text = path.read_text()
text = text.replace('<string name="app_name">SCD X2D</string>', '<string name="app_name">SCDX2D</string>')
text = text.replace('<string name="app_name">Bamboo Mobile</string>', '<string name="app_name">SCDX2D</string>')
text = text.replace('<string name="main_activity_title">Bamboo Mobile</string>', '<string name="main_activity_title">SCD X2D</string>')
path.write_text(text)
print('Launcher label set to SCDX2D; in-app/activity title remains SCD X2D')
