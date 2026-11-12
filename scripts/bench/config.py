"""Configuration for scripts/bench — F0 smoke + F1 dataset preparation.

All constants are collected here to make the harness reproducible and
override-friendly via environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# External dataset
# ---------------------------------------------------------------------------

#: Absolute path to the step-aware .io corpus (BrickLink Studio 2.0 archives).
#: 
#: Resolution order (first match wins):
#: 1. Env var LDRAW_NOVA_IO_DIR (allows local override for testing)
#: 2. LegoGPT data_locator.get_normalized_io_dir() (cross-repo, recommended)
#: 3. Default hardcoded path (fallback for isolated testing)
#: 
#: Validated at import time by any caller that needs the corpus (validate_io_source()).
def _resolve_io_source_dir() -> Path:
    """Resolve IO_SOURCE_DIR with multi-level fallback strategy."""
    # Level 1: explicit env override
    if "LDRAW_NOVA_IO_DIR" in os.environ:
        return Path(os.environ["LDRAW_NOVA_IO_DIR"])
    
    # Level 2: cross-repo via LegoGPT data_locator
    try:
        import sys
        legogpt_root = Path(__file__).resolve().parent.parent.parent.parent / "LegoGPT"
        if legogpt_root.exists():
            sys.path.insert(0, str(legogpt_root))
            from src.data_locator import get_normalized_io_dir
            return get_normalized_io_dir()
    except Exception:
        pass
    
    # Level 3: hardcoded fallback
    return Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io")

IO_SOURCE_DIR: Path = _resolve_io_source_dir()

#: Static password shipped by BrickLink Studio 2.0 for its ``.io`` archives.
#: Not all files are password-protected but trying this first is harmless.
STUDIO_ZIP_PASSWORD: bytes = b"soho0909"

#: Minimum number of ``.io`` files the harness expects to find in
#: ``IO_SOURCE_DIR``. 927 is the total observed (2026-11); 900 leaves headroom
#: for files temporarily missing without aborting.
MIN_EXPECTED_IO_FILES: int = 900


# ---------------------------------------------------------------------------
# Bucket thresholds (step-aware)
# ---------------------------------------------------------------------------

#: Bucket upper bounds on ``step_count`` (inclusive). Tuned from the real
#: histogram over the 927 .io corpus (p10=1, median=17, p90=87, max=440).
#: Samples with ``step_count == 1`` are marked ``no_steps`` and handled
#: separately (excluded from curriculum but usable for E2E).
BUCKET_THRESHOLDS: dict[str, int] = {
    "trivial": 5,
    "simple": 20,
    "medium": 60,
    # "complex": step_count > 60
}

BUCKET_ORDER: tuple[str, ...] = ("trivial", "simple", "medium", "complex")

NO_STEPS_BUCKET: str = "no_steps"


def classify_bucket(step_count: int) -> str:
    """Return the bucket name for a sample with ``step_count`` steps."""
    if step_count <= 1:
        return NO_STEPS_BUCKET
    if step_count <= BUCKET_THRESHOLDS["trivial"]:
        return "trivial"
    if step_count <= BUCKET_THRESHOLDS["simple"]:
        return "simple"
    if step_count <= BUCKET_THRESHOLDS["medium"]:
        return "medium"
    return "complex"


# ---------------------------------------------------------------------------
# Render-cost classification (drives LeoCAD budget, not the curriculum)
# ---------------------------------------------------------------------------

#: Upper bounds on the **total part count** of a sample, used to predict the
#: LeoCAD render cost and memory footprint. ``step_count`` alone is a poor
#: proxy: a sample can have 13 steps but 52k parts, which is far heavier to
#: render than a 60-step sample with 300 parts.
RENDER_COST_THRESHOLDS: dict[str, int] = {
    "light": 500,       # ≤ 500 parts  → ~1-3 s/step
    "moderate": 2_000,  # ≤ 2k parts  → ~3-10 s/step
    "heavy": 10_000,    # ≤ 10k parts → ~10-40 s/step
    # "extreme": > 10k parts → minutes/step, high memory
}

RENDER_COST_ORDER: tuple[str, ...] = ("light", "moderate", "heavy", "extreme")


def classify_render_cost(parts_count: int) -> str:
    """Return the render-cost class for a sample with ``parts_count`` parts."""
    if parts_count <= RENDER_COST_THRESHOLDS["light"]:
        return "light"
    if parts_count <= RENDER_COST_THRESHOLDS["moderate"]:
        return "moderate"
    if parts_count <= RENDER_COST_THRESHOLDS["heavy"]:
        return "heavy"
    return "extreme"


# ---------------------------------------------------------------------------
# Rendering caps and output layout
# ---------------------------------------------------------------------------

#: Hard cap on per-step cumulative parts before rendering that step is skipped
#: (LeoCAD struggles with >50k parts per render). Mega-sets (e.g. 190k parts in
#: 193 steps) are rendered only up to this cap; later steps get an empty
#: placeholder PNG. The F0 report flags any such skip.
#:
#: Calibrated against the F0/F1 measurements (see output/bench/smoke/*/REPORT.md):
#:   *   ~13 parts   → ~1-3 s/step
#:   *   200 parts   → ~3.3 s/step
#:   * 10 806 parts → ~40 s/step  (and high RSS)
#: LeoCAD also gets OOM-killed well before 50k parts when several workers run
#: in parallel, so the cap is deliberately conservative.
MAX_PARTS_PER_STEP_RENDER: int = 5_000

#: Samples whose **total** part count exceeds this are excluded from the
#: GT materialisation entirely (they are recorded in the report as
#: ``skipped_oversized``). Their step structure is still usable for the
#: curriculum (the LDraw files are generated without rendering).
MAX_PARTS_PER_SAMPLE: int = 50_000

#: Soft wall-time cap per render invocation (LeoCAD CLI). Match the default of
#: ``LeoCADRenderer`` in ``ldraw_tools/renderer.py:75`` (30s).
RENDER_TIMEOUT_S: int = 30

#: Default render resolution. Smaller than default to speed up F0; F1 may raise
#: this before the eval run.
RENDER_WIDTH: int = 800
RENDER_HEIGHT: int = 600

#: Output directories (relative to repo root). Overridable via env for CI.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_ROOT: Path = Path(os.environ.get("LDRAW_NOVA_BENCH_OUT", str(_REPO_ROOT / "output" / "bench")))
OUTPUT_SMOKE: Path = OUTPUT_ROOT / "smoke"
OUTPUT_DATASET: Path = OUTPUT_ROOT / "dataset"
OUTPUT_GT: Path = OUTPUT_ROOT / "gt"


# ---------------------------------------------------------------------------
# Per-phase token/latency budgets (consumed by F2-F6, surfaced here for one
# source-of-truth). F0/F1 don't call LLMs.
# ---------------------------------------------------------------------------

#: Hard token budget per sample per phase. The harness aborts if
#: ``TokenTracker`` reports usage beyond this.
TOKEN_BUDGETS: dict[str, int] = {
    "F0b-token": 50_000,  # one dry-run per agent, generous
    "F2": 20_000,
    "F3": 10_000,
    "F4": 40_000,
    "F5": 10_000,
    "F6": 60_000,
}

#: Default agent-model mapping for F0b-token dry-run and F2 baseline. Pulled
#: from ``agents.yaml`` defaults (do NOT override agent_roles.py here; this is
#: only a hint for the smoke estimator).
DEFAULT_MODELS: dict[str, str] = {
    "A1": "gemini-2.5-flash",
    "A2": "claude-haiku-5",
    "A3": "gemini-2.5-flash",
    "A4": "gemini-2.5-flash",
}


# ---------------------------------------------------------------------------
# Profile hint for synthetic specs
# ---------------------------------------------------------------------------

#: The 927 .io corpus is heterogeneous (sets, MOCs); the loop's profile enum
#: currently lacks a generic bucket. We write specs with this profile tag and
#: ask F2 to extend ``docs/schemas/spec.schema.json`` to accept it.
SYNTHETIC_SPEC_PROFILE: str = "generic_set"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_io_source() -> None:
    """Raise ``RuntimeError`` if the corpus directory is missing or sparse.
    
    Tries to auto-resolve LegoGPT paths via data_locator; if that fails,
    gives clear instructions for manual configuration.
    """
    if not IO_SOURCE_DIR.exists():
        msg = (
            f"[bench.config] IO_SOURCE_DIR not found: {IO_SOURCE_DIR}\n"
            f"\n"
            f"To fix, choose one of:\n"
            f"  1. Export env var:  export LDRAW_NOVA_IO_DIR=/path/to/LegoGPT/data/normalized_io\n"
            f"  2. Ensure LegoGPT repo sibling exists at: ../LegoGPT\n"
            f"  3. Copy/symlink LegoGPT/data/normalized_io locally\n"
        )
        raise RuntimeError(
            msg
        )
    n = sum(1 for _ in IO_SOURCE_DIR.glob("*.io"))
    if n < MIN_EXPECTED_IO_FILES:
        raise RuntimeError(
            f"[bench.config] Found only {n} .io files in {IO_SOURCE_DIR}; "
            f"expected ≥ {MIN_EXPECTED_IO_FILES}.\n"
            f"Check that LegoGPT Fase 1 (data recovery) completed successfully."
        )
