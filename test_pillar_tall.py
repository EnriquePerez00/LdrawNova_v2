import json

# Tall pillar to match double-height fence (fence top is at -124, pillar top cap at -160 to -184)
# Y=0: baseplate surface
# Y=-8: Plate 2x2 (3022) [0, -8, 0]
# Y=-32: Brick 2x2 (3003) [0, -32, 0]
# Y=-56: Brick 2x2 (3003) [0, -56, 0]
# Y=-64: Plate 2x2 (3022) [0, -64, 0] (lower collar)
# Y=-88: Brick 2x2 (3003) [0, -88, 0]
# Y=-96: Plate 2x2 (3022) [0, -96, 0] (mid collar)
# Y=-120: Brick 2x2 (3003) [0, -120, 0]
# Y=-144: Brick 2x2 (3003) [0, -144, 0]
# Y=-152: Plate 2x2 (3022) [0, -152, 0] (capital collar)
# Y=-176: Finial 3045 [-10, -176, 10]
plan = {
  "version": 1,
  "author": "Antigravity",
  "sections": [
    {
      "name": "tall_pillar.ldr",
      "description": "Tall pillar test",
      "steps": [
        [
          {"id": "p0", "ref": "3022.dat", "colour": 0, "at": [0, -8, 0]},
          {"id": "b0", "ref": "3003.dat", "colour": 0, "at": [0, -32, 0]},
          {"id": "b1", "ref": "3003.dat", "colour": 0, "at": [0, -56, 0]},
          {"id": "p1", "ref": "3022.dat", "colour": 0, "at": [0, -64, 0]},
          {"id": "b2", "ref": "3003.dat", "colour": 0, "at": [0, -88, 0]},
          {"id": "p2", "ref": "3022.dat", "colour": 0, "at": [0, -96, 0]},
          {"id": "b3", "ref": "3003.dat", "colour": 0, "at": [0, -120, 0]},
          {"id": "b4", "ref": "3003.dat", "colour": 0, "at": [0, -144, 0]},
          {"id": "p3", "ref": "3022.dat", "colour": 0, "at": [0, -152, 0]},
          {"id": "f0", "ref": "3045.dat", "colour": 0, "at": [-10, -176, 10]}
        ]
      ]
    }
  ]
}
with open("test_tall_pillar.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

