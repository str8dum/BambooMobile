#!/usr/bin/env python3
"""KICKR-SIM v0.7.1: numeric-only exact watt input dialog alongside slider."""
from pathlib import Path

root = Path("ridesim")
main = root / "app/src/main/java/com/ridesim/zwift/MainActivity.java"
s = main.read_text()

def once(needle, replacement):
    global s
    n=s.count(needle)
    if n != 1:
        raise SystemExit("Expected exactly one "+repr(needle)+", found "+str(n))
    s=s.replace(needle,replacement,1)

once("import android.app.Activity;", """import android.app.Activity;
import android.app.AlertDialog;""")
once("import android.os.Looper;", """import android.os.Looper;
import android.text.InputFilter;
import android.text.InputType;
import android.text.method.DigitsKeyListener;
import android.view.inputmethod.InputMethodManager;
import android.view.WindowManager;""")
once("""        powerControl.addView(powerSlider, new LinearLayout.LayoutParams(-1, dp(74)));""", """        // Tap the large wattage readout to enter an exact integer power.
        // The keypad and input filter allow 0-9 ONLY (no letters, signs or decimals).
        powerSetpoint.setClickable(true);
        powerSetpoint.setContentDescription("Tap to type an exact target power in watts");
        powerSetpoint.setOnClickListener(v -> showExactPowerDialog(powerSlider));
        powerControl.addView(text("Tap watt value to type exact power (0–2,000 W)",
                12, MUTED, false));
        powerControl.addView(powerSlider, new LinearLayout.LayoutParams(-1, dp(74)));""")
once("    private void adjustPower(SeekBar bar, int delta) {", """    /** Exact watts dialog; only decimal digits are permitted, including pasted input. */
    private void showExactPowerDialog(SeekBar powerSlider) {
        EditText wattsInput = new EditText(this);
        wattsInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        wattsInput.setKeyListener(DigitsKeyListener.getInstance("0123456789"));
        wattsInput.setFilters(new InputFilter[]{new InputFilter.LengthFilter(4)});
        wattsInput.setSingleLine(true);
        wattsInput.setText(String.valueOf(cfg.targetWatts));
        wattsInput.selectAll();
        wattsInput.setHint("0–2000");
        wattsInput.setTextSize(24);
        wattsInput.setSelectAllOnFocus(true);

        // Give the number field comfortable spacing inside the native Android dialog.
        LinearLayout wrapper = new LinearLayout(this);
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setPadding(dp(24), dp(8), dp(24), dp(4));
        wrapper.addView(wattsInput, new LinearLayout.LayoutParams(-1, dp(64)));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Enter target power (W)")
                .setView(wrapper)
                .setNegativeButton("CANCEL", (d, which) -> {})
                .setPositiveButton("SET POWER", null)
                .create();
        dialog.setOnShowListener(d -> {
            // Do not dismiss on invalid input: explain the accepted numeric range.
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String value = wattsInput.getText().toString().trim();
                int newWatts;
                try {
                    if (value.isEmpty()) throw new NumberFormatException("empty");
                    newWatts = Integer.parseInt(value);
                } catch (NumberFormatException e) {
                    wattsInput.setError("Enter a whole number from 0 to 2,000");
                    return;
                }
                if (newWatts < 0 || newWatts > SimEngine.MAX_POWER_WATTS) {
                    wattsInput.setError("Enter a whole number from 0 to 2,000");
                    return;
                }
                powerSlider.setProgress(newWatts);
                cfg.targetWatts = newWatts;
                changed();
                dialog.dismiss();
            });
            wattsInput.requestFocus();
            dialog.getWindow().setSoftInputMode(
                    WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
            wattsInput.post(() -> {
                InputMethodManager imm = (InputMethodManager)
                        getSystemService(INPUT_METHOD_SERVICE);
                if (imm != null) imm.showSoftInput(
                        wattsInput, InputMethodManager.SHOW_IMPLICIT);
            });
        });
        dialog.show();
    }

    private void adjustPower(SeekBar bar, int delta) {""")
main.write_text(s)

gradle=root / "app/build.gradle"
g=gradle.read_text()
assert g.count("versionCode 20")==1 and g.count("versionName '0.7.0'")==1
g=g.replace("versionCode 20","versionCode 21")
g=g.replace("versionName '0.7.0'","versionName '0.7.1'")
gradle.write_text(g)

assert "powerSlider.setMax(SimEngine.MAX_POWER_WATTS);" in s
assert "DigitsKeyListener.getInstance(\"0123456789\")" in s
assert "powerSlider.setProgress(newWatts);" in s
print("v0.7.1 exact numeric watt keypad 0-2000; synchronized slider, saved settings")
