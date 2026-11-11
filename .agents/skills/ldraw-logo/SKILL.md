---
name: ldraw-logo
description: >-
  Specialized skill for creating, designing, and validating 3D LEGO corporate brand logos, lettermarks,
  and crests (profiles/brand_logo) from 2D/3D ground-truth reference images, with CIELAB ΔE color matching,
  macaroni/curved slope geometry, and CAD validation.
---

# Corporate Brand Logo & Typography Skill (`profiles/brand_logo`)

This skill empowers Antigravity to transform 2D and 3D corporate logo reference images into official, structurally sound LEGO models. It guarantees strict brand color fidelity via CIELAB $\Delta E_{00}$ quantization, high-end surface finishes without exposed raw studs (using smooth tiles and curved slopes), and structural integrity (`component_count = 1`, `0 rectangular body overlaps`).

---

## The 4 Brand Logo Archetypes

1. **Bas-Relief & Framed Plaque (`bas_relief_plaque`)**:
   - *Use Case:* Corporate crests, wall-mounted display plaques, horizontal wordmarks with layered backgrounds (e.g. Google, FedEx, Microsoft, LEGO Art style).
   - *Architecture:* Interlocked structural base plate, framed bezel (`05_bezel_frame.ldr`), tiered relief layers ($0\text{ LDU}$, $+8\text{ LDU}$, $+16\text{ LDU}$, $+24\text{ LDU}$) using plates and smooth tiles. Integrated rear hanger plate or desk kickstand.

2. **Geometric Emblem & Round Crest (`geometric_emblem`)**:
   - *Use Case:* Circular, radial, and polygonal emblems (e.g. BMW, Mercedes, Target, Mitsubishi, Volkswagen).
   - *Architecture:* Radial symmetry, round corner macaroni tiles (`27925`, `27507`, `48092`), quarter-round tiles (`25269`), round plates (`4073`, `98138`), and multi-directional bracket/turntable cores.

3. **Organic Swoosh & Smooth Isotype (`organic_swoosh`)**:
   - *Use Case:* Continuous aerodynamic curves, fluid silhouettes, animal or object silhouettes (e.g. Apple, Nike swoosh, Twitter/X, Jaguar).
   - *Architecture:* SNOT studs-not-on-top spine, compound curved slopes (`11477`, `15068`, `50950`), inverted curved slopes (`24201`), and wedge curved tiles (`29119`/`29120`) eliminating stepped pixelation.

4. **Monogram & Free-standing 3D Lettering (`monogram_freestanding`)**:
   - *Use Case:* Three-dimensional freestanding lettermarks and sculptures (e.g. Netflix 'N', Adobe 'A', Bentley 'B', Chanel monogram).
   - *Architecture:* Rigid multi-stud upright columns, 4-way SNOT wrapping with brackets (`99781`, `44728`, `11211`), weighted museum pedestal in Pearl Dark Gray or Black.

---

## 4-Step Assembly Protocol

### Step 1: Image Analysis -> `logo_blueprint.json`
Scaffold the logo blueprint:
```bash
.venv/bin/python profiles/brand_logo/activate_profile.py --init-blueprint output/<slug>/logo_blueprint.json
```
Analyze the GT image and define:
- `archetype`: `bas_relief_plaque` | `geometric_emblem` | `organic_swoosh` | `monogram_freestanding`
- `dimensions`: Width, height, depth in studs ($1\text{ stud} = 20\text{ LDU}$)
- `brand_colors`: Extracted RGB/HEX matched to official LDraw IDs using `BrandLogoColorMatcher`
- `layer_hierarchy`: Base substrate, background, graphic isotype, typography/lettermark, bezel frame

### Step 2: Instantiate `BrandLogoBuilder`
```python
from profiles.brand_logo.helpers.brand_logo_engine import (
    BrandLogoBuilder,
    LogoArchetype,
    studs_to_ldu, plates_to_ldu, bricks_to_ldu,
    ROT_IDENTITY, ROT_Y_90, ROT_Y_180, ROT_Y_270,
    SNOT_FRONT, SNOT_BACK, SNOT_LEFT, SNOT_RIGHT, SNOT_DOWN
)

builder = BrandLogoBuilder(
    name="my_brand_logo",
    description="Official 3D LEGO corporate brand sculpture",
    archetype=LogoArchetype.BAS_RELIEF_PLAQUE,
    width_studs=32,
    height_studs=32
)
```

### Step 3: Modular MPD Subassembly
Structure into standard submodels:
- `01_structural_canvas.ldr`: Interlocked rigid backing plates and support brackets.
- `02_background_substrate.ldr`: Base color tiles or recessed negative space.
- `03_isotype_core.ldr`: Main graphic symbol built with macaroni tiles and curved slopes.
- `04_typography_wordmark.ldr`: Modular lettering with uniform stroke thickness ($8\text{ LDU}$ / $20\text{ LDU}$).
- `05_bezel_frame.ldr`: Architectural perimeter frame, mitered corner slopes, or weighted display pedestal.

Export plan:
```python
plan = builder.export_plan()
plan_path.write_text(json.dumps(plan, indent=2))
```

### Step 4: CAD Validation & High-Fidelity Renders
```bash
# 1. Compile MPD
./ldraw-agent build output/<slug>/logo.plan.json --output output/<slug>/logo.mpd

# 2. Geometry check (0 overlaps)
./ldraw-agent validate output/<slug>/logo.mpd --geometry

# 3. Contact connectivity (component_count = 1)
./ldraw-agent inspect output/<slug>/logo.mpd --contacts all

# 4. Multi-angle renders (4 canonical isometric views) & BOM
LDRAW_DIR=$HOME/LDraw PATH=$HOME/.local/bin:$PATH ./ldraw-agent render \
  output/<slug>/logo.mpd --outdir output/<slug>/renders \
  --views home front right top --timeout 180

# 5. Generate Ground Truth comparison
# Create renders/COMPARISON.md contrasting each view with official GT reference images.
```
