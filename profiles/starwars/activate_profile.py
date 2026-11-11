#!/usr/bin/env python3
"""
Launcher and Environment Activator for Star Wars Starship Profile (profiles/starwars).

Features:
- Configures PYTHONPATH to expose profiles/starwars/helpers and repo root.
- Injects and displays instructions_starwars.md for Antigravity 2.0 system prompt.
- Runs self-tests and validation (test_canonical_starfighter.py).
- Verifies local LDraw environment (LDRAW_DIR, LeoCAD, Python venv).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROFILE_DIR.parents[1]
HELPERS_DIR = PROFILE_DIR / "helpers"
CATALOG_DIR = PROFILE_DIR / "catalog"
INSTRUCTIONS_FILE = PROFILE_DIR / "instructions_starwars.md"
WHITELIST_FILE = CATALOG_DIR / "starwars_whitelist.json"
PALETTE_FILE = CATALOG_DIR / "starwars_palette.json"
TEMPLATE_BLUEPRINT = PROFILE_DIR / "starship_blueprint_template.json"


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
    """Outputs the complete system prompt instructions for Star Wars ship design."""
    if INSTRUCTIONS_FILE.exists():
        print(INSTRUCTIONS_FILE.read_text(encoding="utf-8"))
    else:
        print(f"[ERROR] Instructions file not found at: {INSTRUCTIONS_FILE}", file=sys.stderr)


def init_blueprint(target_path: Path) -> None:
    """Copies starship_blueprint_template.json to the target destination."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if TEMPLATE_BLUEPRINT.exists():
        shutil.copyfile(TEMPLATE_BLUEPRINT, target_path)
        print(f"[OK] Starship blueprint initialized at: {target_path}")
    else:
        print(f"[ERROR] Template blueprint not found at: {TEMPLATE_BLUEPRINT}", file=sys.stderr)


def print_profile_stats() -> None:
    """Displays dataset statistics from catalog."""
    print("=" * 65)
    print("  LDrawNova Star Wars Domain Profile (profiles/starwars)")
    print("=" * 65)
    if WHITELIST_FILE.exists():
        with open(WHITELIST_FILE) as f:
            data = json.load(f)
        metrics = data.get("metrics", {})
        print(f"  * Total Star Wars Sets Cataloged (>= 2004): {metrics.get('total_starwars_sets', 'N/A')}")
        print(f"  * Distinct Specialized Parts:               {metrics.get('total_distinct_parts', 'N/A')}")
        print(f"  * Verified Color Palette:                  {metrics.get('total_distinct_colors', 'N/A')}")
        print(f"  * Validated Part-Color Pairs:              {metrics.get('total_verified_combos', 'N/A')}")
    print(f"  * Whitelist Catalog:   {WHITELIST_FILE}")
    print(f"  * Palette Manifest:    {PALETTE_FILE}")
    print(f"  * System Instructions: {INSTRUCTIONS_FILE}")
    print("=" * 65)


def run_tests() -> int:
    """Executes the canonical starfighter test suite."""
    test_script = PROFILE_DIR / "test_canonical_starfighter.py"
    if not test_script.exists():
        print(f"[ERROR] Test script not found at: {test_script}", file=sys.stderr)
        return 1
    env = ensure_environment()
    print(f"Running Star Wars Canonical Test: {test_script}")
    res = subprocess.run([sys.executable, str(test_script)], env=env)
    return res.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Star Wars Domain Profile Activator")
    parser.add_argument("--prompt", action="store_true", help="Print system instructions for agent context")
    parser.add_argument("--info", action="store_true", help="Display dataset metrics and catalog paths")
    parser.add_argument("--init-blueprint", type=Path, help="Initialize a starship_blueprint.json at path")
    parser.add_argument("--test", action="store_true", help="Run the canonical starfighter CAD validation test")

    args = parser.parse_args()

    ensure_environment()

    if args.prompt:
        print_system_prompt()
        return 0
    elif args.init_blueprint:
        init_blueprint(args.init_blueprint)
        return 0
    elif args.test:
        return run_tests()
    else:
        print_profile_stats()
        return 0


if __name__ == "__main__":
    sys.exit(main())
