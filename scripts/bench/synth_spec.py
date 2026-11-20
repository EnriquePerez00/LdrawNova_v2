"""Deterministic oracle for ``spec.json`` and part-level BOM, per step.

The real A1 agent emits a verbal spec from GT images. The oracle here derives
the **same shape** from the ground-truth ``.ldr`` content so later phases can
isolate the A2 (designer) or A3/A4 (describers/judge) error without the A1
noise. Output is intentionally richer than A1's typical response (it includes
the full BOM, 3D bbox, colour palette and part-id ground truth); downstream
scripts can pick the subset they need.

See ``docs/schemas/spec.schema.json`` and ``docs/schemas/segment.schema.json``
for reference. The synthetic specs carry ``profile=generic_set`` (new enum
value scheduled for F2).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scripts.bench import config
from scripts.bench.io_loader import PartLine, StepBlock, load_io_steps, sample_id_from_path

logger = logging.getLogger(__name__)

__all__ = [
    "build_spec_oracle",
    "write_spec_oracle",
    "write_all_specs_for_sample",
    "LdrawColorTable",
]


# ---------------------------------------------------------------------------
# LDraw color table (SQLite lookup with safe fallback)
# ---------------------------------------------------------------------------

_LDRAW_DB = Path(__file__).resolve().parent.parent.parent / "data" / "ldraw-info.db"

# Hand-crafted fallback for the most common IDs so the oracle still works if
# the DB is missing. Codes beyond this map resolve to "unknown_<id>".
_FALLBACK_COLORS: Dict[int, Tuple[str, str]] = {
    0: ("Black", "#1B2A34"),
    1: ("Blue", "#1E5AA8"),
    2: ("Green", "#00852B"),
    4: ("Red", "#B40000"),
    6: ("Brown", "#543324"),
    7: ("Light_Grey", "#8A928D"),
    8: ("Dark_Grey", "#545955"),
    14: ("Yellow", "#F5CD2F"),
    15: ("White", "#F4F4F4"),
    16: ("Main_Colour", "#808080"),
    24: ("Edge_Colour", "#000000"),
    47: ("Trans_Clear", "#FCFCFC"),
    71: ("Light_Bluish_Grey", "#969696"),
    72: ("Dark_Bluish_Grey", "#646464"),
}


class LdrawColorTable:
    """Lazy loader for LDraw code → (name, hex). SQLite-backed with fallback."""

    def __init__(self, db_path: Path = _LDRAW_DB) -> None:
        self._db_path = db_path
        self._cache: Dict[int, Tuple[str, str]] = {}
        self._loaded = False

    def _load_once(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._db_path.exists():
            logger.warning("[LdrawColorTable] DB missing (%s); using fallback palette.", self._db_path)
            self._cache.update(_FALLBACK_COLORS)
            return
        try:
            con = sqlite3.connect(self._db_path)
            try:
                for code_str, name, value in con.execute("SELECT code, color, value FROM COLORS"):
                    try:
                        self._cache[int(code_str)] = (name or f"code_{code_str}", value or "#808080")
                    except ValueError:
                        continue
            finally:
                con.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[LdrawColorTable] load failed: %r — using fallback", exc)
            self._cache.update(_FALLBACK_COLORS)

    def lookup(self, code: int) -> Tuple[str, str]:
        self._load_once()
        return self._cache.get(code, (f"unknown_{code}", "#808080"))


_COLOR_TABLE = LdrawColorTable()


# ---------------------------------------------------------------------------
# 3D bbox helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BBox3D:
    x_min: float
    y_min: float
    z_min: float
    x_max: float
    y_max: float
    z_max: float

    @property
    def dims(self) -> Tuple[float, float, float]:
        return (self.x_max - self.x_min, self.y_max - self.y_min, self.z_max - self.z_min)

    def as_dict(self) -> Dict[str, float]:
        d = self.dims
        return {
            "x_min": round(self.x_min, 3),
            "y_min": round(self.y_min, 3),
            "z_min": round(self.z_min, 3),
            "x_max": round(self.x_max, 3),
            "y_max": round(self.y_max, 3),
            "z_max": round(self.z_max, 3),
            "width": round(d[0], 3),
            "height": round(d[1], 3),
            "depth": round(d[2], 3),
        }


def compute_bbox3d(parts: Sequence[PartLine]) -> Optional[BBox3D]:
    """Return the axis-aligned bbox of the *origins* of ``parts``.

    This is a cheap approximation (ignores per-part extents) but good enough
    for the composite's ``bbox_ratio`` component and for scale sanity checks.
    """
    if not parts:
        return None
    xs = [p.x for p in parts]
    ys = [p.y for p in parts]
    zs = [p.z for p in parts]
    return BBox3D(
        x_min=min(xs), y_min=min(ys), z_min=min(zs),
        x_max=max(xs), y_max=max(ys), z_max=max(zs),
    )


# ---------------------------------------------------------------------------
# BOM / palette derivation
# ---------------------------------------------------------------------------

def _bom_by_part_and_color(parts: Iterable[PartLine]) -> Dict[str, Dict[int, int]]:
    """Return ``{part_id: {color_code: count}}``."""
    out: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for p in parts:
        out[p.part_id][p.color] += 1
    # Convert inner defaultdicts to plain dicts for JSON serialisation.
    return {k: dict(v) for k, v in out.items()}


def _palette(parts: Iterable[PartLine]) -> List[Dict[str, object]]:
    """Return the colour palette: unique ``(code, name, hex, count)`` tuples."""
    counts = Counter(p.color for p in parts)
    out: List[Dict[str, object]] = []
    for code, n in counts.most_common():
        name, hx = _COLOR_TABLE.lookup(code)
        out.append({"code": code, "name": name, "hex": hx, "count": n})
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_spec_oracle(
    block: StepBlock,
    *,
    sample_id: str,
    step_total: int,
    source_io: Path,
) -> Dict[str, object]:
    """Build a deterministic ``spec_oracle`` dict for a single step.

    The shape is close to A1's output but enriched: it includes a BOM, a
    colour palette and a 3D bbox. The ``segments`` list is intentionally a
    single global segment (MVP; later phases can refine with clustering).
    """
    cumulative = block.cumulative_parts
    new = block.new_parts
    bbox_cum = compute_bbox3d(cumulative)
    palette_cum = _palette(cumulative)

    # A single catch-all segment covers the whole step. Position/size are
    # computed from the 3D bbox so A2 gets a meaningful hint.
    seg = {
        "id": "seg_full_step",
        "type": "assembly",
        "role": "structural",
        "color": palette_cum[0]["name"] if palette_cum else "Main_Colour",
        "description": (
            f"Cumulative assembly after step {block.step_idx}/{step_total - 1} "
            f"({block.parts_count_cum} parts total, {block.parts_count_new} new in this step)."
        ),
        # Normalised 2D bbox (placeholder: whole frame). Real clustering is a
        # future refinement.
        "bbox_norm": [0.0, 0.0, 1.0, 1.0],
        "estimated_size_studs": (
            [round(d / 20.0, 2) for d in bbox_cum.dims] if bbox_cum else [0, 0, 0]
        ),
        "position_description": "whole_frame",
        "confidence": 1.0,
    }

    spec = {
        "version": 1,
        "profile": config.SYNTHETIC_SPEC_PROFILE,
        "brand_name": sample_id,
        "category": "generic_set_step",
        "canonical_description": (
            f"Oracle-derived spec for {sample_id} at step {block.step_idx} "
            f"out of {step_total - 1}. Not a VLM output — ground-truth.\n"
            f"Cumulative parts: {block.parts_count_cum}. "
            f"New parts in this step: {block.parts_count_new}. "
            f"Distinct part IDs cumulative: {len({p.part_id for p in cumulative})}. "
            f"Distinct colours cumulative: {len(palette_cum)}."
        ),
        "segments": [seg],
        # Enrichment fields (outside strict schema; A2 can ignore or consume).
        "oracle": {
            "sample_id": sample_id,
            "step_idx": block.step_idx,
            "step_total": step_total,
            "source_io": str(source_io),
            "parts_count_cum": block.parts_count_cum,
            "parts_count_new": block.parts_count_new,
            "bom_cum": _bom_by_part_and_color(cumulative),
            "bom_new": _bom_by_part_and_color(new),
            "palette_cum": palette_cum,
            "bbox_cum_3d": bbox_cum.as_dict() if bbox_cum else None,
        },
    }
    return spec


def write_spec_oracle(
    block: StepBlock,
    out_path: Path,
    *,
    sample_id: str,
    step_total: int,
    source_io: Path,
) -> Path:
    """Serialise :func:`build_spec_oracle` to ``out_path`` (pretty JSON)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    spec = build_spec_oracle(
        block, sample_id=sample_id, step_total=step_total, source_io=source_io,
    )
    out_path.write_text(json.dumps(spec, indent=2, sort_keys=False), encoding="utf-8")
    return out_path


def write_all_specs_for_sample(
    io_path: Path,
    out_root: Path,
    *,
    max_steps: Optional[int] = None,
) -> List[Path]:
    """Write ``spec_oracle.json`` under every ``out_root/<sample_id>/step_<k>/``.

    Returns the list of written paths.
    """
    io_path = Path(io_path)
    sid = sample_id_from_path(io_path)
    blocks = load_io_steps(io_path)
    if max_steps is not None:
        blocks = blocks[:max_steps]
    paths: List[Path] = []
    for block in blocks:
        p = Path(out_root) / sid / f"step_{block.step_idx}" / "spec_oracle.json"
        write_spec_oracle(
            block, p, sample_id=sid, step_total=len(blocks), source_io=io_path,
        )
        paths.append(p)
    return paths
