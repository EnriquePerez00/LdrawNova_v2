import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# If plate 1x2 (3023) is at X = -30, Z = -40, oriented along X (ROT_ID):
# It has studs at [-40, 0, -40] and [-20, 0, -40].
# Then 11477 at [-30, 0, -40] with ROT_Y_90 has sockets at [-40, 0, -40] and [-20, -8, -40].
# Let's verify:
mpd = """0 FILE test.ldr
0 Test Flank
0 Name: test.ldr
0 Author: Antigravity
1 29 -30 -8 -40 1 0 0 0 1 0 0 0 1 3023.dat
1 29 -30 -8 -40 0 0 1 0 1 0 -1 0 0 11477.dat
0 NOFILE
"""
with open("test_flank.mpd", "w") as f: f.write(mpd)
res = subprocess.run(["./ldraw-agent", "validate", "test_flank.mpd", "--geometry"], capture_output=True, text=True, env=env)
d = json.loads(res.stdout)
print("Errors:", [e["message"] for e in d.get("diagnostics", []) if e.get("severity") == "error"])
print("Contacts count:", d["geometry"]["contact_count"])
for c in d["geometry"]["contacts"]:
    print(c["instances"], c["status"], c["kinds"])
