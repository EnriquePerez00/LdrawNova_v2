import json

# Prototype 1 picket module of GT ornamental ironwork:
# - Base socket: 4070.dat (Brick 1x1 with headlight) or 85861 (Plate 1x1 Round with Open Stud)
# - Vertical bar: 30374.dat (Bar 4L, length 80 LDU)
# - Central nodule: 4733.dat (Brick 1x1 with Studs on 4 Sides)
# - Symmetrical outward horns: 13564.dat (Animal Cow Horn 2.25L) or 87695.dat (Animal Cattlehorns)
plan = {
  "version": 1,
  "author": "Antigravity",
  "sections": [
    {
      "name": "motif_proto.ldr",
      "description": "Prototype GT ironwork motif",
      "steps": [
        [
          {"id": "base_socket", "ref": "85861.dat", "colour": 0, "at": [0, 0, 0]},
          {"id": "bar_vert", "ref": "30374.dat", "colour": 0, "at": [0, -80, 0]},
          {"id": "nodule", "ref": "4733.dat", "colour": 0, "at": [0, -40, 0]},
          {"id": "horns", "ref": "87695.dat", "colour": 0, "at": [0, -40, 0]}
        ]
      ]
    }
  ]
}
with open("test_motif.plan.json", "w") as f:
    json.dump(plan, f, indent=2)

