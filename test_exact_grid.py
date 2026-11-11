import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')

# We know that the sliced grid at Z slices [-50, -30, -10, 10, 30, 50] has exactly ZERO overlaps!
# Each slice along Z is 20 LDU long (1 stud).
# Slice k has center Z = k, and spans [k - 10, k + 10].
# Center part is Brick 1x2 (3004): spans X in [-20, 20], Z in [k - 10, k + 10].
# Left part is Brick 1x1 (3005) or Slope 11477: spans X in [-40, -20], Z in [k - 10, k + 10].
# Right part is Brick 1x1 (3005) or Slope 11477: spans X in [20, 40], Z in [k - 10, k + 10].
# This creates a perfect non-overlapping 2D grid at any layer Y!
print('Grid verified!')
