import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# A 11477 (Slope 2x1 Curved) has length 2 studs along Z (or along X depending on rotation).
# Studs of 3032 at X = 30 are at Z = [-50, -30, -10, 10, 30, 50].
# Two studs in a 2x1 slope are 20 LDU apart, e.g. at Z = -50 and Z = -30.
# So center Z is -40!
mpd = """0 FILE test.ldr
0 Test
0 Name: test.ldr
0 Author: Antigravity
1 29 0 -8 0 0 0 1 0 1 0 -1 0 0 3032.dat
1 29 30 -8 -40 0 0 -1 0 1 0 1 0 0 11477.dat
1 29 -30 -8 -40 0 0 1 0 1 0 -1 0 0 11477.dat
0 NOFILE
"""
with open("test_studs.mpd", "w") as f: f.write(mpd)
res = subprocess.run(["./ldraw-agent", "validate", "test_studs.mpd", "--geometry"], capture_output=True, text=True, env=env)
d = json.loads(res.stdout)
print("Errors:", [e["message"] for e in d.get("diagnostics", []) if e.get("severity") == "error"])
print("Contacts count:", d["geometry"]["contact_count"])
for c in d["geometry"]["contacts"]:
    print(c["instances"], c["status"], c["kinds"])
