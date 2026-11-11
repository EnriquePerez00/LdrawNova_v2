# Workspace Guidelines: LdrawNova

## Virtual Environment & Execution Rules
Whenever executing commands or running scripts in this repository:
1. **Always activate the Python virtual environment**:
   Use `.venv/bin/python` or prefix terminal commands with `source .venv/bin/activate`.
2. **Always export LDraw Environment Variables**:
   Ensure `LDRAW_DIR=$HOME/LDraw` is exported, and `$HOME/.local/bin` is in `PATH` so `leocad` is accessible.
3. **Hardware Specifications (Apple Silicon M4)**:
   Leverage multi-core CPU capabilities reserving at least 2-4 cores for the system (`max_workers = max(1, os.cpu_count() - 2)`).
   Keep memory allocations safe under the 48 GB Unified Memory envelope.

## Antigravity 2.0 Governance Protocol (Gemini-Only)
Antigravity acts as the primary orchestrator, architect, and compiler for all Ldraw-Nova model creations:
0. **Step 0: Multimodal Profile Detection & Domain Routing**:
   - Detect input signals (image + text) BEFORE part searches or planning:
     - `bust_hd`: Face, portrait, bust, human head/shoulders -> inject exclusively `profiles/bust_hd/instructions_bust_hd.md`, `bust_whitelist.json`, and `bust_engine.py`.
     - `starwars_scifi`: Spaceships, sci-fi vehicles, mechas -> inject exclusively `profiles/starwars/instructions_starwars.md`, `starwars_whitelist.json`, `starwars_palette.json`, and `starwars_engine.py`.
     - `fauna`: Animals, birds, aquatic/marine creatures, mammals, insects/arthropods, dinosaurs/reptiles -> inject exclusively `profiles/fauna/instructions_fauna.md`, `fauna_whitelist.json`, `fauna_palette.json`, and `fauna_engine.py`.
     - `brand_logo`: Corporate brand logos, lettermarks, typography, crests, emblems, 2.5D plaques -> inject exclusively `profiles/brand_logo/instructions_brand_logo.md`, `brand_logo_whitelist.json`, `brand_logo_palette.json`, and `brand_logo_engine.py`.
     - **Ambiguity Rule**: If input combines domains without `@perfil`, ask in 1 line: *"¿Prefieres un paradigma constructivo de Logotipo Corporativo (`@brand_logo`), Escultura Biomecánica (`@fauna`), Escultura por capas (`@bust_hd`) o de Panelado angular (`@starwars_scifi`)?"*
   - Always persist `"profile": "<slug>"` in the header of `plan.json`.
1. **Zero External API Dependency**: Exclusively use Antigravity 2.0 native Gemini models (Flash / Pro / Coder) and local determinism. Do not rely on external paid API keys.
2. **Three-Tier Architecture & Physical Connectivity (CRITICAL)**:
   - **Tier 1 (Continuous Stacking & Rigid Core)**: Every upright part MUST strictly rest on the top plane of the supporting part:
     $$y_{\text{upper}} = y_{\text{lower}} - \text{body\_height\_of\_upper\_part}$$
     (Plate body = 8 LDU, Brick body = 24 LDU). Internal spine/core extends from base through upper levels. Seams cross-bonded (`component_count = 1`).
   - **Tier 2 (Real SNOT Anchorages)**: Horizontal orientations must strictly anchor to SNOT adapter bricks (`87087.dat`, `11211.dat`) or brackets (`99781.dat`, `44728.dat`) embedded in the core grid.
   - **Tier 3 (Exterior Skin & Micro-Detailing)**: Use compound curved slopes (`50950`, `11477`) and smooth tiles (`2431`, `3068b`) to eliminate raw exposed studs and provide high visual fidelity (greebling).
   - **MANDATORY ANTI-FRAGMENTATION & SCALE RULE (Anti-1x1 Mosaic Anti-Pattern)**:
     - **Surface-First Part Sizing**: Surfaces and structures MUST be covered using the largest fitting official LEGO pieces available in the catalog (e.g. Plates 2x4, 2x6, 2x8, 4x6, 4x8; Wedge plates 41769/41770, 43720/43721; Wings 3933/3934).
     - **Strict Ban on Volume Subdividing**: NEVER substitute a single medium/large piece ($W \times L$) with multiple smaller pieces ($1\times 1$ plates or tiles) merely to artificially inflate the part count without adding structural or geometric differentiation. Subdividing flat co-planar surfaces into micro-pieces adds zero visual/architectural value and is explicitly forbidden across all profiles.
     - **Scale-Driven Part Count**: To achieve higher piece counts (e.g., 500, 1000+ UCS), scale up the overall physical dimensions (wingspan, fuselage length, internal cockpit detailing, mechanical hinging, 4x4 turbine assemblies) and add real functional greebling and angled panels, rather than fragmenting existing geometric envelopes.
