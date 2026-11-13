# Build Helpers Usage Guide

Quick reference for using `ldraw_tools.build_helpers` to generate grid-aligned LEGO models.

## Import

```python
from ldraw_tools.build_helpers import (
    studs, plates, bricks,              # Unit converters
    placement, stack_on,                 # Basic placement
    ring, octagon, pyramid, apex_point   # Geometric primitives
)
```

## Unit Conversions

Always convert studs/plates to LDU before emitting coordinates.

```python
from ldraw_tools.build_helpers import studs, plates

# These functions ensure grid alignment
x = studs(2.5)       # → 50 LDU (correct!)
y = plates(3)        # → 24 LDU (one brick height, correct!)

# BAD: don't emit raw studs as LDU
# x = 2.5              # → interpreted as 2.5 LDU (wrong, ~0.125 studs)
```

## Simple Placement

Create a single part at a grid-aligned position.

```python
from ldraw_tools.build_helpers import placement, studs, plates

part = placement(
    pid="base_1",
    ref="3022.dat",           # 2×2 plate
    colour=16,                # Dark gray
    x=studs(0),
    y=plates(0),
    z=studs(0),
    purpose="Foundation base plate"
)
# → {"id": "base_1", "ref": "3022.dat", "colour": 16, "at": [0, 0, 0], "purpose": ...}
```

## Stacking with "on" Mechanism

Stack pieces on top of each other with automatic Y-offset calculation.

```python
from ldraw_tools.build_helpers import stack_on, plates

# First placement (base)
placements = [placement("base", "3022.dat", 16, studs(0), plates(0), studs(0))]

# Stack on base
placements.append(stack_on(
    pid="layer_1",
    support_id="base",        # Must reference earlier placement
    ref="3001.dat",           # 2×4 brick
    colour=4,                 # Red
    offset_studs=(0, 0)       # No horizontal offset
))

# Builder automatically calculates Y offset based on base height
# → {"id": "layer_1", "ref": "3001.dat", "colour": 4, "on": "base", "offset_studs": [0, 0]}
```

## Ring / Octagon Arrangements

Generate circular patterns, useful for pyramids, cylinders, crowns.

```python
from ldraw_tools.build_helpers import ring, octagon, studs, plates

# Octagonal ring (8 parts)
parts = octagon(
    pid_prefix="crown",
    ref="3070b.dat",          # Slope 45° brick
    colours=[73, 1],          # Alternate blue/bright blue
    radius_studs=3.0,         # 60 LDU from center
    y=plates(-10),            # Position in Y
    purpose_template="Crown facet {i}"
)
# → List of 8 placement dicts, each with yaw=(angle+90)° for radial orientation

# Custom ring (arbitrary count)
parts = ring(
    pid_prefix="halo",
    ref="2540.dat",           # Slope brick
    colours=[9, 9, 9],        # Dark blue (will cycle if count > 3)
    radius_studs=2.5,
    y=plates(-5),
    count=12,                 # 12 parts (pentagon arrangement)
    start_angle_deg=0,        # Starting angle
    purpose_template="Halo segment {i} at {angle}°"
)
```

## Pyramid Structures

Generate faceted pyramids with tapering rings (e.g., gems, diamond shapes).

```python
from ldraw_tools.build_helpers import pyramid, studs, plates

parts = pyramid(
    pid_prefix="gem",
    ref_by_layer=[
        "2399.dat",   # Wedge 3×4
        "2399.dat",   # Wedge 3×4
        "4858.dat",   # Wedge 4×4 (wider)
    ],
    colours_by_layer=[
        [73, 1],      # Blue / bright blue alternating
        [89, 110],    # Blue violet / violet
        [22],         # Purple
    ],
    radii_studs=[3.0, 2.0, 1.0],     # Decreasing radius (tapering)
    y_bottom=plates(-10),             # Bottom Y position
    heights_studs=[1, 1, 1],          # Height between layers in studs
    count_per_layer=8,                # 8 facets per ring
    purpose_template="Gem layer {layer_idx}: radius={radius_studs} studs"
)
# → List of (8×3) = 24 placements forming a tapered pyramid
```

## Validation

Check if coordinates are grid-aligned before emitting.

