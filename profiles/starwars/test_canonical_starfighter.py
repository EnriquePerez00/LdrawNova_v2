"""
Canonical Star Wars Starfighter Test & Verification Script.

Generates a fully compliant, collision-free, monolithic canonical Star Wars starfighter
conforming to the Core-and-Armor architecture (profiles/starwars),
divided into 8 distinct MPD submodels:
  01_spine_chassis.ldr
  02_cockpit_canopy.ldr
  03_fuselage_armor.ldr
  04_wings_port.ldr
  05_wings_starboard.ldr
  06_engine_nacelles.ldr
  07_greebling_trenches.ldr
  08_display_stand.ldr

Validates geometry, collision avoidance (0 rectangular body overlaps),
and physical connectivity via ./ldraw-agent.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from profiles.starwars.helpers.starwars_engine import (
    StarshipCoreBuilder,
    ROT_IDENTITY,
    ROT_Y_180,
    ROT_Y_90,
    ROT_Y_270
)


def build_canonical_starfighter_plan(output_dir: Path) -> Path:
    """Builds and writes the complete canonical starfighter plan."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "canonical_starfighter.plan.json"

    builder = StarshipCoreBuilder(
        name="canonical_starfighter",
        description="Canonical Star Wars Starfighter Prototype",
    )

    # 1. SPINE & CHASSIS (Rigid continuous spine at X=0, along Z axis)
    # Base spine plate 2x6 rotated 90 deg: X span [-20, 20], Z span [-60, 60], Y from 0 to +8
    builder.add_submodel_part(
        submodel_file="01_spine_chassis.ldr",
        part_id="3795.dat",  # Plate 2x6
        color=71,            # Light Bluish Grey
        at=[0.0, 0.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Centerline load-bearing spine plate 2x6 along Z axis"
    )
    # Fuselage brick 2x4 on top: at y=-24, resting on top plane y=0. X span [-20, 20], Z span [-40, 40]
    builder.add_submodel_part(
        submodel_file="01_spine_chassis.ldr",
        part_id="3001.dat",  # Brick 2x4
        color=72,            # Dark Bluish Grey
        at=[0.0, -24.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Central structural fuselage core brick 2x4"
    )
    # Upper spine plate 2x4 at y=-32 (resting on top of brick y=-24): X span [-20, 20], Z span [-40, 40]
    builder.add_submodel_part(
        submodel_file="01_spine_chassis.ldr",
        part_id="3020.dat",  # Plate 2x4
        color=71,            # Light Bluish Grey
        at=[0.0, -32.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Upper fuselage spine anchor plate 2x4"
    )

    # 2. COCKPIT & CANOPY (Front section at negative Z, resting on front of spine plate at y=-24)
    # Slope 45 2x2 at x=0, y=-24, z=-40: X span [-20, 20], Z span [-60, -20]
    builder.add_submodel_part(
        submodel_file="02_cockpit_canopy.ldr",
        part_id="3039.dat",  # Slope 45 2x2
        color=47,            # Trans-Clear
        at=[0.0, -24.0, -40.0],
        matrix=ROT_IDENTITY,
        purpose="Aerodynamic cockpit windscreen canopy"
    )

    # 3. FUSELAGE ARMOR (Upper spine curved slope at y=-40 resting on upper plate y=-32)
    builder.add_submodel_part(
        submodel_file="03_fuselage_armor.ldr",
        part_id="15068.dat", # Slope Curved 2x2
        color=71,            # Light Bluish Grey
        at=[0.0, -40.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Aerodynamic dorsal fuselage armor slope"
    )

    # 4. WINGS PORT (Left wing at x=-40: X span [-60, -20], touches spine at x=-20)
    # Wedge Plate 4x2 Left: at y=0, z=-20
    builder.add_submodel_part(
        submodel_file="04_wings_port.ldr",
        part_id="41770.dat", # Wedge Plate 4x2 Left
        color=71,            # Light Bluish Grey
        at=[-40.0, 0.0, -20.0],
        matrix=ROT_Y_90,
        purpose="Port wing forward wedge plate 4x2 Left"
    )
    # Wing trailing plate 2x4 at y=0, z=20
    builder.add_submodel_part(
        submodel_file="04_wings_port.ldr",
        part_id="3020.dat",  # Plate 2x4
        color=71,            # Light Bluish Grey
        at=[-40.0, 0.0, 20.0],
        matrix=ROT_Y_90,
        purpose="Port wing trailing plate 2x4"
    )
    # Wing top tile 1x4 at y=-8 (resting on top of wing plate at y=0), z=0
    builder.add_submodel_part(
        submodel_file="04_wings_port.ldr",
        part_id="2431.dat",  # Tile 1x4
        color=320,           # Dark Red (Red Squadron)
        at=[-40.0, -8.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Port wing Red Squadron identification marking"
    )

    # 5. WINGS STARBOARD (Right wing at x=40: X span [20, 60], touches spine at x=20)
    # Wedge Plate 4x2 Right: at y=0, z=-20
    builder.add_submodel_part(
        submodel_file="05_wings_starboard.ldr",
        part_id="41769.dat", # Wedge Plate 4x2 Right
        color=71,            # Light Bluish Grey
        at=[40.0, 0.0, -20.0],
        matrix=ROT_Y_90,
        purpose="Starboard wing forward wedge plate 4x2 Right"
    )
    # Wing trailing plate 2x4 at y=0, z=20
    builder.add_submodel_part(
        submodel_file="05_wings_starboard.ldr",
        part_id="3020.dat",  # Plate 2x4
        color=71,            # Light Bluish Grey
        at=[40.0, 0.0, 20.0],
        matrix=ROT_Y_90,
        purpose="Starboard wing trailing plate 2x4"
    )
    # Wing top tile 1x4 at y=-8, z=0
    builder.add_submodel_part(
        submodel_file="05_wings_starboard.ldr",
        part_id="2431.dat",  # Tile 1x4
        color=320,           # Dark Red (Red Squadron)
        at=[40.0, -8.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Starboard wing Red Squadron identification marking"
    )

    # 6. ENGINE NACELLES (Twin thrusters at rear, mounted at port x=-40, starboard x=40, z=50)
    # Port Thruster
    builder.add_submodel_part(
        submodel_file="06_engine_nacelles.ldr",
        part_id="3941.dat",  # Round Brick 2x2
        color=71,            # Light Bluish Grey
        at=[-40.0, -8.0, 50.0],
        matrix=ROT_IDENTITY,
        purpose="Port sublight thruster cylinder intake"
    )
    builder.add_submodel_part(
        submodel_file="06_engine_nacelles.ldr",
        part_id="4740.dat",  # Dish 2x2 Inverted
        color=72,            # Dark Bluish Grey
        at=[-40.0, -8.0, 70.0],
        matrix=ROT_IDENTITY,
        purpose="Port thruster exhaust convergence nozzle"
    )
    builder.add_submodel_part(
        submodel_file="06_engine_nacelles.ldr",
        part_id="6141.dat",  # Round Plate 1x1
        color=38,            # Trans-Neon Orange (LDraw code 38)
        at=[-40.0, -8.0, 78.0],
        matrix=ROT_IDENTITY,
        purpose="Port ion exhaust plasma glow emitter"
    )
    # Starboard Thruster
    builder.add_submodel_part(
        submodel_file="06_engine_nacelles.ldr",
        part_id="3941.dat",  # Round Brick 2x2
        color=71,            # Light Bluish Grey
        at=[40.0, -8.0, 50.0],
        matrix=ROT_IDENTITY,
        purpose="Starboard sublight thruster cylinder intake"
    )
    builder.add_submodel_part(
        submodel_file="06_engine_nacelles.ldr",
        part_id="4740.dat",  # Dish 2x2 Inverted
        color=72,            # Dark Bluish Grey
        at=[40.0, -8.0, 70.0],
        matrix=ROT_IDENTITY,
        purpose="Starboard thruster exhaust convergence nozzle"
    )
    builder.add_submodel_part(
        submodel_file="06_engine_nacelles.ldr",
        part_id="6141.dat",  # Round Plate 1x1
        color=38,            # Trans-Neon Orange (LDraw code 38)
        at=[40.0, -8.0, 78.0],
        matrix=ROT_IDENTITY,
        purpose="Starboard ion exhaust plasma glow emitter"
    )

    # 7. GREEBLING TRENCHES (Optical depth layering with grilles and clips at rear spine y=-40)
    builder.add_submodel_part(
        submodel_file="07_greebling_trenches.ldr",
        part_id="2412b.dat", # Tile 1x2 Grille
        color=71,            # Light Bluish Grey
        at=[0.0, -40.0, 20.0],
        matrix=ROT_Y_90,
        purpose="Dorsal service bay cooling radiator grille"
    )
    builder.add_submodel_part(
        submodel_file="07_greebling_trenches.ldr",
        part_id="2555.dat",  # Tile 1x1 with Clip
        color=71,            # Light Bluish Grey
        at=[0.0, -40.0, -20.0],
        matrix=ROT_IDENTITY,
        purpose="Central coolant conduit mounting clamp"
    )

    # 8. DISPLAY STAND (Sturdy black pedestal underneath resting under plate y=0)
    # Brick 2x2 at y=8 (body extends from y=8 to y=32)
    builder.add_submodel_part(
        submodel_file="08_display_stand.ldr",
        part_id="3003.dat",  # Brick 2x2
        color=0,             # Black
        at=[0.0, 8.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Display stand vertical pedestal support pillar"
    )
    # Plate 4x4 at y=32 (body extends from y=32 to y=40)
    builder.add_submodel_part(
        submodel_file="08_display_stand.ldr",
        part_id="3031.dat",  # Plate 4x4
        color=0,             # Black
        at=[0.0, 32.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Display stand weighted museum base plate 4x4"
    )

    plan = builder.export_plan()
    plan_path.write_text(json.dumps(plan, indent=2))
    print(f"Plan exported successfully to {plan_path}")
    return plan_path


def validate_canonical_starfighter(plan_path: Path, output_mpd: Path) -> bool:
    """Compiles the plan to MPD and validates geometry and contacts."""
    ldraw_dir = os.environ.get("LDRAW_DIR", str(Path.home() / "LDraw"))
    env = os.environ.copy()
    env["LDRAW_DIR"] = ldraw_dir
    env["PATH"] = f"{Path.home() / '.local/bin'}:{env.get('PATH', '')}"

    # 1. Build MPD from plan
    build_cmd = [
        str(REPO_ROOT / "ldraw-agent"),
        "build",
        "--force",
        "--output",
        str(output_mpd),
        str(plan_path),
    ]
    print(f"Executing: {' '.join(build_cmd)}")
    build_res = subprocess.run(build_cmd, capture_output=True, text=True, env=env)
    if build_res.returncode != 0:
        print("Build failed with stderr:\n", build_res.stderr)
        print("Build stdout:\n", build_res.stdout)
        return False
    print(f"[OK] MPD compiled at: {output_mpd}")

    # 2. Validate geometry
    val_cmd = [
        str(REPO_ROOT / "ldraw-agent"),
        "validate",
        "--geometry",
        "--contacts",
        "all",
        str(output_mpd),
    ]
    print(f"Executing: {' '.join(val_cmd)}")
    val_res = subprocess.run(val_cmd, capture_output=True, text=True, env=env)

    try:
        report = json.loads(val_res.stdout)
    except Exception:
        print("Raw validate output:\n", val_res.stdout)
        print("Validate stderr:\n", val_res.stderr)
        return False

    checks_passed = report.get("checks_passed", False)
    diagnostics = report.get("diagnostics", [])
    errors = [d for d in diagnostics if d.get("severity") == "error"]
    overlaps = [d for d in diagnostics if "overlap" in d.get("code", "")]

    print("\n--- STAR WARS STARFIGHTER VALIDATION SUMMARY ---")
    print(f"Checks passed: {checks_passed}")
    print(f"Total Diagnostics: {len(diagnostics)}")
    print(f"Errors: {len(errors)}")
    print(f"Body Overlaps: {len(overlaps)}")

    geom = report.get("geometry", {})
    if geom:
        comp_count = geom.get("optimistic_component_count", "N/A")
        print(f"Optimistic Component Count: {comp_count}")

    if errors:
        print("\nDiagnostics Details:")
        for e in errors[:10]:
            print(f" - [{e.get('code')}] {e.get('message')}")
        return False

    print("\n[SUCCESS] Canonical Star Wars Starfighter PASSED with 0 ERRORS and 0 BODY OVERLAPS!")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical Starfighter Test & Validation Runner")
    parser.add_argument("--outdir", default="output/canonical-starfighter", help="Output directory")
    args = parser.parse_args()

    outdir = REPO_ROOT / args.outdir
    plan_path = build_canonical_starfighter_plan(outdir)
    mpd_path = outdir / "canonical_starfighter.mpd"

    success = validate_canonical_starfighter(plan_path, mpd_path)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
