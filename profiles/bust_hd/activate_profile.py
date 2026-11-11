#!/usr/bin/env python3
"""
Launcher and Environment Activator for High Definition Human Bust Profile (profiles/bust_hd).

Features:
- Configures PYTHONPATH to expose profiles/bust_hd/helpers and repo root.
- Injects and displays instructions_bust_hd.md for Antigravity 2.0 system prompt.
- Runs self-tests and validation (test_canonical_bust.py).
- Verifies local LDraw environment (LDRAW_DIR, LeoCAD, Python venv).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROFILE_DIR.parents[1]
HELPERS_DIR = PROFILE_DIR / "helpers"
CATALOG_DIR = PROFILE_DIR / "catalog"
INSTRUCTIONS_FILE = PROFILE_DIR / "instructions_bust_hd.md"
WHITELIST_FILE = CATALOG_DIR / "bust_whitelist.json"


def ensure_environment() -> dict[str, str]:
    """Ensures and exports appropriate environment variables for LDrawNova."""
    env = os.environ.copy()

    # Configure PYTHONPATH
    current_pythonpath = env.get("PYTHONPATH", "")
    paths_to_add = [str(REPO_ROOT), str(HELPERS_DIR)]
    for p in paths_to_add:
        if p not in current_pythonpath.split(os.pathsep):
            current_pythonpath = f"{p}{os.pathsep}{current_pythonpath}" if current_pythonpath else p
    env["PYTHONPATH"] = current_pythonpath

    # Verify LDRAW_DIR
    if "LDRAW_DIR" not in env:
        default_ldraw = Path.home() / "LDraw"
        if default_ldraw.exists():
            env["LDRAW_DIR"] = str(default_ldraw)
        else:
            print("[WARNING] LDRAW_DIR not set and ~/LDraw not found. CAD tools may require --library.")

    # Ensure PATH has ~/.local/bin for leocad
    local_bin = str(Path.home() / ".local" / "bin")
    current_path = env.get("PATH", "")
    if local_bin not in current_path.split(os.pathsep):
        env["PATH"] = f"{local_bin}{os.pathsep}{current_path}"

    return env


def print_system_prompt() -> None:
    """Outputs the complete system prompt instructions for bust sculpting."""
    if INSTRUCTIONS_FILE.exists():
        print(INSTRUCTIONS_FILE.read_text(encoding="utf-8"))
    else:
        print(f"[ERROR] Instructions file not found at {INSTRUCTIONS_FILE}", file=sys.stderr)


def run_tests(env: dict[str, str]) -> int:
    """Executes the canonical bust verification test suite."""
    test_script = PROFILE_DIR / "test_canonical_bust.py"
    if not test_script.exists():
        print(f"[ERROR] Test script {test_script} not found.", file=sys.stderr)
        return 1

    print(f"\n[ACTIVATION] Running Canonical Bust Geometry Validation...")
    python_bin = sys.executable
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        python_bin = str(venv_python)

    res = subprocess.run([python_bin, str(test_script)], env=env)
    return res.returncode


def generate_empty_blueprint(output_path: Path) -> None:
    """Generates an initial blank blueprint JSON for a new portrait project."""
    blueprint_template = {
        "subject_profile": {
            "name": "Portrait Subject",
            "gender_presentation": "masculine",
            "apparent_age": "mature_adult",
            "proportions": {
                "face_width_to_length_ratio": 0.82,
                "head_width_studs": 14,
                "head_depth_studs": 14,
                "head_height_bricks": 12,
                "shoulders_width_studs": 20
            },
            "mandible_and_chin": {
                "jaw_shape": "square",
                "chin_cleft": False,
                "beard_type": "full_beard",
                "beard_density": 0.85,
                "beard_palette_roles": [0, 72, 71, 308]
            },
            "nasal_morphology": {
                "prominence": "straight",
                "bridge_width_ldu": 20.0,
                "tip_angle_degrees": 30.0,
                "nostril_flare": "medium"
            },
            "ocular_region": {
                "eye_spacing_studs": 4,
                "iris_color_code": 308,
                "sclera_color_code": 15,
                "pupil_color_code": 0,
                "eyebrow_arch": "straight",
                "eyebrow_thickness_plates": 1
            },
            "cranium_and_hairline": {
                "hairline_shape": "receded_temples",
                "hair_texture": "curly_dense",
                "hair_primary_color": 308,
                "hair_highlight_color": 70
            },
            "wardrobe_and_pedestal": {
                "collar_type": "crew_neck",
                "clothing_primary_color": 272,
                "pedestal_style": "museum_plinth",
                "pedestal_color": 0
            }
        }
    }
    output_path.write_text(json.dumps(blueprint_template, indent=2), encoding="utf-8")
    print(f"[OK] Blueprint template generated at: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LdrawNova HD Bust Profile Activator (profiles/bust_hd)"
    )
    parser.add_argument(
        "--test", action="store_true", help="Run canonical bust verification tests"
    )
    parser.add_argument(
        "--prompt", action="store_true", help="Print system instructions for Antigravity"
    )
    parser.add_argument(
        "--init-blueprint", type=Path, help="Generate an empty facial_blueprint.json at the given path"
    )
    parser.add_argument(
        "--status", action="store_true", help="Display profile status and environment checks"
    )
    args = parser.parse_args()

    env = ensure_environment()

    if args.prompt:
        print_system_prompt()
        return 0

    if args.init_blueprint:
        generate_empty_blueprint(args.init_blueprint)
        return 0

    if args.test:
        return run_tests(env)

    # Default action / --status
    print("=" * 70)
    print("  LdrawNova - High Definition Human Bust Profile (profiles/bust_hd)")
    print("=" * 70)
    print(f"Profile Root:      {PROFILE_DIR}")
    print(f"Engine Module:     {HELPERS_DIR / 'bust_engine.py'} ({'EXISTS' if (HELPERS_DIR / 'bust_engine.py').exists() else 'MISSING'})")
    print(f"Curated Catalog:   {WHITELIST_FILE} ({'EXISTS' if WHITELIST_FILE.exists() else 'MISSING'})")
    print(f"System Prompt:     {INSTRUCTIONS_FILE} ({'EXISTS' if INSTRUCTIONS_FILE.exists() else 'MISSING'})")
    print(f"LDRAW_DIR:         {env.get('LDRAW_DIR', 'NOT_SET')}")
    print(f"Python Executable: {sys.executable}")
    print("-" * 70)
    print("Usage Quickstart:")
    print("  1. Iniciar nuevo diseño desde foto:")
    print("     python profiles/bust_hd/activate_profile.py --init-blueprint output/<slug>/facial_blueprint.json")
    print("  2. Ver el prompt de sistema especializado:")
    print("     python profiles/bust_hd/activate_profile.py --prompt")
    print("  3. Ejecutar test suite canónico:")
    print("     python profiles/bust_hd/activate_profile.py --test")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
