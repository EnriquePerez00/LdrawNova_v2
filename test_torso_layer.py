import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# Let's test a simple torso of 2 layers:
# Layer 1: Underbelly plate 4x6 at Y=-8: X [-40, 40], Z [-60, 60] -> Wait! Plate 4x6 is 4 studs by 6 studs!
# At ROT_ID: Plate 4x6 (3032.dat): min=[-60, -4, -40], max=[60, 8, 40].
# That is 6 studs along X, 4 studs along Z!
# If rotated ROT_Y_90: min=[-40, -4, -60], max=[40, 8, 60]! That is 4 studs along X, 6 studs along Z!