```python
from ldraw_tools.build_helpers import validate_grid_alignment, studs, plates

# Check alignment
if validate_grid_alignment(studs(2.5), studs(1.0), plates(3)):
    print("Coordinates are grid-aligned ✓")
else:
    print("WARNING: Coordinates deviate from grid!")

# Using the helpers automatically ensures alignment:
aligned_x = studs(2.5)   # Always returns 50.0 (grid-aligned)
aligned_y = plates(3)    # Always returns 24.0 (grid-aligned)
```

## Complete Example: Build a Simple Tower

```python
from ldraw_tools.build_helpers import placement, stack_on, studs, plates
import json
from pathlib import Path

def build_tower():
    placements = []
    
    # Base (white plate)
    placements.append(placement(
        "base",
        "3022.dat",         # 2×2 plate
        16,                 # Dark gray
        studs(0), plates(0), studs(0)
    ))
    
    # Stack 5 red bricks on top
    for i in range(5):
        placements.append(stack_on(
            f"brick_{i}",
            support_id="base" if i == 0 else f"brick_{i-1}",
            ref="3001.dat",   # 2×4 brick
            colour=4,         # Red
            offset_studs=(0, 0)
        ))
    
    return placements

# Generate plan JSON
plan = {
    "version": 1,
    "author": "builder-script",
    "profile": "test",
    "sections": [{
        "name": "tower.ldr",
        "description": "Simple stacked tower",
        "author": "builder-script",
        "steps": [build_tower()]
    }]
}

Path("tower.plan.json").write_text(json.dumps(plan, indent=2))
print("✓ Plan generated: tower.plan.json")
```

Then build and render:

```bash
./ldraw-agent build tower.plan.json --output tower.mpd
./ldraw-agent render tower.mpd --outdir renders --views home front
```

## Troubleshooting

### Problem: "All pyramid layer lists must have the same length"

**Cause:** Mismatched array sizes in `pyramid()`

**Fix:**
```python
# WRONG: different lengths
pyramid(...,
    ref_by_layer=["part1", "part2"],
    colours_by_layer=[[73], [1], [16]],  # 3 items vs 2 refs
    radii_studs=[3.0, 2.0],              # 2 items
)

# CORRECT: all same length
pyramid(...,
    ref_by_layer=["part1", "part2", "part3"],
    colours_by_layer=[[73], [1], [16]],
    radii_studs=[3.0, 2.0, 1.0],
    heights_studs=[1, 1, 1],
)
```

### Problem: YAW value > 360 validation error

**Cause:** `ring()` emits `yaw = angle_deg + 90` which can exceed 360

**Fix:** Already handled in `build_helpers.py` (line 121):
```python
yaw = (angle_deg + 90) % 360  # Normalize to [0, 360)
```

### Problem: Build fails with "overlapping body envelopes"

**Cause:** Parts placed at same (x, z) without using "on" mechanism

**Fix:** Use `stack_on()` for vertical stacking:
```python
# WRONG: both at (0, 0, 0)
placements.append(placement("p1", "3001.dat", 16, 0, 0, 0))
placements.append(placement("p2", "3001.dat", 4, 0, -24, 0))  # Manually offset Y

# CORRECT: use "on" mechanism
placements.append(placement("p1", "3001.dat", 16, 0, 0, 0))
placements.append(stack_on("p2", "p1", "3001.dat", 4))  # Builder handles Y offset
```

---

## Constants Reference

```python
STUD = 20        # 1 stud = 20 LDU (horizontal)
PLATE = 8        # 1 plate = 8 LDU (vertical)
BRICK = 24       # 1 brick = 24 LDU = 3 plates

# Common part dimensions (in studs):
# Plates: typically 1-4 studs wide/deep, 0.125 studs tall
# Bricks: typically 1-4 studs wide/deep, 1 brick (3 plates) tall
# Slopes/wedges: varied, often 3×4 or 4×4 base
```

---

## See Also

- **Grid Validator:** `ldraw_tools.physical_gate._grid_alignment_diffs()`
- **SAP Diamond Logo Example:** `output/sap-diamond-logo/generate.py`
- **LDraw Coordinate System:** LDRAW spec (Z-axis = depth, Y-axis = height measured downward)
