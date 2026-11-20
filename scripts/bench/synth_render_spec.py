"""Deterministic oracle for ``render_spec.json`` (A3 output shape).

Same idea as :mod:`synth_spec` but mirrors the shape of
``A3.describe_render_blind`` in ``ldraw_tools/agent_roles.py:92-129``:

    {"version": 1, "profile": ..., "segments": [{"id","type","role","color","description"}]}

Used by F5 to seed perturbed render_specs for A4 ablation and by the F4
curriculum harness as a control signal.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from scripts.bench import config
from scripts.bench.io_loader import StepBlock, load_io_steps, sample_id_from_path
from scripts.bench.synth_spec import _palette, compute_bbox3d  # noqa: PLC0415

logger = logging.getLogger(__name__)

__all__ = [
    "build_render_spec_oracle",
    "write_render_spec_oracle",
    "write_all_render_specs_for_sample",
]


def build_render_spec_oracle(
    block: StepBlock,
    *,
    sample_id: str,
    step_total: int,
) -> Dict[str, object]:
    """Build a deterministic ``render_spec_oracle`` dict for a single step."""
    palette = _palette(block.cumulative_parts)
    bbox = compute_bbox3d(block.cumulative_parts)
    dominant_color = palette[0]["name"] if palette else "Main_Colour"
    secondary_color = palette[1]["name"] if len(palette) > 1 else None

    desc = (
        f"Render-side oracle description for {sample_id} step "
        f"{block.step_idx}/{step_total - 1}. Cumulative assembly with "
        f"{block.parts_count_cum} parts and {len(palette)} distinct colours."
    )

    segments: List[Dict[str, object]] = [
        {
            "id": "seg_full_step",
            "type": "assembly",
            "role": "structural",
            "color": dominant_color,
            "description": desc,
        }
    ]
    if secondary_color is not None:
        segments.append({
            "id": "seg_accent",
            "type": "detail",
            "role": "detail",
            "color": secondary_color,
            "description": (
                f"Secondary colour accents (count="
                f"{palette[1]['count']}) visible across the render."
            ),
        })

    spec = {
        "version": 1,
        "profile": config.SYNTHETIC_SPEC_PROFILE,
        "segments": segments,
        "oracle": {
            "sample_id": sample_id,
            "step_idx": block.step_idx,
            "step_total": step_total,
            "parts_count_cum": block.parts_count_cum,
            "palette_cum": palette,
            "bbox_cum_3d": bbox.as_dict() if bbox else None,
        },
    }
    return spec


def write_render_spec_oracle(
    block: StepBlock,
    out_path: Path,
    *,
    sample_id: str,
    step_total: int,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    spec = build_render_spec_oracle(block, sample_id=sample_id, step_total=step_total)
    out_path.write_text(json.dumps(spec, indent=2, sort_keys=False), encoding="utf-8")
    return out_path


def write_all_render_specs_for_sample(
    io_path: Path,
    out_root: Path,
    *,
    max_steps: Optional[int] = None,
) -> List[Path]:
    io_path = Path(io_path)
    sid = sample_id_from_path(io_path)
    blocks = load_io_steps(io_path)
    if max_steps is not None:
        blocks = blocks[:max_steps]
    paths: List[Path] = []
    for block in blocks:
        p = Path(out_root) / sid / f"step_{block.step_idx}" / "render_spec_oracle.json"
        write_render_spec_oracle(block, p, sample_id=sid, step_total=len(blocks))
        paths.append(p)
    return paths
