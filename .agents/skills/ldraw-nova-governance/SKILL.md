---
name: ldraw-nova-governance
description: >-
  Standard operating procedure to govern Ldraw-Nova directly from Antigravity 2.0
  using native Gemini models for visual deconstruction, official .dat catalog binding,
  generate.py scripting, and ./ldraw-agent CAD build/render validation.
---

# Ldraw-Nova Antigravity Governance Protocol

This skill formalizes the end-to-end pipeline to design, prototype, build, and verify high-realism LEGO models directly within Antigravity 2.0, adhering to the advanced engineering strategies proven in `examples/sakura-garden` and `examples/spaceship-atlas`.

## Core Philosophy & Anti-Floating Constraints
1. **Zero External API Dependency**: Exclusively use Antigravity 2.0 native Gemini models and local determinism.
2. **Three-Tier Physical Architecture**:
   - **Tier 1 (Rigid Structural Spine/Core)**: Continuous core column (Bricks 2x2/2x4, Technic pins/beams) extending from the base through the upper levels. Continuous stacking: $y_{\text{upper}} = y_{\text{lower}} - \text{body\_height\_upper}$. Seams must be cross-bonded (`component_count = 1`).
   - **Tier 2 (SNOT Mounts & Functional Substrate)**: Real SNOT adapter bricks (`87087.dat`, `11211.dat`) or brackets (`99781.dat`, `44728.dat`) embedded in the core grid.
   - **Tier 3 (Exterior Skin & Greebling)**: Tiles (`2431`, `3068b`) to eliminate unfinished exposed studs, compound curved slopes (`50950`, `11477`) to create authentic organic contours, and high-density micro-detailing (greebles) to convey scale and realism.
3. **Layering & Depth**: Avoid flat planar surfaces. Recess windows and panels, add overhangs with shadow colors (e.g., Dark Red under red roofs), and structure terrain elevations (e.g. recessed water beds below turf level).

---

## 5-Phase Workflow

### Phase 1: Creative Direction & The 6-Question Design Intake
Before writing any placement code or when inspecting a new reference image/prompt, Antigravity MUST extract and answer this mandatory **6-Question Design Gate**:

1. **¿He creado `design-brief.md` con silueta, paleta de sombras y jerarquía focal?**
   - *Silueta:* 2 o 3 masas principales legibles en thumbnail.
   - *Jerarquía focal:* 1º foco (protagonista), 2º foco (apoyo), acentos (greebles, iluminación).
   - *Paleta:* roles cromáticos incluyendo tonos de sombra (Dark Red bajo voladizos, Dark Blue bajo agua).
2. **¿He buscado en el catálogo piezas especializadas (tiles, slopes curvos, brackets) antes de usar bricks estándar?**
   - Evitar caras planas con simples bricks 2x4. Consultar `./ldraw-agent catalog parts` para slopes compuestos (`50950`, `11477`), brackets (`99781`, `44728`), y tiles (`2431`, `3068b`).
3. **¿He modelado los 2 o 3 elementos más complejos como submódulos independientes en `proto/`?**
   - Identificar los núcleos difíciles (aleros, góndolas, copas de árboles, cabinas) y prototiparlos de forma aislada con `generate.py --main <submodulo>`.
4. **¿El terreno o la base tiene relieve y estratificación (desniveles, aceras, agua hundida)?**
   - Romper la base plana uniforme: agua hundida a $-8\text{ LDU}$, bordillos a $+8\text{ LDU}$, podios a $+24\text{ LDU}$, fachadas con molduras salientes.
5. **¿Las superficies visibles están rematadas con losetas lisas (tiles) y juntas deliberadas?**
   - Tapar espárragos visibles no deseados; disponer las juntas entre losetas y cuñas para que sugieran hileras de tejas, sillería o paneles de blindaje.
6. **¿El núcleo interno es sólido e indivisible (`component_count = 1`)?**
   - Garantizar el apilamiento estricto $y_{\text{upper}} = y_{\text{lower}} - \text{body\_height}$ y traba de juntas desde la base hasta la cima.

### Phase 2: Catalog Discovery & Greeble Curation
1. Search official LDraw parts (`~/LDraw/parts/` / `data/ldraw-info.db`):
   ```bash
   ./ldraw-agent catalog parts "<search-term>" --category <category> --limit 5
   ```
2. Verify part origins and bounding envelopes:
   ```bash
   ./ldraw-agent part <part_reference>
   ```
3. Generate visual part-boards if selecting complex alternatives:
   ```bash
   ./ldraw-agent part-board <part1> <part2> --colour <colour_code> --outdir output/<design-slug>/part-board
   ```

### Phase 3: Modular Synthesis & Submodel Prototyping (`proto/`)
1. Create `output/<design-slug>/generate.py` based on `templates/modular_generator_template.py`.
2. Use the local coordinate abstraction `ldraw_tools.architecture.Module`:
   - $X, Z$ in studs ($20\text{ LDU}$), $h$ in LDU upwards ($Y = -h$).
   - Base of each module at $h=0$, facing $-Z$.
3. Prototype the 1-2 most challenging subassemblies first in `proto/`:
   ```bash
   .venv/bin/python output/<design-slug>/generate.py --main <submodule_name> --build --render
   ```
4. Visually inspect the rendered prototype in `output/<design-slug>/proto/<submodule_name>/renders/` and adjust geometry until proportions and fit are proven.

### Phase 4: Master Assembly, Build & Overlap Triage
1. Assemble modules into the master scene in `generate.py`.
2. Compile the full scene:
   ```bash
   .venv/bin/python output/<design-slug>/generate.py --build
   ```
3. Run comprehensive contact and collision inspection:
   ```bash
   ./ldraw-agent validate output/<design-slug>/<slug>.mpd --geometry --detail summary
   ./ldraw-agent inspect output/<design-slug>/<slug>.mpd --contacts all --detail summary
   ```
4. **Collision Triage (`overlap-triage.txt`)**:
   - If collisions occur, analyze whether they are fatal physical penetrations or standard LDraw bounding-box tolerances (e.g. clip/bar engagements, angled bracket lips).
   - Resolve fatal collisions in `generate.py`. Record accepted structural clearances in `overlap-triage.txt`.

### Phase 5: Mandatory Multi-Angle Renders & BOM Extraction
1. **Always render full 3D perspective and isometric/orthogonal review views by default**:
   ```bash
   ./ldraw-agent render output/<design-slug>/<slug>.mpd --outdir output/<design-slug>/renders --views home front right top --timeout 180
   ```
   - `home.png`: Render tridimensional en perspectiva (isométrica) con volumen y profundidad angular.
   - `front.png`, `right.png`, `top.png`: Vistas ortogonales (alzado, perfil, planta) para análisis dimensional y validación de proporciones.
2. **Generate `renders/COMPARISON.md`** comparing each rendered view against the official Ground Truth (GT) reference images. Include side-by-side visual notes on fidelity, color accuracy (CIELAB ΔE), and geometric alignment.
3. Extract and verify physical Bill of Materials:
   ```bash
   ./ldraw-agent bom output/<design-slug>/<slug>.mpd --report output/<design-slug>/bom.json
   ```
4. Deliver the final summary with direct links to the design brief, renders, COMPARISON.md, BOM, and assembly file.
