---
name: ldraw-fauna
description: >-
  Specialized skill for creating, sculpting, and validating 3D LEGO animal sets (profiles/fauna)
  across 5 biological archetypes (avian, quadruped mammals, aquatic creatures, arthropods/insects,
  and dinosaurs/reptiles) with Mixels ball joints, SNOT organic musculature, and CAD validation.
---

# Biomechanical Fauna & Animal Construction Skill (`profiles/fauna`)

This skill empowers Antigravity to create, articulate, and validate 3D LEGO animal sculptures and Creator 3-in-1 style creatures, adhering to the physical connectivity rules (`component_count = 1`), collision avoidance (`0 rectangular body overlaps`), and verified catalogs from 147 official animal sets.

---

## The 5 Biological Archetypes

1. **Avian (`avian`)**:
   - *Key Sets:* Kingfisher `10331`, Exotic Parrot `31136`, Birds `21301`, Fawkes `76394`, Hedwig `75979`.
   - *Architecture:* SNOT thoracic core, multi-axis neck with towball `14704`/`14417`, laminar wedge flight wings (`43723`/`43722`), organic talons on branch perches.
2. **Mammal Quadruped (`mammal_quadruped`)**:
   - *Key Sets:* Majestic Tiger `31129`, Tuxedo Cat `21349`, Red Fox `31154`, Wild Safari `31150`, Adorable Dogs `31137`.
   - *Architecture:* 3-segment flexible spine (cervical, thoracic, lumbar), ball-jointed hips/shoulders, 3-point flexed legs (click hinges `57360`/`53923`), paws with curved slopes (`11477`) and claws (`53451`).
3. **Aquatic (`aquatic`)**:
   - *Key Sets:* Deep Sea Creatures `31088`, Dolphins & Turtle `31128`, Sea Animals `31158`.
   - *Architecture:* Hydrodynamic tapered torso, continuous curved slope flow (`50950`, `11153`), inverted belly slopes (`24201`), pectoral fin hinges, trans-clear display mount (`47`).
4. **Arthropod (`arthropod`)**:
   - *Key Sets:* The Insect Collection `21342`, Surprising Spider `31159`.
   - *Architecture:* 3 tagmata (head, thorax, abdomen), lightweight Bar-and-Clip hexapod legs (`32828`, `11090`, `87994`, `65578`), delicate translucent wings (`47`, `41`).
5. **Reptilian & Dinosaurs (`reptilian_dino`)**:
   - *Key Sets:* Mighty Dinosaurs `31058`, T. rex `31151`, Crocodile `31121`, Dinosaur Fossils `21320`.
   - *Architecture:* Massive counterbalancing caudal tail (4-6 segments), tooth plates (`15208`, `49668`), heavy ball-and-socket hindquarters.

---

## 4-Step Assembly Protocol

### Step 1: Anatomical Intake -> `animal_blueprint.json`
Scaffold using:
```bash
.venv/bin/python profiles/fauna/activate_profile.py --init-blueprint output/<slug>/animal_blueprint.json
```
Define:
- `archetype`: `avian` | `mammal_quadruped` | `aquatic` | `arthropod` | `reptilian_dino`
- `color_palette`: roles for primary coat, underbelly, eyes, mouth interior, claws
- `habitat_pedestal`: perch branch, aquatic coral base, or museum stand

### Step 2: Instantiate `FaunaAnimalBuilder`
```python
from profiles.fauna.helpers.fauna_engine import (
    FaunaAnimalBuilder,
    MorphologicalArchetype,
    ROT_IDENTITY, ROT_Y_90, ROT_Y_180, ROT_Y_270,
    SNOT_FRONT, SNOT_BACK, SNOT_LEFT, SNOT_RIGHT, SNOT_DOWN,
    studs_to_ldu, plates_to_ldu, bricks_to_ldu
)

builder = FaunaAnimalBuilder(
    name="my_animal",
    description="Detailed organic LEGO sculpture",
    archetype=MorphologicalArchetype.AVIAN
)
```

### Step 3: Modular MPD Subassembly
Structure into standard submodels:
- `01_spine_torso.ldr`: central rigid spine and SNOT brackets (`11211`, `87087`, `44728`).
- `02_cranial_head.ldr`: cranium, snout/beak, curved slopes (`11477`), expressive eyes.
- `03_mandible_jaw.ldr`: lower jaw/mandible with teeth or plates.
- `04_forelimbs_left.ldr` & `05_forelimbs_right.ldr`: bilateral symmetrical limbs/wings/fins. Use `builder.add_symmetric_pair()`.
- `06_hindlimbs_left.ldr` & `07_hindlimbs_right.ldr`: hind legs, talons, or pelvic fins.
- `08_caudal_tail.ldr`: multi-segment tapered tail.
- `09_habitat_perch.ldr`: stable weighted ground, branch, or display pedestal.

Export plan:
```python
plan = builder.export_plan()
plan_path.write_text(json.dumps(plan, indent=2))
```

### Step 4: CAD Validation & Multi-Angle Renders
```bash
# 1. Compile MPD
./ldraw-agent build output/<slug>/animal.plan.json --output output/<slug>/animal.mpd

# 2. Geometry check (0 overlaps)
./ldraw-agent validate output/<slug>/animal.mpd --geometry

# 3. Contact connectivity (component_count = 1)
./ldraw-agent inspect output/<slug>/animal.mpd --contacts all

# 4. Multi-angle renders & BOM
LDRAW_DIR=$HOME/LDraw PATH=$HOME/.local/bin:$PATH ./ldraw-agent render output/<slug>/animal.mpd --outdir output/<slug>/renders
```
