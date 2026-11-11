import json

# base brick: at [0, 0, 0] (top surface at Y = 0)
# slope curved 2x1 (11477.dat):
# from part 11477 inspect:
# bounds min Y = -16, max Y = 0.
# So placing at Y = 0 puts bottom at 0 and top curved ridge at -16!
plan = {
  "version": 1,
  "author": "Antigravity",
  "sections": [
    {
      "name": "slope_test.ldr",
      "description": "Slope stack test",
      "steps": [
        [
          {"id": "base", "ref": "3001.dat", "colour": 71, "at": [0, 0, 0]},
          {"id": "slope_f", "ref": "11477.dat", "colour": 71, "at": [0, 0, 20]},
          {"id": "slope_r", "ref": "11477.dat", "colour": 71, "at": [0, 0, -20], "yaw": 180}
        ]
      ]
    }
  ]
}
with open("test_slope.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

