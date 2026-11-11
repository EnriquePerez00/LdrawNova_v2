import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# Test placing 11477 at Y = -8 directly on plate 3032 at Y = -8:
for y_slope in [-8, 0, -16]:
    mpd = f"""0 FILE test.ldr
0 Test
0 Name: test.ldr
0 Author: Antigravity
1 29 0 -8 0 0 0 1 0 1 0 -1 0 0 3032.dat
1 29 -30 {y_slope} 0 0 0 1 0 1 0 -1 0 0 11477.dat
0 NOFILE
"""
    with open("test_try.mpd", "w") as f: f.write(mpd)
    res = subprocess.run(["./ldraw-agent", "validate", "test_try.mpd", "--geometry"], capture_output=True, text=True, env=env)
    d = json.loads(res.stdout)
    errs = len([e for e in d.get("diagnostics", []) if e.get("severity") == "error"])
    cnts = d["geometry"]["contact_count"]
    print(f"y_slope={y_slope:3d}: errors={errs}, contacts={cnts}")
