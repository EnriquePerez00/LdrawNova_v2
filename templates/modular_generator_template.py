"""
Modular Ldraw-Nova Generator Template.
Standard operating template following the sakura-garden and spaceship-atlas architecture.

Features:
- Local coordinate authoring via ldraw_tools.architecture.Module:
    * X and Z in studs (1 stud = 20 LDU)
    * h in LDU upwards (LDraw Y = -h)
    * Each module has its base at h = 0 and faces -Z
- Three-Tier Assembly:
    1. Tier 1: Solid structural spine/core (continuous stacking, clutch & cross-bonding)
    2. Tier 2: SNOT brackets/adapters (87087, 11211, 99781, 44728)
    3. Tier 3: Exterior skin & micro-detailing (curved slopes 50950/11477, tiles, greebles)
- Support for fast unit prototyping via `--main <module_name>` flag:
    * Emits isolated plan into proto/<module_name>.plan.json for fast CAD render/inspection.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Repository root discovery
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ldraw_tools.architecture import Module

# -----------------------------------------------------------------------------
# PALETTE DEFINITIONS (Functional Roles)
# -----------------------------------------------------------------------------
C = {
    # Structural Core (Hidden / Semi-hidden)
    "core": 72,          # Dark Bluish Gray (Rigid internal spine)
    "sub_structure": 71,  # Light Bluish Gray (Foundations & brackets)

    # Primary & Secondary Surfaces
    "primary": 4,        # Red / Main body color
    "secondary": 0,      # Black / Secondary surfaces & framing
    "trim": 15,          # White / Architectural trim & plaster

    # Depth & Optical Illusions
    "shadow": 320,       # Dark Red (Shadows under eaves, recessed panels)
    "accent_metal": 297, # Pearl Gold (Finials, bells, mechanical nozzles)

    # Landscaping / Environment / Translucents (if applicable)
    "ground": 19,        # Tan (Pavements, terrain top)
    "trans_glass": 41,   # Trans Medium Blue (Windows or water surface)
    "water_bed": 272,    # Dark Blue (Deep bed under transparent water)
}

# -----------------------------------------------------------------------------
# SUBMODULE DEFINITIONS (Coordenadas Locales: X/Z en studs, h en LDU hacia arriba)
# -----------------------------------------------------------------------------

def build_submodule_example() -> Module:
    """
    Example of a reusable, self-contained subassembly.
    Base at h = 0, facing -Z.
    """
    mod = Module("submodule_sample", "Prototipo de subensamble modular")

    # Tier 1: Base estructural sólida
    mod.step()
    mod.add("3003", C["core"], x=0, h=0, z=0, purpose="Columna central 2x2")

    # Tier 2: SNOT Adapter en h = 24
    mod.step()
    # 87087.dat = Brick 1x1 with stud on 1 side
    mod.add("87087", C["sub_structure"], x=0, h=24, z=0, yaw=180, purpose="SNOT adapter hacia el frente")

    # Tier 3: Acabado estético y greebles
    mod.step()
    # 54200.dat = Cheese slope 1x1
    mod.add("54200", C["primary"], x=0, h=48, z=0, yaw=180, purpose="Bisel superior")
    # Loseta lisa para tapar espárragos
    mod.add("3069b", C["accent_metal"], x=0, h=48, z=-1, purpose="Loseta dorada 1x2")

    return mod


def build_scene() -> Module:
    """
    Main Assembly: Combines modules onto the baseplate/structural chassis.
    """
    scene = Module("scene_main", "Ensamblaje maestro de la escena")

    # 1. Base / Terreno
    scene.step()
    # Placa base 16x16 (Plate 16x16 = 91405.dat) en h = 0
    scene.add("91405", C["ground"], x=0, h=0, z=0, purpose="Placa base de soporte")

    # 2. Instanciación de submódulos en posiciones relativas
    scene.step()
    sample_a = build_submodule_example()
    # Colocar módulo A en la posición izquierda (X = -4 studs, Z = 0)
    scene.add(sample_a, 16, x=-4, h=8, z=0, purpose="Submódulo lateral izquierdo")

    # Colocar módulo B en la posición derecha (X = +4 studs, Z = 0)
    sample_b = build_submodule_example()
    scene.add(sample_b, 16, x=4, h=8, z=0, purpose="Submódulo lateral derecho")

    return scene


# -----------------------------------------------------------------------------
# CLI & COMPILATION HARNESS
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generador Ldraw-Nova Modular")
    parser.add_argument(
        "--main",
        type=str,
        default=None,
        help="Nombre de un submódulo para prototipado rápido en proto/ (ej. submodule_sample)",
    )
    parser.add_argument("--build", action="store_true", help="Ejecutar ./ldraw-agent build tras generar")
    parser.add_argument("--render", action="store_true", help="Ejecutar ./ldraw-agent render tras build")
    args = parser.parse_args()

    outdir = Path(__file__).resolve().parent

    if args.main:
        # Prototipado unitario en proto/
        proto_dir = outdir / "proto" / args.main
        proto_dir.mkdir(parents=True, exist_ok=True)
        plan_file = proto_dir / f"{args.main}.plan.json"
        mpd_file = proto_dir / f"{args.main}.mpd"
        render_dir = proto_dir / "renders"

        # Registrar módulos disponibles
        registry = {
            "submodule_sample": build_submodule_example,
        }

        if args.main not in registry:
            print(f"Error: Módulo '{args.main}' no encontrado en el registro. Disponibles: {list(registry.keys())}")
            sys.exit(1)

        root_module = registry[args.main]()
        plan_data = root_module.plan()
        print(f"-> Generando prototipo de submódulo: {args.main}")
    else:
        # Ensamblaje global
        slug = outdir.name
        plan_file = outdir / f"{slug}.plan.json"
        mpd_file = outdir / f"{slug}.mpd"
        render_dir = outdir / "renders"

        root_module = build_scene()
        plan_data = root_module.plan()
        print(f"-> Generando escena maestra: {slug}")

    # Guardar .plan.json
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Plan guardado: {plan_file}")

    # Opciones de compilación automática
    env = os.environ.copy()
    if "LDRAW_DIR" not in env:
        env["LDRAW_DIR"] = str(Path.home() / "LDraw")
    env["PATH"] = f"{Path.home()}/.local/bin:{env.get('PATH', '')}"

    if args.build or args.render:
        print("-> Compilando con ./ldraw-agent build...")
        cmd_build = [
            "./ldraw-agent", "build", str(plan_file),
            "--output", str(mpd_file),
            "--detail", "summary"
        ]
        res = subprocess.run(cmd_build, cwd=REPO_ROOT, env=env)
        if res.returncode != 0:
            print(f"✗ Error al compilar {mpd_file}")
            sys.exit(res.returncode)
        print(f"✓ MPD compilado: {mpd_file}")

    if args.render:
        print("-> Renderizando vistas técnicas con LeoCAD (4 vistas canónicas)...")
        cmd_render = [
            "./ldraw-agent", "render", str(mpd_file),
            "--outdir", str(render_dir),
            "--views", "home", "front", "right", "top",
            "--timeout", "180"
        ]
        res = subprocess.run(cmd_render, cwd=REPO_ROOT, env=env)
        if res.returncode == 0:
            print(f"✓ Renders listos en: {render_dir}")
            print(f"  Vistas generadas: home.png (isométrica), front.png (alzado), right.png (perfil), top.png (planta)")
            print(f"  BOM exportado: {render_dir}/leocad-bom.csv")


if __name__ == "__main__":
    main()
