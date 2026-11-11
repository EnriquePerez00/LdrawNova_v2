import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# For the RIGHT flank (X = +30, curving down to +X):
# Plate 1x2 at [30, -8, -40] (ROT_ID)
# 11477 at [30, -8, -40] with ROT_Y_270:
mpd = """0 FILE test.ldr
0 Test Right Flank
0 Name: test.ldr
0 Author: Antigravity
1 29 30 -8 -40 1 0 0 0 1 0 0 0 1 3023.dat
1 29 30 -8 -40 0 0 -1 0 1 0 1 0 0 11477.dat
0 NOFILE
"""
with open("test_right_flank.mpd", "w") as f: f.write(mpd)
res = subprocess.run(["./ldraw-agent", "validate", "test_right_flank.mpd", "--geometry"], capture_output=True, text=True, env=env)
d = json.loads(res.stdout)
print("Errors:", [e["message"] for e in d.get("diagnostics", []) if e.get("severity") == "error"])
print("Contacts count:", d["geometry"]["contact_count"])
for c in d["geometry"]["contacts"]:
    print(c["instances"], c["status"], c["kinds"])
