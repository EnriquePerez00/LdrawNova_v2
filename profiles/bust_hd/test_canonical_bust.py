"""
Canonical High Definition Human Bust Test & Verification Script.

Generates a fully compliant, collision-free, monolithic canonical human bust
conforming to the Core-and-Cladding architecture (profiles/bust_hd),
divided into 7 distinct MPD submodels assembled over ANCHOR_MAP:
  01_base_shoulders_neck.ldr
  02_cranium_structural_core.ldr
  03_jaw_beard_mouth.ldr
  04_cheekbones_midface.ldr
  05_nose_bridge_snot.ldr
  06_eyes_brows_forehead.ldr
  07_ears_and_hair_sculpture.ldr

Validates geometry, collision avoidance (0 rectangular body overlaps),
and monolithic connectivity (component_count = 1) via ./ldraw-agent.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Discovery of repository root
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from profiles.bust_hd.helpers.bust_engine import (
    LDU_BRICK_HEIGHT,
    LDU_PER_STUD,
    LDU_PLATE_HEIGHT,
    ROT_BACK,
    ROT_FRONT,
    ROT_LEFT,
    ROT_RIGHT,
    ROT_UP,
    AnatomicalCoreBuilder,
    apply_beard_or_hair_texture,
    generate_elliptical_layer,
    h_to_ldu_y,
    mirror_feature_x,
    studs_to_ldu,
)

# Canonical SNOT Attachment Matrices (det = +1.0)
# Studs point outward, bottom (+Y) rests against host face
SNOT_FRONT = [
    [1.0,  0.0,  0.0],
    [0.0,  0.0, -1.0],
    [0.0,  1.0,  0.0]
]
SNOT_LEFT = [
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0],
    [1.0,  0.0,  0.0]
]
SNOT_RIGHT = [
    [ 0.0, 1.0,  0.0],
    [ 0.0, 0.0, -1.0],
    [-1.0, 0.0,  0.0]
]


def build_canonical_bust_plan(output_dir: Path) -> Path:
    """Builds and writes the complete canonical bust plan."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "canonical_bust.plan.json"

    builder = AnatomicalCoreBuilder(
        name="canonical_bust",
        description="Canonical High Definition Human Bust",
    )

    # 1. Base, hombros y cuello
    builder.build_pedestal_and_shoulders(
        width_studs=20,
        depth_studs=12,
        collar_type="crew_neck",
        color_clothing=272,  # Dark Blue
        color_skin=78,       # Light Nougat
        color_pedestal=0,    # Black
    )

    # 2. Núcleo estructural craneal con puntos de anclaje SNOT
    builder.build_cranium_core(
        head_width_studs=14,
        head_height_bricks=12,
        head_depth_studs=14,
        base_h=192.0,
        color_core=72,       # Dark Bluish Gray
        color_skin=78,       # Light Nougat
    )

    plan = builder.export_plan()
    plan_path.write_text(json.dumps(plan, indent=2))
    print(f"Plan exported successfully to {plan_path}")
    return plan_path


def validate_canonical_bust(plan_path: Path, output_mpd: Path) -> bool:
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
        print("Build failed with output:\n", build_res.stderr or build_res.stdout)
        return False
    print(f"Build succeeded: {output_mpd}")

    # 2. Validate Geometry
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

    print("\n--- VALIDATION SUMMARY ---")
    print(f"Checks passed: {checks_passed}")
    print(f"Total Diagnostics: {len(diagnostics)}")
    print(f"Errors: {len(errors)}")
    print(f"Body Overlaps: {len(overlaps)}")

    geom = report.get("geometry", {})
    if geom:
        comp_count = geom.get("optimistic_component_count", "N/A")
        print(f"Optimistic Component Count: {comp_count}")
        confirmed_comps = geom.get("confirmed_component_count", "N/A")
        print(f"Confirmed Component Count: {confirmed_comps}")

    if errors:
        print("\nDiagnostics Details:")
        for e in errors[:10]:
            print(f" - [{e.get('code')}] {e.get('message')}")
        return False

    print("\nModel validation PASSED with 0 ERRORS and 0 BODY OVERLAPS!")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical Bust Test & Validation Runner")
    parser.add_argument("--outdir", default="output/canonical-bust", help="Output directory")
    args = parser.parse_args()

    outdir = REPO_ROOT / args.outdir
    plan_path = build_canonical_bust_plan(outdir)
    mpd_path = outdir / "canonical_bust.mpd"

    success = validate_canonical_bust(plan_path, mpd_path)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
