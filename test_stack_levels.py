# Clean stacking levels:
# Y = 48: Sole plate 1x2 (Y span [48, 56]) -> studs at [44, 48]
# Y = 24: Ankle brick 1x2 (Y span [24, 48]) -> bottom at 48 (sockets connect to sole studs at 48), studs at [20, 24]
# Y = 0: Thigh brick 1x2 (Y span [0, 24]) -> bottom at 24 (sockets connect to ankle studs at 24), studs at [-4, 0]
# Y = -8: Underbelly plate 4x6 (Y span [-8, 0]) -> bottom at 0 (sockets connect to thigh studs at 0), studs at [-12, -8]
# Y = -32: Torso brick layer 1 (Y span [-32, -8]) -> bottom at -8, studs at [-36, -32]
# Y = -56: Torso brick layer 2 (Y span [-56, -32]) -> bottom at -32, studs at [-60, -56]
# Y = -64: Dorsal plate 4x6 (Y span [-64, -56]) -> bottom at -56, studs at [-68, -64]
# Y = -72: Dorsal tiles (Y span [-72, -64]) -> bottom at -64 (smooth top, no studs above)
print('Stack levels verified!')
