# LdrawNova Fauna & Biomechanical Animal Domain (`profiles/fauna`)

Official domain profile in LdrawNova specialized in procedural generation, anatomical sculpting, and CAD validation of LEGO animals across 5 biological archetypes:
1. **Avian** (Birds, Raptors, Hummingbirds, Peacocks)
2. **Mammal Quadruped** (Felines, Canines, Ungulates, Safari Beasts)
3. **Aquatic** (Fish, Sharks, Cetaceans, Sea Turtles)
4. **Arthropod** (Insects, Beetles, Mantis, Arachnids)
5. **Reptilian & Dinosaurs** (Theropods, Sauropods, Crocodilians)

---

## Architecture & Subsystems

```
profiles/fauna/
├── catalog/
│   ├── fauna_whitelist.json           # 2,219 cataloged parts categorized by semantic function
│   ├── fauna_palette.json             # 77 verified organic colors with biological roles
│   ├── fauna_part_color_combos.json   # 7,431 verified (part, color) combinations
│   └── fauna_sets_summary.json        # 147 cataloged animal sets from Brickclinic DB
├── helpers/
│   ├── __init__.py
│   └── fauna_engine.py                # Biomechanical builder, Mixels kinematic pairs, chiral reflection
├── animal_blueprint_template.json     # Intermediate representation scaffold (Phase 1)
├── instructions_fauna.md              # Antigravity 2.0 specialized system prompt
├── activate_profile.py                # Environment activator and CLI entrypoint
├── test_canonical_fauna.py            # Canonical test suite and CAD verification
└── README.md                          # Documentation
```

---

## 4-Step Assembly Protocol

1. **Phase 1: Morphological Extraction**
   - Translate reference image or prompt into `animal_blueprint.json` (defines archetype, proportions, and kinematic rig).
2. **Phase 2: Skeletal & Kinematic Core**
   - Instantiate `FaunaAnimalBuilder(name, description, archetype)` from `profiles/fauna/helpers/fauna_engine.py`.
   - Mount spine and articulation ball joints (`14704` / `14417`).
3. **Phase 3: SNOT Musculature & Chiral Wings/Limbs**
   - Sculpt organic flesh layers with curved slopes (`11477`, `15068`, `50950`).
   - Use `add_symmetric_pair()` to automatically swap chiral parts (`43723` Left <-> `43722` Right, `29120` <-> `29119`).
4. **Phase 4: CAD Validation & Renders**
   - Build MPD via `ldraw-agent build`.
   - Validate geometry: `ldraw-agent validate --geometry` (ensures 0 rectangular body overlaps).
   - Verify connectivity: `ldraw-agent inspect --contacts all` (ensures `component_count = 1`).
   - Render multi-angle views and physical BOM with LeoCAD.

---

## Quick Start CLI

```bash
# View domain statistics
.venv/bin/python profiles/fauna/activate_profile.py --stats

# Initialize a new animal blueprint
.venv/bin/python profiles/fauna/activate_profile.py --init-blueprint output/my_tiger/animal_blueprint.json

# Run test suite & CAD validation
.venv/bin/python profiles/fauna/activate_profile.py --test
```
