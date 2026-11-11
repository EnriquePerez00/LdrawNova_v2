import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# We want to connect curved slopes 11477 or 61678 to the flanks using REAL SNOT adapter bricks:
# 11211 (Brick 1x2 with 2 studs on side) or 87087 (Brick 1x1 with 1 stud on side) or brackets (99781).
# Let's test what orientation of 11477 connects to 11211:
