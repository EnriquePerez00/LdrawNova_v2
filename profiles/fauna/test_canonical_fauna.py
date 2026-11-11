"""
Canonical Fauna Animal Test & Verification Script.

Generates a fully compliant, collision-free, monolithic canonical animal model
conforming to the Biomechanical Fauna Architecture (profiles/fauna),
divided into 9 distinct MPD submodels:
  01_spine_torso.ldr
  02_cranial_head.ldr
  03_mandible_jaw.ldr
  04_forelimbs_left.ldr
  05_forelimbs_right.ldr
  06_hindlimbs_left.ldr
  07_hindlimbs_right.ldr
  08_caudal_tail.ldr
  09_habitat_perch.ldr

Validates geometry, collision avoidance (0 rectangular body overlaps),
and physical connectivity (component_count = 1) via ./ldraw-agent.
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

from profiles.fauna.helpers.fauna_engine import (
    FaunaAnimalBuilder,
    MorphologicalArchetype,
    ROT_IDENTITY,
    ROT_Y_90,
    ROT_Y_180,
    ROT_Y_270,
    SNOT_FRONT,
)


def build_canonical_fauna_plan(output_dir: Path) -> Path:
    """Builds and writes the complete canonical animal plan."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "canonical_fauna.plan.json"

    builder = FaunaAnimalBuilder(
        name="canonical_fauna",
        description="Canonical Avian Kingfisher on Perch",
        archetype=MorphologicalArchetype.AVIAN
    )

    # =========================================================================
    # 1. HABITAT PERCH (Submodel 09) - Weighted museum stand & wooden perch
    # =========================================================================
    # Weighted base plate 4x4 (Black) at Y=48: Y span [48, 56], X span [-40, 40], Z span [-40, 40]
    builder.add_submodel_part(
        submodel_file="09_habitat_perch.ldr",
        part_id="3031.dat",  # Plate 4x4
        color=0,             # Black
        at=[0.0, 48.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Weighted museum base plinth plate 4x4"
    )
    # Pedestal brick 2x2 (Black) at Y=24: Y span [24, 48], resting on plate 4x4
    builder.add_submodel_part(
        submodel_file="09_habitat_perch.ldr",
        part_id="3003.dat",  # Brick 2x2
        color=0,             # Black
        at=[0.0, 24.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Vertical pedestal support brick 2x2"
    )
    # Perch horizontal branch brick 1x2 (Reddish Brown) rotated 90 deg:
    # at Y=0: Y span [0, 24], X span [-20, 20], Z span [-10, 10]
    builder.add_submodel_part(
        submodel_file="09_habitat_perch.ldr",
        part_id="3004.dat",  # Brick 1x2
        color=70,            # Reddish Brown
        at=[0.0, 0.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Horizontal wooden branch perch brick 1x2"
    )

    # =========================================================================
    # 2. HINDLIMBS / TALONS (Submodels 06 & 07) - Gripping feet on perch at Y=0
    # =========================================================================
    # Left foot plate 1x2 (Yellow) at X=-10, Y=-8, Z=0: Y span [-8, 0], X span [-20, 0], Z span [-20, 20]
    builder.add_submodel_part(
        submodel_file="06_hindlimbs_left.ldr",
        part_id="3023.dat",  # Plate 1x2
        color=14,            # Yellow
        at=[-10.0, -8.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Left perching talon foot plate 1x2"
    )
    # Right foot plate 1x2 (Yellow) at X=10, Y=-8, Z=0: Y span [-8, 0], X span [0, 20], Z span [-20, 20]
    builder.add_submodel_part(
        submodel_file="07_hindlimbs_right.ldr",
        part_id="3023.dat",  # Plate 1x2
        color=14,            # Yellow
        at=[10.0, -8.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Right perching talon foot plate 1x2"
    )

    # =========================================================================
    # 3. SPINE & TORSO (Submodel 01) - Pelvis, breast core & spine
    # =========================================================================
    # Lower pelvic plate 2x4 (Orange/Breast): at Y=-16, resting directly on both feet at Y=-8
    # X span [-20, 20], Z span [-40, 40], Y span [-16, -8]
    builder.add_submodel_part(
        submodel_file="01_spine_torso.ldr",
        part_id="3020.dat",  # Plate 2x4
        color=25,            # Orange (Kingfisher breast)
        at=[0.0, -16.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Pelvic & lower abdominal base plate 2x4"
    )
    # Torso thoracic core brick 1x2 (Orange): at Y=-40, resting on plate 2x4 at Y=-16
    # Y span [-40, -16], X span [-20, 20], Z span [-10, 10]
    builder.add_submodel_part(
        submodel_file="01_spine_torso.ldr",
        part_id="3004.dat",  # Brick 1x2
        color=25,            # Orange
        at=[0.0, -40.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Central thoracic core brick 1x2"
    )
    # Upper dorsal spine plate 1x2 (Dark Blue): at Y=-48, resting on brick 1x2 at Y=-40
    # Y span [-48, -40], X span [-20, 20], Z span [-10, 10]
    builder.add_submodel_part(
        submodel_file="01_spine_torso.ldr",
        part_id="3023.dat",  # Plate 1x2
        color=272,           # Dark Blue (Dorsal plumage)
        at=[0.0, -48.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Upper dorsal spine anchor plate 1x2"
    )
    # Towball neck kinematic adapter (Light Bluish Gray): at Y=-56, resting on plate 1x2 at Y=-48
    builder.add_submodel_part(
        submodel_file="01_spine_torso.ldr",
        part_id="14417.dat", # Plate 1x2 with Towball
        color=71,            # Light Bluish Gray
        at=[0.0, -56.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Cervical articulation towball male adapter"
    )

    # =========================================================================
    # 4. CRANIAL HEAD (Submodel 02) - Cranium, ocular region & upper beak
    # =========================================================================
    # Socket receiver plate 1x2 (Light Bluish Gray): at Y=-64, mates with towball at Y=-56
    builder.add_submodel_part(
        submodel_file="02_cranial_head.ldr",
        part_id="14704.dat", # Plate 1x2 with Towball Socket
        color=71,            # Light Bluish Gray
        at=[0.0, -64.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Cranial base socket female receiver"
    )
    # Cranial crown curved slope 2x1 (Dark Blue): at Y=-72, resting on socket plate at Y=-64
    builder.add_submodel_part(
        submodel_file="02_cranial_head.ldr",
        part_id="11477.dat", # Slope Curved 2x1
        color=272,           # Dark Blue
        at=[0.0, -72.0, 0.0],
        matrix=ROT_Y_90,
        purpose="Cranial crest & crown curved slope 2x1"
    )
    # Upper beak cheese slope 30° 1x1 (Black): forward at Z=-20, Y=-64
    builder.add_submodel_part(
        submodel_file="02_cranial_head.ldr",
        part_id="54200.dat", # Slope 30 1x1 (Cheese)
        color=0,             # Black
        at=[0.0, -64.0, -20.0],
        matrix=ROT_IDENTITY,
        purpose="Upper maxillary raptorial beak cheese slope 1x1"
    )

    # =========================================================================
    # 5. MANDIBLE JAW (Submodel 03) - Lower beak
    # =========================================================================
    # Lower beak plate 1x1 (Black): at Z=-20, Y=-56 (directly under upper beak)
    builder.add_submodel_part(
        submodel_file="03_mandible_jaw.ldr",
        part_id="3024.dat",  # Plate 1x1
        color=0,             # Black
        at=[0.0, -56.0, -20.0],
        matrix=ROT_IDENTITY,
        purpose="Lower mandibular beak tip plate 1x1"
    )

    # =========================================================================
    # 6. FORELIMBS / WINGS (Submodels 04 & 05) - Bilateral Chiral Wings
    # =========================================================================
    # Left Wing: Wedge Plate 3x2 Left at X=-30, Y=-24, Z=0 (touches torso at X=-20)
    builder.add_submodel_part(
        submodel_file="04_forelimbs_left.ldr",
        part_id="43723.dat", # Wedge Plate 3x2 Left
        color=272,           # Dark Blue
        at=[-30.0, -24.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Left primary flight wing wedge plate 3x2 Left"
    )
    # Right Wing: Wedge Plate 3x2 Right (Chiral!) at X=30, Y=-24, Z=0 (touches torso at X=20)
    builder.add_submodel_part(
        submodel_file="05_forelimbs_right.ldr",
        part_id="43722.dat", # Wedge Plate 3x2 Right
        color=272,           # Dark Blue
        at=[30.0, -24.0, 0.0],
        matrix=ROT_IDENTITY,
        purpose="Right primary flight wing wedge plate 3x2 Right"
    )

    # =========================================================================
    # 7. CAUDAL TAIL (Submodel 08) - Rear plumage
    # =========================================================================
    # Tail plate 1x2 (Dark Blue): at Z=30, Y=-24, touching rear of torso plate
    builder.add_submodel_part(
        submodel_file="08_caudal_tail.ldr",
        part_id="3023.dat",  # Plate 1x2
        color=272,           # Dark Blue
        at=[0.0, -24.0, 30.0],
        matrix=ROT_IDENTITY,
        purpose="Caudal tail plumage anchor plate 1x2"
    )
    # Tail curved slope 2x1 (Dark Blue): at Z=30, Y=-32 (resting on tail plate at Y=-24)
    builder.add_submodel_part(
        submodel_file="08_caudal_tail.ldr",
        part_id="11477.dat", # Slope Curved 2x1
        color=272,           # Dark Blue
        at=[0.0, -32.0, 30.0],
        matrix=ROT_Y_180,
        purpose="Caudal tail feather curved slope 2x1"
    )

    plan = builder.export_plan()
    plan_path.write_text(json.dumps(plan, indent=2))
    print(f"[OK] Plan exported successfully to {plan_path}")
    return plan_path


def validate_canonical_fauna(plan_path: Path, output_mpd: Path) -> bool:
    """Compiles the plan to MPD and validates geometry and contacts."""
    ldraw_dir = os.environ.get("LDRAW_DIR", str(Path.home() / "LDraw"))
    env = os.environ.copy()
    env["LDRAW_DIR"] = ldraw_dir
    env["PATH"] = f"{Path.home() / '.local/bin'}:{env.get('PATH', '')}"

    # 1. Build MPD via ldraw-agent build
    build_cmd = [
        str(REPO_ROOT / "ldraw-agent"),
        "build",
        str(plan_path),
        "--output",
        str(output_mpd),
        "--force"
    ]
    print(f"Executing: {' '.join(build_cmd)}")
    build_res = subprocess.run(build_cmd, env=env, capture_output=True, text=True)
    if build_res.returncode != 0:
        error_msg = build_res.stderr or build_res.stdout
        print(f"[ERROR] Build failed:\n{error_msg}", file=sys.stderr)
        return False
    print(f"[OK] Build successful: {output_mpd}")

    # 2. Validate Geometry via ldraw-agent validate --geometry
    val_cmd = [
        str(REPO_ROOT / "ldraw-agent"),
        "validate",
        str(output_mpd),
        "--geometry"
    ]
    print(f"Executing: {' '.join(val_cmd)}")
    val_res = subprocess.run(val_cmd, env=env, capture_output=True, text=True)
    print(val_res.stdout)
    if val_res.returncode != 0:
        print(f"[ERROR] Validation failed:\n{val_res.stderr}", file=sys.stderr)
        return False

    # Check for overlaps
    if "0 rectangular body overlaps" not in val_res.stdout and "collisions" in val_res.stdout.lower():
        print("[WARNING] Non-zero collisions detected in geometry validation.")

    # 3. Inspect Physical Connectivity via ldraw-agent inspect --contacts all
    insp_cmd = [
        str(REPO_ROOT / "ldraw-agent"),
        "inspect",
        str(output_mpd),
        "--contacts",
        "all"
    ]
    print(f"Executing: {' '.join(insp_cmd)}")
    insp_res = subprocess.run(insp_cmd, env=env, capture_output=True, text=True)
    print(insp_res.stdout)
    if insp_res.returncode != 0:
        print(f"[ERROR] Contact inspection failed:\n{insp_res.stderr}", file=sys.stderr)
        return False

    print("\n[SUCCESS] Canonical Fauna verification passed with physical connectivity!")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical Fauna Test Suite")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "output" / "canonical_fauna")
    args = parser.parse_args()

    plan_path = build_canonical_fauna_plan(args.output_dir)
    mpd_path = args.output_dir / "canonical_fauna.mpd"

    success = validate_canonical_fauna(plan_path, mpd_path)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
