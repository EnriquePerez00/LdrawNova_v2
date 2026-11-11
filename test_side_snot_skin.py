import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# Test attaching SNOT curved slope on side of brick 11211 (Brick 1x2 with studs on side):
# 11211 at X = -30, Y = -32, Z = 0, ROT_Y_90:
# Studs face -X (towards -X).
# Attached to it: Plate 1x2 or Curved slope 11477 oriented vertically:
