from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "BT_VESC")

def p(rel):
    return ROOT / rel

def replace_once(rel, old, new):
    path = p(rel)
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{rel}: expected 1 match for {old!r}, got {n}")
    path.write_text(s.replace(old, new, 1))

# Build identifier.
replace_once(
    "applications/app_version.h",
    '#define APP_VERSION "BT_VESC VERSION 2.3 GEORGE 0.4"',
    '#define APP_VERSION "BT_VESC VERSION 2.3 GEORGE 0.4 SINGLE PRESET IMBAL"'
)

# Single-press start only. Running click/shift logic remains stock GEORGE.
tp = p("applications/trigger.c")
L = tp.read_text().splitlines(keepends=True)
hits = [i for i, x in enumerate(L) if x.strip() == "case SWST_OFF:"]
if len(hits) != 1:
    raise SystemExit(f"trigger.c SWST_OFF hits: {hits}")
off = hits[0]
on = next((i for i in range(off + 1, len(L)) if L[i].strip() == "case SWST_ON:"), None)
if on is None:
    raise SystemExit("trigger.c SWST_ON not found after SWST_OFF")
L[off:on] = [
    "        case SWST_OFF:\n",
    "            if (event == SW_PRESSED)\n",
    "            {\n",
    "                state = SWST_ONE_ON;\n",
    "                timeout = TIME_INFINITE;\n",
    "                send_to_speed (SPEED_ON);\n",
    "            }\n",
    "            break;\n",
]
tp.write_text("".join(L))

# User's current BT_VESC settings as reset defaults.
defaults = p("applications/defaults.h")
s = defaults.read_text()
pairs = [
    ("#define TRIG_ON_TOUT_MS 400", "#define TRIG_ON_TOUT_MS 800"),
    ("#define TRIG_OFF_TOUT_MS 500", "#define TRIG_OFF_TOUT_MS 900"),
    ("#define SPEED_DEFAULT 3", "#define SPEED_DEFAULT 2"),
    ("#define SPEEDS1 1525", "#define SPEEDS1 1975"),
    ("#define SPEEDS2 2300", "#define SPEEDS2 2175"),
    ("#define SPEEDS3 3100", "#define SPEEDS3 2350"),
    ("#define SPEEDS4 3525", "#define SPEEDS4 2525"),
    ("#define SPEEDS5 3900", "#define SPEEDS5 2950"),
    ("#define SPEEDS6 4150", "#define SPEEDS6 3250"),
    ("#define SPEEDS7 4450", "#define SPEEDS7 3975"),
    ("#define SPEEDS8 4850", "#define SPEEDS8 4150"),
    ("#define SPEEDS9 5000", "#define SPEEDS9 4700"),
    ("#define LIMITS1 1", "#define LIMITS1 1.75"),
    ("#define LIMITS2 2.2", "#define LIMITS2 2.00"),
    ("#define LIMITS3 3.8", "#define LIMITS3 2.40"),
    ("#define LIMITS4 6.2", "#define LIMITS4 3.00"),
    ("#define LIMITS5 9.6", "#define LIMITS5 4.50"),
    ("#define LIMITS6 12.8", "#define LIMITS6 6.00"),
    ("#define LIMITS7 17", "#define LIMITS7 9.20"),
    ("#define LIMITS8 22.8", "#define LIMITS8 12.50"),
    ("#define LIMITS9 23", "#define LIMITS9 20.00"),
    ("#define CRUISE 0", "#define CRUISE 1"),
    ("#define LOW_MIGRATE 0", "#define LOW_MIGRATE 1"),
]
for old, new in pairs:
    if s.count(old) != 1:
        raise SystemExit(f"defaults.h: expected 1 match for {old!r}, got {s.count(old)}")
    s = s.replace(old, new, 1)
defaults.write_text(s)

# Emit a display-only warning immediately after each existing 5-second
# filtered battery update. The sign convention matches display_battery_graph():
# positive batteries[1]-batteries[0] => battery 1 is lower.
app = p("applications/app_sikorski.c")
s = app.read_text()
anchor = "    chMtxUnlock(&batt_mutex);\n}\n\nstatic THD_FUNCTION(switch_thread, arg)"
repl = (
    "    chMtxUnlock(&batt_mutex);\n"
    "\n"
    "    // Live imbalance indication using the existing filtered battery values.\n"
    "    if (settings->b2Rratio != 0.0)\n"
    "    {\n"
    "        float imbalance = get_battery_imbalance();\n"
    "        if (imbalance > settings->batt_imbalance)\n"
    "            send_to_display (BATT_1_TOOLOW);\n"
    "        else if (imbalance < (-settings->batt_imbalance))\n"
    "            send_to_display (BATT_2_TOOLOW);\n"
    "    }\n"
    "}\n"
    "\n"
    "static THD_FUNCTION(switch_thread, arg)"
)
if s.count(anchor) != 1:
    raise SystemExit(f"app_sikorski warning anchor count={s.count(anchor)}")
app.write_text(s.replace(anchor, repl, 1))

# While running, show the existing battery graph and its small 1/2 marker
# for 3 seconds. Persistent imbalance repeats every 5 seconds. Any speed
# change display event takes priority. No motor/speed messages are generated.
disp = p("applications/display.c")
s = disp.read_text()

old = "#define HOLD_DISPLAY_TIME_mS MS2ST(1500)\n"
new = "#define HOLD_DISPLAY_TIME_mS MS2ST(1500)\n#define IMBALANCE_WARN_TIME_mS MS2ST(3000)\n"
if s.count(old) != 1:
    raise SystemExit("display hold-time anchor not found")
s = s.replace(old, new, 1)

