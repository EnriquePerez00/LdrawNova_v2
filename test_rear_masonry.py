import json

# Footing at Y=0, Z in [-20, 20]
# Front curb: 11477 at [0, 0, 20] (yaw 0)
# Center spine: 3710 at [0, -8, 0] and [0, -16, 0]
# Rear masonry wall: 98283 (Brick 1x2 with Masonry Profile) at Z=-20, yaw 180!
# Height of 98283 is 24 LDU (brick).
# Wait, if footing top is at Y=0, placing 98283 at [0, -24, -20] has bounds Y [-24, 0]!
# But curb slopes top is at Y=-16!
# Can 98283 sit at Y=0, going down to Y=24, or sit on footing?
# Let's inspect 98283 bounds:
