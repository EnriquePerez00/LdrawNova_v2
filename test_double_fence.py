import json

# Lower fence: 19121 at Y = -64 (bottom at -16, top at -64)
# Plate 1x4 (3710) tie between fences: sits at Y = -64, height 8 -> top at -72
# Upper fence: 19121 at Y = -120 (bottom at -72, top at -120)
# Top handrail tile 1x4 (2431): sits at Y = -120, height 4 -> top at -124
plan = {
  "version": 1,
  "author": "Antigravity",
  "sections": [
    {
      "name": "double_fence.ldr",
      "description": "Double fence tier test",
      "steps": [
        [
          {"id": "base", "ref": "3001.dat", "colour": 71, "at": [0, 0, 0]},
          {"id": "plate1", "ref": "3710.dat", "colour": 71, "at": [0, -8, 0]},
          {"id": "plate2", "ref": "3710.dat", "colour": 71, "at": [0, -16, 0]},
          {"id": "fence_lower", "ref": "19121.dat", "colour": 0, "at": [0, -64, 0]},
          {"id": "plate_mid", "ref": "3710.dat", "colour": 0, "at": [0, -72, 0]},
          {"id": "fence_upper", "ref": "19121.dat", "colour": 0, "at": [0, -120, 0]},
          {"id": "tile_top", "ref": "2431.dat", "colour": 0, "at": [0, -124, 0]}
        ]
      ]
    }
  ]
}
with open("test_double.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

