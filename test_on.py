import json, subprocess

# Test placing brick on plate vs at
plan = {
  "version": 1,
  "author": "Antigravity",
  "sections": [
    {
      "name": "pillar.ldr",
      "description": "Pillar test",
      "steps": [
        [
          {"id": "b0", "ref": "3003.dat", "colour": 0, "at": [0, 0, 0]},
          {"id": "p0", "ref": "3022.dat", "colour": 0, "on": "b0"},
          {"id": "b1", "ref": "3003.dat", "colour": 0, "on": "p0"}
        ]
      ]
    }
  ]
}
with open("test_on.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

