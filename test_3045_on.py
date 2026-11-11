import json

# Check 3045 on 3022
plan = {
  "version": 1,
  "author": "Antigravity",
  "sections": [
    {
      "name": "pillar_top.ldr",
      "description": "Pillar top test",
      "steps": [
        [
          {"id": "plate", "ref": "3022.dat", "colour": 0, "at": [0, 0, 0]},
          {"id": "finial", "ref": "3045.dat", "colour": 0, "at": [-10, -24, 10]}
        ]
      ]
    }
  ]
}
with open("test_top.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

