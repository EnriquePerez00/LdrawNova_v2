"""Per-step ground-truth renderer.

For a given ``.io`` sample, materialise every step as a flat ``.ldr`` and
render the 4 canonical views (home/front/right/top) with LeoCAD. Output
layout matches the plan:

    output/bench/{smoke|gt}/<sample_id>/step_<k>/
        design_GT.ldr
        renders/
            home.png
            front.png
            right.png
            top.png

Idempotent: a step with all 4 PNGs already present is skipped. A hard cap
(:data:`scripts.bench.config.MAX_PARTS_PER_STEP_RENDER`) prevents LeoCAD from
blowing up on mega-sets.

Why this module does not use ``ldraw_tools.renderer.LeoCADRenderer``
----------------------------------------------------------------------
``LeoCADRenderer.render_views`` passes ``--camera "x y z dx dy dz"``. LeoCAD's
CLI defines ``-c, --camera <camera name>`` (the *name* of a saved camera) and
``--camera-position <x y z tx ty tz ux uy uz>`` for explicit placement — so the
old argument is silently ignored and every one of the 4 invocations renders
the *same* default auto-fit camera. That produced byte-identical PNGs for
home/front/right/top (see F0 report §3.1) and made the visual axis of the
benchmark meaningless.

This module therefore drives the LeoCAD CLI directly with ``--viewpoint``
(``home`` / ``front`` / ``right`` / ``top``), which LeoCAD documents as a
first-class preset. ``ldraw_tools/renderer.py`` is left untouched so the
rest of the production pipeline keeps its current behaviour.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from scripts.bench import config
from scripts.bench.io_loader import (
    StepBlock,
    load_io_steps,
    sample_id_from_path,
    serialize_step_to_ldr,
)

logger = logging.getLogger(__name__)

__all__ = ["RenderStepResult", "RenderSampleResult", "render_sample", "render_views"]

#: The 4 canonical views, mapped to LeoCAD ``--viewpoint`` presets.
VIEWPOINTS: Dict[str, str] = {
    "home": "home",
    "front": "front",
    "right": "right",
    "top": "top",
}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RenderStepResult:
    step_idx: int
    ldr_path: Path
    render_dir: Path
    rendered_views: Dict[str, Path] = field(default_factory=dict)
    #: ``True`` if we skipped because of ``MAX_PARTS_PER_STEP_RENDER``.
    skipped_too_large: bool = False
    #: Wall-clock milliseconds spent in this step (ldr serialise + render).
    duration_ms: int = 0
    #: Breakdown for diagnostics.
    serialize_ms: int = 0
    render_ms: int = 0
    #: Cumulative parts count at this step.
    parts_count_cum: int = 0
    #: ``True`` if nothing was done because artefacts existed already.
    reused_cached: bool = False


@dataclass
class RenderSampleResult:
    sample_id: str
    source_io: Path
    sample_dir: Path
    step_count: int
    steps: List[RenderStepResult] = field(default_factory=list)
    total_ms: int = 0


# ---------------------------------------------------------------------------
# LeoCAD CLI driver
# ---------------------------------------------------------------------------

_LEOCAD_BIN: Optional[str] = None


def _leocad_bin() -> Optional[str]:
    """Locate the LeoCAD executable (cached). Returns ``None`` if absent."""
    global _LEOCAD_BIN
    if _LEOCAD_BIN is None:
        _LEOCAD_BIN = shutil.which("leocad") or ""
        if not _LEOCAD_BIN:
            logger.error("[render_gt] LeoCAD binary 'leocad' not found on PATH")
    return _LEOCAD_BIN or None


def render_views(
    ldr_path: Path,
    render_dir: Path,
    *,
    views: Optional[List[str]] = None,
    timeout_s: int = config.RENDER_TIMEOUT_S,
    width: int = config.RENDER_WIDTH,
    height: int = config.RENDER_HEIGHT,
) -> Dict[str, Path]:
    """Render the 4 canonical views of ``ldr_path`` into ``render_dir``.

    Each view is a separate LeoCAD invocation using ``--viewpoint <preset>``.
    Returns the mapping of view name → PNG path for the views that were
    actually produced (a failed or timed-out view is simply absent).
    """
    views = views or list(VIEWPOINTS)
    render_dir = Path(render_dir)
    render_dir.mkdir(parents=True, exist_ok=True)
    binary = _leocad_bin()
    if binary is None:
        return {}

    rendered: Dict[str, Path] = {}
    for view_name in views:
        preset = VIEWPOINTS.get(view_name)
        if preset is None:
            logger.warning("[render_gt] unknown view %r — skipped", view_name)
            continue
        out_png = render_dir / f"{view_name}.png"
        cmd = [
            binary,
            str(ldr_path),
            "-i", str(out_png),
            "-w", str(width),
            "-h", str(height),
            "--viewpoint", preset,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout_s)
            if proc.returncode != 0 and not out_png.exists():
                logger.warning(
                    "[render_gt] %s view failed (rc=%s): %s",
                    view_name, proc.returncode,
                    (proc.stderr or b"").decode("utf-8", errors="replace")[:300],
                )
                continue
            if out_png.exists():
                rendered[view_name] = out_png
            else:
                logger.warning("[render_gt] %s view produced no PNG", view_name)
        except subprocess.TimeoutExpired:
            logger.warning("[render_gt] %s view timed out after %ss", view_name, timeout_s)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[render_gt] %s view failed: %r", view_name, exc)
    return rendered


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _views_complete(render_dir: Path) -> bool:
    for v in VIEWPOINTS:
        if not (render_dir / f"{v}.png").exists():
            return False
    return True


def _collect_cached_views(render_dir: Path) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for v in VIEWPOINTS:
        p = render_dir / f"{v}.png"
        if p.exists():
            out[v] = p
    return out


def render_sample(
    io_path: Path,
    out_root: Path,
    *,
    max_steps: Optional[int] = None,
    max_parts_cap: int = config.MAX_PARTS_PER_STEP_RENDER,
    force: bool = False,
) -> RenderSampleResult:
    """Render every step of ``io_path`` under ``out_root/<sample_id>/``.

    Parameters
    ----------
    io_path:
        Path to the ``.io`` archive.
    out_root:
        Directory that will contain ``<sample_id>/step_<k>/`` subtrees. The
        caller decides whether this lives under ``output/bench/smoke/<ts>/``
        or ``output/bench/gt/``.
    max_steps:
        If set, only steps ``0..max_steps-1`` are processed. Useful for F0d
        smoke on huge samples.
    max_parts_cap:
        Steps whose cumulative part count exceeds this cap are *not* rendered
        (``skipped_too_large=True``); their ``.ldr`` is still written.
    force:
        When ``True``, cached renders are ignored and regenerated.
    """
    io_path = Path(io_path)
    sample_id = sample_id_from_path(io_path)
    sample_dir = Path(out_root) / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    blocks: List[StepBlock] = load_io_steps(io_path)
    if max_steps is not None:
        blocks = blocks[:max_steps]

    result = RenderSampleResult(
        sample_id=sample_id,
        source_io=io_path,
        sample_dir=sample_dir,
        step_count=len(blocks),
    )

    for block in blocks:
        step_t0 = time.perf_counter()
        step_dir = sample_dir / f"step_{block.step_idx}"
        render_dir = step_dir / "renders"
        render_dir.mkdir(parents=True, exist_ok=True)
        ldr_path = step_dir / "design_GT.ldr"

        # 1. Serialise the cumulative state to .ldr (always, cheap).
        serialize_t0 = time.perf_counter()
        serialize_step_to_ldr(
            block, ldr_path, sample_id=sample_id, step_total=len(blocks),
        )
        serialize_ms = int((time.perf_counter() - serialize_t0) * 1000)

        step_result = RenderStepResult(
            step_idx=block.step_idx,
            ldr_path=ldr_path,
            render_dir=render_dir,
            serialize_ms=serialize_ms,
            parts_count_cum=block.parts_count_cum,
        )

        # 2. Skip rendering if over cap.
        if block.parts_count_cum > max_parts_cap:
            logger.warning(
                "[render_sample] %s step %d: %d parts > cap %d — skipping render",
                sample_id, block.step_idx, block.parts_count_cum, max_parts_cap,
            )
            step_result.skipped_too_large = True
            step_result.duration_ms = int((time.perf_counter() - step_t0) * 1000)
            result.steps.append(step_result)
            continue

        # 3. Idempotency: reuse existing PNGs unless forced.
        if not force and _views_complete(render_dir):
            step_result.rendered_views = _collect_cached_views(render_dir)
            step_result.reused_cached = True
            step_result.duration_ms = int((time.perf_counter() - step_t0) * 1000)
            result.steps.append(step_result)
            continue

        # 4. Actually render.
        render_t0 = time.perf_counter()
        rendered = render_views(ldr_path, render_dir)
        step_result.render_ms = int((time.perf_counter() - render_t0) * 1000)
        step_result.rendered_views = dict(rendered)
        step_result.duration_ms = int((time.perf_counter() - step_t0) * 1000)
        result.steps.append(step_result)

    result.total_ms = int((time.perf_counter() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# CLI (manual invocation for diagnostics; the real entry point is smoke.py)
# ---------------------------------------------------------------------------

def get_final_gt_renders(io_path: Path, out_root: Path) -> List[Path]:
    """Render the final assembled state of a .io and return the 4 view PNGs for A1.
    
    Args:
        io_path: Path to .io archive
        out_root: Output root (e.g., /tmp/gt_renders)
    
    Returns:
        List of PNG paths [home.png, front.png, right.png, top.png] for the final assembled model.
        Empty list if rendering failed or skipped.
    """
    res = render_sample(io_path, out_root, force=False)
    
    if not res.steps:
        logger.warning(f"[get_final_gt_renders] No steps rendered for {io_path}")
        return []
    
    # Take the LAST step (fully assembled model)
    final_step = res.steps[-1]
    if final_step.skipped_too_large or not final_step.rendered_views:
        logger.warning(
            f"[get_final_gt_renders] Final step {final_step.step_idx} was skipped or has no renders"
        )
        return []
    
    # Return PNGs in canonical order: [home, front, right, top]
    order = ["home", "front", "right", "top"]
    png_paths = [final_step.rendered_views.get(view) for view in order if view in final_step.rendered_views]
    logger.info(f"[get_final_gt_renders] {res.sample_id}: {len(png_paths)} views from step {final_step.step_idx}")
    
    return png_paths


def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Render every step of a .io sample.")
    parser.add_argument("io_path", type=Path, help="Path to a .io archive.")
    parser.add_argument("--out", type=Path, default=config.OUTPUT_SMOKE / "manual",
                        help="Output root (default: output/bench/smoke/manual).")
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Ignore cached renders.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    res = render_sample(args.io_path, args.out, max_steps=args.max_steps, force=args.force)
    print(f"sample={res.sample_id} steps={res.step_count} total_ms={res.total_ms}")
    for s in res.steps:
        tag = "SKIP" if s.skipped_too_large else ("CACHE" if s.reused_cached else "FRESH")
        print(f"  step={s.step_idx:3d} parts={s.parts_count_cum:6d} {tag:5s} "
              f"serialize_ms={s.serialize_ms:4d} render_ms={s.render_ms:5d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