3. **Modular Subassembly & Prototyping (`templates/modular_generator_template.py`)**:
   - Write modular Python generators (`output/<slug>/generate.py`) leveraging `ldraw_tools.architecture.Module` (local coordinates: X/Z in studs, h in LDU upwards, facing -Z).
   - Support `--main <submodule>` to prototype and verify complex modules in `proto/` prior to full-scene assembly.
4. **Design Brief & Optical Layering**:
   - Create `design-brief.md` before coding: establish silhouette, focal hierarchy (primary, secondary, accents), and depth layering (shadow colors under eaves, recessed features, varied elevations).
5. **Deterministic Assembly, Contact Inspection, Overlap Triage & Mandatory Render Suite**:
   - Compile via `./ldraw-agent build` in the virtual environment.
   - Run `./ldraw-agent validate --geometry` and `./ldraw-agent inspect --contacts all`.
   - Record and triage physical clearances in `overlap-triage.txt`.
   - **MANDATORY RENDERING (All Models by Default)**: Always run `./ldraw-agent render <model>.mpd --outdir output/<slug>/renders/ --views home front right top --timeout 180`.
     - `home.png`: Perspectiva 3D angular (isométrica) que exhibe el volumen completo, profundidad y tridimensionalidad del modelo.
     - `front.png` / `right.png` / `top.png`: Vistas ortogonales (alzado, perfil, planta) para verificación dimensional y proporciones.
     - Generar `renders/COMPARISON.md` contrastando cada vista renderizada contra la imagen Ground Truth (GT) de referencia oficial.
     - Extraer el BOM físico oficial de LeoCAD (`leocad-bom.csv`) y verificar que todas las piezas están en el whitelist del perfil.

## Mandatory Vision & Intake Protocol (The 6-Question Design Gate)
Whenever receiving a reference image or prompt for a new design, Antigravity MUST explicitly analyze, extract, and align with the user on this 6-question gate before writing assembly code:
1. **Design Brief & Silueta**: ¿Se ha creado `design-brief.md` con silueta distintiva, paleta funcional con colores de sombra y jerarquía focal (1º plano, 2º plano, acentos)?
2. **Piezas Especializadas vs Bricks Estándar**: ¿Se ha buscado en el catálogo (`./ldraw-agent catalog parts`) piezas de acabado (tiles, curved slopes `50950`/`11477`, brackets `99781`) para evitar bloques planos monótonos?
3. **Submódulos Complejos en `proto/`**: ¿Se han identificado y modelado los 2 o 3 elementos más desafiantes como submódulos independientes en `proto/` usando `generate.py --main <submodulo>`?
4. **Relieve y Estratificación**: ¿La base, terreno o estructura tiene relieve real (desniveles, aceras elevadas, agua hundida a $-8\text{ LDU}$, molduras y cornisas salientes)?
5. **Acabado de Superficies & Juntas**: ¿Las superficies visibles están rematadas con losetas lisas (*tiles*) o juntas deliberadas que simulen texturas reales (tejas, tablas)?
6. **Solidez Estructural del Núcleo**: ¿El núcleo interno es continuo, trabado e indivisible desde la base hasta la cima garantizando `component_count = 1`?
