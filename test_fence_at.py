import json

# base brick: at [0, 0, 0] (bounds Y: -4 to 24)
# plate on brick: at [0, -8, 0] (bounds Y: -12 to 0 -> body is [-8, 0], bottom rests on brick top at 0)
# plate 2 on plate 1: at [0, -16, 0] (body is [-16, -8], bottom rests at -8)
# fence 19121: bounds min Y = -4, max Y = 48.
# When placed at Y = y: bounds are [y - 4, y + 48].
# For bottom of fence to rest on top of plate 2 (which is at Y = -16):
# y + 48 = -16  =>  y = -64 !
plan = {
  "version": 1,
  "author": "Antigravity",
  "sections": [
    {
      "name": "fence_test.ldr",
      "description": "Fence stack test",
      "steps": [
        [
          {"id": "base", "ref": "3001.dat", "colour": 71, "at": [0, 0, 0]},
          {"id": "plate1", "ref": "3710.dat", "colour": 71, "at": [0, -8, 0]},
          {"id": "plate2", "ref": "3710.dat", "colour": 71, "at": [0, -16, 0]},
          {"id": "fence", "ref": "19121.dat", "colour": 0, "at": [0, -64, 0]},
          {"id": "tile", "ref": "2431.dat", "colour": 0, "at": [0, -68, 0]}
        ]
      ]
    }
  ]
}
with open("test_fence.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

