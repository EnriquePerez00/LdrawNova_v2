import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# Test placing 4085c with snaps:
mpd = """0 FILE test.ldr
0 Test
0 Name: test.ldr
0 Author: Antigravity
1 29 0 0 0 1 0 0 0 1 0 0 0 1 3023.dat
1 29 0 -8 0 1 0 0 0 1 0 0 0 1 4085c.dat
0 NOFILE
"""
with open("test_snap_4085.mpd", "w") as f: f.write(mpd)
res = subprocess.run(["./ldraw-agent", "validate", "test_snap_4085.mpd", "--geometry"], capture_output=True, text=True, env=env)
d = json.loads(res.stdout)
print("Contacts count with 4085c at -8 on 3023 at 0:", d["geometry"]["contact_count"])
for c in d["geometry"]["contacts"]:
    print(c["instances"], c["status"], c["kinds"])
