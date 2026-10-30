#!/usr/bin/env python3
"""Raise Rich Kickr v0.7.0 user power range and all transmit caps to 2,000 W.

The BLE Cycling Power Measurement is sint16 and FTMS Indoor Bike Power is
sint16, so 2,000 W fits in both. We cap *transmitted* power at 2,000 W,
including added hill power and random variation; there is no hidden 1,200 W cap.
"""
from pathlib import Path

root=Path("ridesim")
sim=root/"app/src/main/java/com/ridesim/zwift/SimEngine.java"
src=sim.read_text()
assert src.count("public final class SimEngine {")==1
src=src.replace("public final class SimEngine {",
    "public final class SimEngine {\n    /** Maximum user target AND transmitted power, in watts. */\n    public static final int MAX_POWER_WATTS = 2000;",1)
# There were six hardcoded simulation cap occurrences in the 0.6.x engine.
assert src.count("1200")==6, ("power cap occurrences",src.count("1200"))
src=src.replace("1200","MAX_POWER_WATTS")
sim.write_text(src)

ui=root/"app/src/main/java/com/ridesim/zwift/MainActivity.java"
m=ui.read_text()
assert m.count("powerSlider.setMax(600);")==1
assert m.count("Math.min(600, cfg.targetWatts)")==1
m=m.replace("powerSlider.setMax(600);","powerSlider.setMax(SimEngine.MAX_POWER_WATTS);",1)
m=m.replace("Math.min(600, cfg.targetWatts)","Math.min(SimEngine.MAX_POWER_WATTS, cfg.targetWatts)",1)
ui.write_text(m)

gradle=root/"app/build.gradle"
g=gradle.read_text()
assert "versionCode 19" in g and "versionName '0.6.9'" in g
g=g.replace("versionCode 19","versionCode 20")
g=g.replace("versionName '0.6.9'","versionName '0.7.0'")
gradle.write_text(g)
print("v0.7.0: UI 0-2000 W, settings 0-2000 W, output max 2000 W, versionCode20")
