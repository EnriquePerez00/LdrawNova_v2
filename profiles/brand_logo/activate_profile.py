#!/usr/bin/env python3
"""
Launcher and Environment Activator for Corporate Brand Logo Profile (profiles/brand_logo).

Features:
- Configures PYTHONPATH to expose profiles/brand_logo/helpers and repo root.
- Injects and displays instructions_brand_logo.md for Antigravity 2.0 system prompt.
- Initializes logo_blueprint.json templates for incoming reference images.
- Verifies local LDraw environment (LDRAW_DIR, LeoCAD, Python venv).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROFILE_DIR.parents[1]
HELPERS_DIR = PROFILE_DIR / "helpers"
CATALOG_DIR = PROFILE_DIR / "catalog"
INSTRUCTIONS_FILE = PROFILE_DIR / "instructions_brand_logo.md"
WHITELIST_FILE = CATALOG_DIR / "brand_logo_whitelist.json"
PALETTE_FILE = CATALOG_DIR / "brand_logo_palette.json"
TEMPLATE_BLUEPRINT = PROFILE_DIR / "logo_blueprint_template.json"


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
            print("[WARNING] LDRAW_DIR not set and ~/LDraw not found. CAD tools may require --library.", file=sys.stderr)

    # Ensure PATH has ~/.local/bin for leocad
    local_bin = str(Path.home() / ".local" / "bin")
    current_path = env.get("PATH", "")
    if local_bin not in current_path.split(os.pathsep):
        env["PATH"] = f"{local_bin}{os.pathsep}{current_path}"

    return env


def print_system_prompt() -> None:
    """Outputs the complete system prompt instructions for Brand Logo design."""
    if INSTRUCTIONS_FILE.exists():
        print(INSTRUCTIONS_FILE.read_text(encoding="utf-8"))
    else:
        print(f"[ERROR] Instructions file not found at: {INSTRUCTIONS_FILE}", file=sys.stderr)


def init_blueprint(target_path: Path) -> None:
    """Copies logo_blueprint_template.json to the target destination."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if TEMPLATE_BLUEPRINT.exists():
        shutil.copyfile(TEMPLATE_BLUEPRINT, target_path)
        print(f"[OK] Brand logo blueprint initialized at: {target_path}")
    else:
        print(f"[ERROR] Template blueprint not found at: {TEMPLATE_BLUEPRINT}", file=sys.stderr)


def print_profile_stats() -> None:
    """Displays dataset statistics from catalog."""
    print("=" * 65)
    print("  LDrawNova Corporate Brand Logo Profile (profiles/brand_logo)")
    print("=" * 65)
    if WHITELIST_FILE.exists():
        with open(WHITELIST_FILE) as f:
            data = json.load(f)
        cats = data.get("categories", {})
        total_parts = sum(len(parts) for parts in cats.values())
        print(f"  * Total Approved Brand Parts:      {total_parts}")
        for cat_name, parts in cats.items():
            print(f"    - {cat_name.replace('_', ' ').title()}: {len(parts)} parts")
    if PALETTE_FILE.exists():
        with open(PALETTE_FILE) as f:
            p_data = json.load(f)
        colors = p_data.get("colors", [])
        print(f"  * Calibrated Brand Colors:         {len(colors)}")
    print(f"  * Whitelist Catalog:   {WHITELIST_FILE}")
    print(f"  * Palette Manifest:    {PALETTE_FILE}")
    print(f"  * System Instructions: {INSTRUCTIONS_FILE}")
    print("=" * 65)


def main() -> None:
    parser = argparse.ArgumentParser(description="Brand Logo Profile Activator for LdrawNova")
    parser.add_argument("--prompt", action="store_true", help="Print system prompt instructions")
    parser.add_argument("--stats", action="store_true", help="Print catalog and profile statistics")
    parser.add_argument("--init-blueprint", type=Path, help="Target path to initialize logo_blueprint.json")
    args = parser.parse_args()

    ensure_environment()

    if args.prompt:
        print_system_prompt()
    elif args.init_blueprint:
        init_blueprint(args.init_blueprint)
    else:
        print_profile_stats()


if __name__ == "__main__":
    main()
