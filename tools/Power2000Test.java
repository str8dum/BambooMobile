package com.ridesim.zwift;
public final class Power2000Test {
  static void check(boolean value, String message) {
    if (!value) throw new AssertionError(message);
  }
  public static void main(String[] args) {
    check(SimEngine.MAX_POWER_WATTS == 2000,"max=2000");
    SimEngine e = new SimEngine();
    SimEngine.Settings s = new SimEngine.Settings();
    s.targetWatts = 2000; s.variationPercent = 0;
    e.configure(s); e.reset();
    check(e.settings().targetWatts == 2000,"2000 target retained after configure");
    for (int i=0;i<500;i++) e.tick(0.2);
    SimEngine.Snapshot z=e.snapshot();
    check(z.watts == 2000,"2000 baseline: "+z.watts);
    byte[] cps=BlePackets.power(z), ftms=FtmsPackets.indoorBikeData(z);
    check((cps[2]&255)==0xD0 && (cps[3]&255)==7, "Cycling Power 2000 W bytes");
    check((ftms[6]&255)==0xD0 && (ftms[7]&255)==7, "FTMS 2000 W bytes");
    e.setZwiftGrade(10.0);
    for (int i=0;i<25;i++) {
      z=e.tick(0.2);
      check(z.watts==2000,"no output above 2000 W with hill gain");
    }
    s.targetWatts=1800; s.variationPercent=40;
    e.configure(s); e.reset(); e.setZwiftGrade(5.0);
    z=e.tick(0.2);
    check(z.watts>=1980 && z.watts<=2000,
         "1800W +5% grade floor 1980, cap2000: "+z.watts);
    s.targetWatts=3000;
    e.configure(s);
    check(e.settings().targetWatts==2000,"old engine 1200 cap replaced by 2000");
    System.out.println("PASS: 2000W UI/engine cap, Bluetooth encoded 2000W, hill floor, stored target");
  }
}
