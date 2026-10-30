#!/usr/bin/env python3
"""Rich Kickr v0.6.9: restore Zwift's true map grade from trainer-control grade.

Zwift transmits scaled terrain grades to a trainer according to Trainer Difficulty:
uphill: displayed_grade * difficulty
downhill: displayed_grade * difficulty * 0.5
Only FTMS values should be unscaled; grade from the optional OCR Wi-Fi helper is
already the displayed road grade and must not be transformed.
"""
from pathlib import Path

root = Path("ridesim")
sim = root / "app/src/main/java/com/ridesim/zwift/SimEngine.java"
s = sim.read_text()
def replace_once(src, a, b, label):
    count = src.count(a)
    if count != 1:
        raise RuntimeError(f"{label}: wanted exactly one occurrence, got {count}")
    return src.replace(a, b, 1)

s = replace_once(s,
    "        public boolean followZwiftGrade = true;",
    """        public boolean followZwiftGrade = true;
        /** Match Zwift's Trainer Difficulty slider; Zwift defaults to 50%. */
        public int zwiftTrainerDifficultyPercent = 50;""", "setting declaration")
s = replace_once(s,
    "            c.followZwiftGrade = followZwiftGrade;",
    """            c.followZwiftGrade = followZwiftGrade;
            c.zwiftTrainerDifficultyPercent = zwiftTrainerDifficultyPercent;""", "settings copy")
s = replace_once(s,
    "        config.hillPowerPercentPerFiveGrade = clamp(config.hillPowerPercentPerFiveGrade, 0, 20);",
    """        config.hillPowerPercentPerFiveGrade = clamp(config.hillPowerPercentPerFiveGrade, 0, 20);
        config.zwiftTrainerDifficultyPercent = clamp(config.zwiftTrainerDifficultyPercent, 10, 100);""", "clamp")
s = replace_once(s,
    "    public synchronized void setZwiftGrade(double grade) { gradePercent = clamp(grade, -25.0, 25.0); gradeValid = true; }",
    """    /** True game-road grade inferred from Zwift's FTMS trainer command.
     * A 50%-difficulty trainer sees ~half uphill and ~quarter downhill.
     * Use displayed grade for hill power, NOT the trainer resistance command.
     */
    static double displayedRoadGrade(double trainerGrade, int difficultyPercent) {
        double difficulty = clamp(difficultyPercent, 10, 100) / 100.0;
        double scale = difficulty * (trainerGrade < 0.0 ? 0.5 : 1.0);
        return clamp(trainerGrade / scale, -25.0, 25.0);
    }
    public synchronized void setFtmsTrainerGrade(double ftmsGrade) {
        setZwiftGrade(displayedRoadGrade(ftmsGrade, config.zwiftTrainerDifficultyPercent));
    }
    /** Wi-Fi helper already reads actual screen grade: do not undo scaling. */
    public synchronized void setZwiftGrade(double grade) { gradePercent = clamp(grade, -25.0, 25.0); gradeValid = true; }""", "FTMS method")
sim.write_text(s)

ble = root / "app/src/main/java/com/ridesim/zwift/BlePeripheral.java"
b = ble.read_text()
b = replace_once(b,
    "RideService.ENGINE.setZwiftGrade(command.gradePercent);",
    "RideService.ENGINE.setFtmsTrainerGrade(command.gradePercent);",
    "FTMS handler")
ble.write_text(b)

ui = root / "app/src/main/java/com/ridesim/zwift/MainActivity.java"
m = ui.read_text()
m = replace_once(m,
    '        seek(hills, "Uphill boost at 5% road grade", "%", 0, 20,',
    '''        seek(hills, "Zwift Trainer Difficulty (match Zwift setting)", "%", 10, 100,
                cfg.zwiftTrainerDifficultyPercent, x -> cfg.zwiftTrainerDifficultyPercent = x);
        hills.addView(text("Default 50%: Zwift sends about half the map grade uphill and one-quarter downhill. "
                + "Rich Kickr reverses this for the displayed road grade and hill boost. "
                + "Match this slider to Zwift Settings > Trainer Difficulty. "
                + "This applies only to Bluetooth FTMS, not the Windows Helper.", 12, MUTED, false));
        seek(hills, "Uphill boost at 5% road grade", "%", 0, 20,''', "UI difficulty slider")
m = replace_once(m,
    '                .putBoolean("zwiftGrade", cfg.followZwiftGrade)',
    '''                .putBoolean("zwiftGrade", cfg.followZwiftGrade)
                .putInt("zwiftTrainerDifficulty", cfg.zwiftTrainerDifficultyPercent)''', "settings save")
m = replace_once(m,
    '        cfg.followZwiftGrade = preferences.getBoolean("zwiftGrade", true);',
    '''        cfg.followZwiftGrade = preferences.getBoolean("zwiftGrade", true);
        cfg.zwiftTrainerDifficultyPercent = preferences.getInt("zwiftTrainerDifficulty", 50);''',
    "settings read")
ui.write_text(m)

gradle = root / "app/build.gradle"
g = gradle.read_text()
g = replace_once(g, "versionCode 18", "versionCode 19", "version code")
g = replace_once(g, "versionName '0.6.8'", "versionName '0.6.9'", "version name")
gradle.write_text(g)
print("v0.6.9 true Zwift grade scaling applied; Wi-Fi helper remains unscaled")
