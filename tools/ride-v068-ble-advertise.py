#!/usr/bin/env python3
"""v0.6.8: one trainer-focused BLE advertisement, no duplicate CPS+FTMS discovery."""
from pathlib import Path
import re

root = Path("ridesim")
p = root / "app/src/main/java/com/ridesim/zwift/BlePeripheral.java"
s = p.read_text()
pattern = re.compile(
    r'''            AdvertiseData\.Builder dataBuilder = new AdvertiseData\.Builder\(\)
                    \.addServiceUuid\(new ParcelUuid\(CPS\)\)
                    \.addServiceUuid\(new ParcelUuid\(HR\)\);
            if \(enableTrainerControl\) dataBuilder\.addServiceUuid\(new ParcelUuid\(FTMS\)\);
            AdvertiseData data = dataBuilder\.setIncludeDeviceName\(false\)\.build\(\);
            AdvertiseData scanResponse = new AdvertiseData\.Builder\(\)
                    \.setIncludeDeviceName\(true\)\.build\(\);'''
)
replacement = '''            // Prefer ONE advertised trainer identity when FTMS control is on.
            // Previously CPS + HR + FTMS were all in the primary advertisement,
            // leading Zwift to show redundant power/trainer discoveries.
            // Keep all GATT services for power/cadence/HR once connected.
            // When control is disabled, advertise a normal CPS power meter.
            AdvertiseData data = new AdvertiseData.Builder()
                    .addServiceUuid(new ParcelUuid(enableTrainerControl ? FTMS : CPS))
                    .setIncludeDeviceName(false).build();
            // Heart-rate remains discoverable; the scan response has space for
            // both the device name and this UUID.
            AdvertiseData scanResponse = new AdvertiseData.Builder()
                    .addServiceUuid(new ParcelUuid(HR))
                    .setIncludeDeviceName(true).build();'''
s,n=pattern.subn(replacement,s)
if n!=1: raise SystemExit("Expected a single primary advertisement section, found %s"%n)
p.write_text(s)
gradle=root/"app/build.gradle"
g=gradle.read_text()
assert "versionCode 17" in g and "versionName '0.6.7'" in g, g[:900]
g=g.replace("versionCode 17", "versionCode 18").replace("versionName '0.6.7'", "versionName '0.6.8'")
gradle.write_text(g)
assert "FTMS_INCLINATION_RANGE" in s
print("v0.6.8 GATT services retained, advertise one primary FTMS or CPS profile")