old = (
    "    DISP_SPEED,     // displaying the speed number\n"
    "    DISP_PWR_ON     // Power on display\n"
    "} DISP_STATE;\n"
    "\n"
    "const char *const disp_states[] =\n"
    '    { "DISP_OFF", "DISP_BATT", "DISP_TRIG", "DISP_WAIT", "DISP_SPEED", "DISP_PWR_ON" };'
)
new = (
    "    DISP_SPEED,     // displaying the speed number\n"
    "    DISP_WARN,      // live battery-imbalance warning while running\n"
    "    DISP_PWR_ON     // Power on display\n"
    "} DISP_STATE;\n"
    "\n"
    "const char *const disp_states[] =\n"
    '    { "DISP_OFF", "DISP_BATT", "DISP_TRIG", "DISP_WAIT", "DISP_SPEED", "DISP_WARN", "DISP_PWR_ON" };'
)
if s.count(old) != 1:
    raise SystemExit("display enum anchor not found")
s = s.replace(old, new, 1)

old = (
    "        case DISP_TRIG:\n"
    "            if (event >= DISP_SPEED_1 && event <= DISP_SPEED_9) // don't handle above speed 9, rewrite as needed to support...\n"
    "                last_speed = event;\n"
    "\n"
    "            switch (event)"
)
new = (
    "        case DISP_TRIG:\n"
    "            if (event >= DISP_SPEED_1 && event <= DISP_SPEED_9) // don't handle above speed 9, rewrite as needed to support...\n"
    "                last_speed = event;\n"
    "\n"
    "            if (event == BATT_1_TOOLOW || event == BATT_2_TOOLOW)\n"
    "            {\n"
    "                display_battery_graph(false);\n"
    "                timeout = IMBALANCE_WARN_TIME_mS;\n"
    "                state = DISP_WARN;\n"
    "                break;\n"
    "            }\n"
    "\n"
    "            switch (event)"
)
if s.count(old) != 1:
    raise SystemExit("DISP_TRIG anchor not found")
s = s.replace(old, new, 1)

old = (
    '        case DISP_SPEED:\t\t\t\t// enter this state when "on trigger" - motor is running\n'
    "            if (event >= DISP_SPEED_1 && event <= DISP_SPEED_9) // don't handle above speed 9, rewrite as needed to support...\n"
    "            {\n"
    "                last_speed = event;\n"
    "                display_speed (last_speed);\n"
    "                timeout = MS2ST(settings->disp_on_ms);\n"
    "                break;\n"
    "            }\n"
    "            switch (event)"
)
new = (
    '        case DISP_SPEED:\t\t\t\t// enter this state when "on trigger" - motor is running\n'
    "            if (event >= DISP_SPEED_1 && event <= DISP_SPEED_9) // don't handle above speed 9, rewrite as needed to support...\n"
    "            {\n"
    "                last_speed = event;\n"
    "                display_speed (last_speed);\n"
    "                timeout = MS2ST(settings->disp_on_ms);\n"
    "                break;\n"
    "            }\n"
    "            if (event == BATT_1_TOOLOW || event == BATT_2_TOOLOW)\n"
    "            {\n"
    "                display_battery_graph(false);\n"
    "                timeout = IMBALANCE_WARN_TIME_mS;\n"
    "                state = DISP_WARN;\n"
    "                break;\n"
    "            }\n"
    "            switch (event)"
)
if s.count(old) != 1:
    raise SystemExit("DISP_SPEED anchor not found")
s = s.replace(old, new, 1)

old = (
    "        case DISP_BATT:\n"
    "            switch (event)\n"
    "            {\n"
    "            case DISP_ON_TRIGGER:"
)
new = (
    "        case DISP_WARN:\n"
    "            if (event >= DISP_SPEED_1 && event <= DISP_SPEED_9)\n"
    "            {\n"
    "                // User speed-change feedback takes priority.\n"
    "                last_speed = event;\n"
    "                display_speed (last_speed);\n"
    "                timeout = MS2ST(settings->disp_on_ms);\n"
    "                state = DISP_SPEED;\n"
    "                break;\n"
    "            }\n"
    "            switch (event)\n"
    "            {\n"
    "            case BATT_1_TOOLOW:\n"
    "            case BATT_2_TOOLOW:\n"
    "                display_battery_graph(false);\n"
    "                timeout = IMBALANCE_WARN_TIME_mS;\n"
    "                break;\n"
    "            case DISP_OFF_TRIGGER:\n"
    "                display_idle();\n"
    "                timeout = MS2ST(settings->disp_beg_ms / 24);\n"
    "                state = DISP_WAIT;\n"
    "                dot_pos = 0;\n"
    "                break;\n"
    "            case TIMER_EXPIRY:\n"
    "                if (last_speed >= DISP_SPEED_1 && last_speed <= DISP_SPEED_9)\n"
    "                {\n"
    "                    display_speed(last_speed);\n"
    "                    timeout = MS2ST(settings->disp_on_ms);\n"
    "                }\n"
    "                else\n"
    "                {\n"
    "                    display_idle();\n"
    "                    timeout = TIME_INFINITE;\n"
    "                }\n"
    "                state = DISP_SPEED;\n"
    "                break;\n"
    "            default:\n"
    "                break;\n"
    "            }\n"
    "            break;\n"
    "\n"
    "        case DISP_BATT:\n"
    "            switch (event)\n"
    "            {\n"
    "            case DISP_ON_TRIGGER:"
)
if s.count(old) != 1:
    raise SystemExit("DISP_BATT insertion anchor not found")
s = s.replace(old, new, 1)
disp.write_text(s)

print("Applied single-press start, user defaults, and live imbalance warning.")
