import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# Cross-bonded torso test:
# Layer 1 at Y = -32:
# 3 plates 2x4 along Z at X=0: Z=-40, Z=0, Z=40
# Layer 2 at Y = -56:
# Bricks 2x4 staggered along Z: Z=-30, Z=10, Z=50
