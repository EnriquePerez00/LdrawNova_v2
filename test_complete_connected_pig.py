import json, subprocess, os

# Let's write the complete generator where every single part connects to its underlying or adjacent support.
# 1. Underbelly base plate 4x6 at Y = -8 (ROT_Y_90):
#    Its bottom (Y=0) connects to the 4 legs at X=-30, +30 and Z=-40, +40.
# 2. Torso brick layer 1 at Y = -32:
#    Bricks 1x2 and 1x1 along Z slices [-50, -30, -10, 10, 30, 50].
# 3. Inter-tier tie plate layer at Y = -40:
#    Plates 1x2 and 1x1 along Z slices.
# 4. Torso brick layer 2 at Y = -64:
#    Bricks 1x2 and 1x1 along Z slices.
# 5. Dorsal plate 4x6 at Y = -72 (ROT_Y_90):
#    Rests on brick layer 2 top (Y=-64).
# 6. On top of dorsal plate (at Y = -72):
#    Center tiles 1x2 (3069b) along X = 0 at Z in [-50, -30, -10, 10, 30, 50].
#    Left flank curved slopes 11477 at X = -30, Z in [-40, 0, 40] (ROT_Y_90):
#      Connect to plates 1x2 at X = -30, Y = -72!
#    Right flank curved slopes 11477 at X = +30, Z in [-40, 0, 40] (ROT_Y_270):
#      Connect to plates 1x2 at X = +30, Y = -72!
# 7. Cranial Head at Z in [-120, -60]:
#    Neck plate 2x2 at Y = -8, Z = -80 (connects to underbelly plate).
#    Lower cranium brick 2x2 at Y = -32, Z = -80 (rests on neck plate).
#    Cheek plates 1x2 at X = -30, +30, Y = -32, Z = -80 (connects to cranium).
#    Mid cranial tie plate 2x2 at Y = -40, Z = -80.
#    Upper cranium brick 2x2 at Y = -64, Z = -80.
#    Cranial brow curved slope 15068 at Y = -64, Z = -80 (connects to upper cranium studs!).
#    Snout assembly at Z = -110 (mandible plate + bricks + face plate + nostrils).
# 8. Legs:
#    Sole plate 1x2 at Y = 48 (ROT_Y_90).
#    Toe slope 54200 forward + heel slope 54200 rearward.
#    Ankle brick 1x2 at Y = 24.
#    Thigh brick 1x2 at Y = 0 (top at 0 connects to underbelly plate).
# 9. Tail:
#    Clip plate 4085c at Y = -32, Z = 70.
#    Horn spiral 89522 plugged into clip.
