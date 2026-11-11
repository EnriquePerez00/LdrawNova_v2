import json

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
          {"id": "plate", "ref": "3710.dat", "colour": 71, "on": "base"},
          {"id": "fence", "ref": "19121.dat", "colour": 0, "at": [0, -8, 0]}
        ]
      ]
    }
  ]
}
with open("test_fence.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

