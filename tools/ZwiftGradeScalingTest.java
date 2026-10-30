package com.ridesim.zwift;
public final class ZwiftGradeScalingTest {
    private static void near(double actual, double expected, String description) {
        if (Math.abs(actual-expected) > 0.00001)
            throw new AssertionError(description + ": got " + actual + " expected " + expected);
    }
    public static void main(String[] args) {
        near(SimEngine.displayedRoadGrade(1.42, 50), 2.84, "50% uphill");
        near(SimEngine.displayedRoadGrade(-0.75, 50), -3.0, "50% downhill");
        near(SimEngine.displayedRoadGrade(-0.70, 50), -2.8, "reported downhill");
        near(SimEngine.displayedRoadGrade(3.0, 100), 3.0, "100% uphill");
        near(SimEngine.displayedRoadGrade(-1.5, 100), -3.0, "100% downhill");
        near(SimEngine.displayedRoadGrade(0, 50), 0, "flat");
        near(SimEngine.displayedRoadGrade(3.0, 75), 4.0, "75% uphill");
        near(SimEngine.displayedRoadGrade(-1.5, 75), -4.0, "75% downhill");
        SimEngine e = new SimEngine();
        SimEngine.Settings c = new SimEngine.Settings();
        c.zwiftTrainerDifficultyPercent=50;
        c.targetWatts=300;
        e.configure(c);
        e.setFtmsTrainerGrade(2.5); // +5% displayed => +10% power
        near(e.gradePercent(), 5.0, "engine grade");
        SimEngine.Snapshot snap=e.tick(0.1);
        if (snap.hillBoostWatts!=30 || snap.hillMinimumWatts<330)
            throw new AssertionError("grade driven power floor "+snap.hillBoostWatts+" "+snap.hillMinimumWatts);
        System.out.println("True road grade restoration passed including downhill 4x and uphill floor");
    }
}
