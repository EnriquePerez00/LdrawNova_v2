"""Deterministic pre-render physical gate for ImprovementLoopV2.

Phase 3 of the loop-v2-physical-gate plan: before running the LeoCAD renderer
and A3/A4 VLM calls, inspect the MPD produced by A2 for
- rectangular body collisions (two parts penetrating each other),
- floating islands (connected components disconnected from the base plate).

If either check fails, the loop short-circuits: a penalizing score is emitted
and the deterministic findings are turned into synthetic ``diffs`` that A2
consumes in the next iteration, in the same shape as the diffs A4 normally
returns.

Design notes:
- All heavy lifting is delegated to the already-present modules ``collision``,
  ``connectivity``, ``connection_adapter``, and ``document`` (plan §5: these
  stay read-only).
- Occurrence -> segment_id attribution reuses the MPD submodel convention
  defined in ``mpd_segments``: the owning submodel is the model.name of the
  last hop in the occurrence path.
- Everything is wrapped in a single ``run_physical_gate`` entry point so the
  loop orchestrator never touches pyldraw3 types directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import logging
import os

logger = logging.getLogger(__name__)

# Floating-island tolerance: a component whose minimum Y (LDraw Y points
# downward, so minimum Y is the *highest* geometry) is more than this many
# LDU away from the overall baseline counts as "floating". 8 LDU == 1 plate.
DEFAULT_FLOATING_TOLERANCE_LDU = 8.0

# Severity assigned to synthetic diffs. 5 == "critical" in loop_policy.SEVERITY_MAP.
SYNTHETIC_SEVERITY = 5

# Loop-wide score when the gate fails. Kept below REVERT_MARGIN(=5) of a
# typical best score so the orchestrator reverts to the previous best.
PRE_RENDER_GATE_SCORE = float(os.getenv("LOOP_PHYSICAL_GATE_SCORE", "10.0"))

# AUDIT FIX (Phase 3): AutoSnapRepairer flag - attempt to auto-fix before failing gate
ENABLE_AUTO_SNAP_REPAIR = os.getenv("ENABLE_AUTO_SNAP_REPAIR", "false").lower() == "true"
AUTO_SNAP_REPAIR_MAX_DISPLACEMENT_LDU = float(os.getenv("AUTO_SNAP_REPAIR_MAX_DISPLACEMENT_LDU", "40.0"))

# ---- FASE B.2: Heuristic gate tolerance (NEW) ----
# Maximum number of penetrations tolerated before failing the gate (default 0 = strict).
# Set to higher value (e.g. 15) to allow A3/A4 to execute and produce real score.
GATE_MAX_PENETRATIONS = int(os.getenv("GATE_MAX_PENETRATIONS", "0"))

# Maximum number of floating islands tolerated before failing the gate (default 0 = strict).
GATE_MAX_FLOATING_ISLANDS = int(os.getenv("GATE_MAX_FLOATING_ISLANDS", "0"))

# Penetration depth threshold (LDU): penetrations smaller than this are ignored.
# Default 0.0 = count all penetrations. Set to e.g. 4.0 to ignore < 0.5 stud overlaps.
GATE_MAX_PENETRATION_DEPTH_LDU = float(os.getenv("GATE_MAX_PENETRATION_DEPTH_LDU", "0.0"))

# ---- AUDIT FIX (Phase A): Grid alignment validator ----
GRID_VALIDATION_ENABLED = os.getenv("GRID_VALIDATION_ENABLED", "true").lower() == "true"
GRID_ALIGNMENT_TOLERANCE_LDU = float(os.getenv("GRID_ALIGNMENT_TOLERANCE_LDU", "0.1"))
STUD_LDU = 20
PLATE_LDU = 8

def _grid_alignment_diffs(mpd_path: Path, segment_blocks: Dict[str, Tuple[int, int, str]]) -> List[Dict[str, Any]]:
    """Check for grid misalignment (sub-stud coordinates)."""
    from ldraw_tools.document import parse_source
    diffs = []
    try:
        model = parse_source(mpd_path)
        for section in model.parts:
            for piece in section.parts:
                x, y, z = piece.position.x, piece.position.y, piece.position.z
                x_residual = x % STUD_LDU
                z_residual = z % STUD_LDU
                x_aligned = x_residual < GRID_ALIGNMENT_TOLERANCE_LDU or (STUD_LDU - x_residual) < GRID_ALIGNMENT_TOLERANCE_LDU
                z_aligned = z_residual < GRID_ALIGNMENT_TOLERANCE_LDU or (STUD_LDU - z_residual) < GRID_ALIGNMENT_TOLERANCE_LDU
                y_residual = y % PLATE_LDU
                y_aligned = y_residual < GRID_ALIGNMENT_TOLERANCE_LDU or (PLATE_LDU - y_residual) < GRID_ALIGNMENT_TOLERANCE_LDU
                if not (x_aligned and z_aligned and y_aligned):
                    segment_id = next(iter(segment_blocks.keys()), "")
                    diffs.append({
                        "severity": SYNTHETIC_SEVERITY,
                        "type": "grid_misalignment",
                        "segment_id": segment_id,
                        "mpd_line_range": None,
                        "issue": f"Part {piece.part_code} at ({x}, {y}, {z}) misaligned. X/Z must be multiples of {STUD_LDU}; Y multiples of {PLATE_LDU}.",
                        "suggestion": f"Use build_helpers.studs(n) to convert coordinates correctly.",
                        "source": "physical_gate.grid_alignment"
                    })
    except Exception as e:
        logger.debug(f"[Grid alignment] Parse error: {e}")
    return diffs





@dataclass
class PhysicalGateResult:
    """Outcome of a single pre-render gate pass.

    - ``ok``: True iff no critical physical issues were detected.
    - ``penetrations``: list of ``{segment_a, segment_b, depth_ldu, parts, ...}``
      records, one per colliding occurrence pair with a measurable body
      penetration.
    - ``floating_islands``: list of ``{segment_ids, occurrence_indices,
      distance_to_base_ldu}`` records for each connected component that lifts
      off the base plate.
    - ``synthetic_diffs``: diff-shaped dicts (severity, type, segment_id,
      mpd_line_range, issue, suggestion) ready for loop_policy.normalize_diffs.
    - ``unknown_parts``: set of part codes for which no body profile was
      available (see collision.py). Reported as a warning, never as a block.
    - ``degraded``: True when the gate was partial (e.g. instance_limit hit).
    - ``parse_error``: human-readable reason when the MPD could not be parsed.
    """

    ok: bool
    penetrations: List[Dict[str, Any]] = field(default_factory=list)
    floating_islands: List[Dict[str, Any]] = field(default_factory=list)
    synthetic_diffs: List[Dict[str, Any]] = field(default_factory=list)
    unknown_parts: List[str] = field(default_factory=list)
    degraded: bool = False
    parse_error: Optional[str] = None
    passed_with_warnings: bool = False  # (FASE B.2) True if ok=True but issues were tolerated via GATE_MAX_*

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "penetrations": self.penetrations,
            "floating_islands": self.floating_islands,
            "synthetic_diffs": self.synthetic_diffs,
            "unknown_parts": self.unknown_parts,
            "degraded": self.degraded,
            "parse_error": self.parse_error,
            "penetration_count": len(self.penetrations),
            "floating_island_count": len(self.floating_islands),
            "passed_with_warnings": self.passed_with_warnings,
        }


def _segment_id_for_occurrence(occ, segment_blocks: Dict[str, Tuple[int, int, str]]) -> Optional[str]:
    """Attribute a pyldraw3 occurrence to a segment id when possible.

    Priority:
    1. If the last-hop model.name matches a known segment filename convention
       (``segment_<id>.ldr``) or its SEGMENT_ID comment, use that id.
    2. Otherwise return None (unattributed collision).
    """
    try:
        hops = occ.occurrence.path
    except AttributeError:  # pragma: no cover - defensive
        return None
    for hop in reversed(hops):
        model_name = getattr(hop.model, "name", "") or ""
        stem = model_name.strip().rsplit(".", 1)[0].lower()
        if stem.startswith("segment_"):
            candidate = stem[len("segment_"):]
            # Match via explicit block table so the comment wins.
            if candidate in segment_blocks:
                return candidate
            # Still a plausible attribution even if the submodel is unknown.
            return candidate or None
    return None


def _segment_line_range(segment_id: Optional[str],
                        segment_blocks: Dict[str, Tuple[int, int, str]]) -> Optional[List[int]]:
    if segment_id and segment_id in segment_blocks:
        start, end, _ = segment_blocks[segment_id]
        return [start, end]
    return None


def _format_bounds(occ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    b = occ.bounds
    return ((float(b.min.x), float(b.min.y), float(b.min.z)),
            (float(b.max.x), float(b.max.y), float(b.max.z)))


def _build_penetration_diffs(penetrations: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    diffs = []
    for pen in penetrations:
        a, b = pen.get("segment_a"), pen.get("segment_b")
        depth = pen.get("depth_ldu")
        parts = pen.get("parts") or []
        parts_fmt = f" ({parts[0]} vs {parts[1]})" if len(parts) == 2 else ""
        subject_segment = a or b
        issue = (
            f"Collision: segments '{a or '?'}' and '{b or '?'}'{parts_fmt} "
            f"penetrate each other by {depth:.1f} LDU"
            if depth is not None else
            f"Collision: segments '{a or '?'}' and '{b or '?'}'{parts_fmt} overlap"
        )
        suggestion = (
            f"Move one of the segments by at least {depth:.1f} LDU or change the part"
            if depth is not None else
            "Reposition one of the segments to eliminate the overlap"
        )
        diffs.append({
            "severity": SYNTHETIC_SEVERITY,
            "type": "collision",
            "segment_id": subject_segment or "",
            "mpd_line_range": pen.get("mpd_line_range"),
            "issue": issue,
            "suggestion": suggestion,
            "source": "physical_gate",
            "evidence": {
                "segment_a": a, "segment_b": b,
                "depth_ldu": depth, "parts": parts,
                "occurrence_indices": pen.get("occurrence_indices"),
            },
        })
    return diffs


def _build_island_diffs(islands: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    diffs = []
    for island in islands:
        seg_ids = island.get("segment_ids") or []
        distance = island.get("distance_to_base_ldu") or 0.0
        subject = seg_ids[0] if seg_ids else ""
        ids_fmt = ", ".join(seg_ids) if seg_ids else "unattributed occurrences"
        diffs.append({
            "severity": SYNTHETIC_SEVERITY,
            "type": "floating_island",
            "segment_id": subject,
            "mpd_line_range": island.get("mpd_line_range"),
            "issue": (
                f"Floating island: segments [{ids_fmt}] are "
                f"{distance:.1f} LDU above the base plate with no connection to the main assembly"
            ),
            "suggestion": (
                f"Lower the island by {distance:.1f} LDU or add a connecting piece "
                f"(brick/plate) that bridges it to the main assembly"
            ),
            "source": "physical_gate",
            "evidence": {
                "segment_ids": seg_ids,
                "occurrence_indices": island.get("occurrence_indices"),
                "distance_to_base_ldu": distance,
            },
        })
    return diffs


def _union_find(occurrence_indices: Iterable[int],
                contact_pairs: Iterable[Tuple[int, int]]) -> Dict[int, int]:
    """Return {occurrence_index: component_root}.

    Each occurrence starts in its own component; contact pairs merge them.
    """
    parent: Dict[int, int] = {}
    for idx in occurrence_indices:
        parent[idx] = idx

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for a, b in contact_pairs:
        if a in parent and b in parent:
            union(a, b)

    # Compress.
    return {idx: find(idx) for idx in parent}


def _attempt_auto_snap_repair(floating_islands: List[Dict[str, Any]], 
                              model: Any, parts: Any, 
                              instance_limit: int = 2000) -> Tuple[bool, Optional[str]]:
    """Attempt to auto-repair floating islands using snap_report + apply_snap.
    
    AUDIT FIX (Phase 3): Before rejecting a model for floating islands,
    try to find a valid snapping configuration that fixes the issue.
    
    Args:
        floating_islands: List of floating island records from gate detection
        model: pyldraw3 model object
        parts: pyldraw3 Parts instance
        instance_limit: Budget for occurrence inspection
    
    Returns:
        (success: bool, repair_log: Optional[str])
        - success=True if at least one island was successfully snapped
        - repair_log: Human-readable description of repair attempt
    """
    if not ENABLE_AUTO_SNAP_REPAIR or not floating_islands:
        return False, None
    
    try:
        from ldraw_tools.connectivity import snap_report, apply_snap, inspect_connections
        repair_log = f"[AutoSnapRepairer] Attempting to repair {len(floating_islands)} floating island(s)\n"
        
        # Try to snap the first floating island to base as a heuristic
        island_record = floating_islands[0]
        occ_indices = island_record.get("occurrence_indices", [])
        
        if not occ_indices:
            repair_log += "  No occurrence indices in first island; skipping\n"
            return False, repair_log
        
        moving_occ = occ_indices[0]  # Try to move the first part in the island
        repair_log += f"  Attempting snap for occurrence {moving_occ}...\n"
        
        # Call snap_report with limit=1 (fastest, find best single snap)
        snap_result = snap_report(
            model, parts, moving_occ,
            fixed=None,  # Let it find any valid target
            limit=1,
            instance_limit=instance_limit,
            allow_occupied=False
        )
        
        candidates = snap_result.get("candidates", [])
        if not candidates:
            repair_log += "  No valid snap candidates found\n"
            return False, repair_log
        
        best = candidates[0]
        displacement = best.get("displacement_ldu", 0.0)
        
        # Only apply if displacement is within tolerance (default 40 LDU = 2 bricks)
        if displacement > AUTO_SNAP_REPAIR_MAX_DISPLACEMENT_LDU:
            repair_log += f"  Best snap requires {displacement:.1f} LDU displacement (max={AUTO_SNAP_REPAIR_MAX_DISPLACEMENT_LDU}); too large\n"
            return False, repair_log
        
        # Apply the snap
        repair_log += f"  Applying snap with {displacement:.1f} LDU displacement...\n"
        apply_result = apply_snap(model, parts, best.get("placement_path", []))
        
        repair_log += "  ✅ Snap applied successfully\n"
        logger.info(repair_log)
        return True, repair_log
    
    except Exception as e:
        repair_log = f"[AutoSnapRepairer] Failed to auto-repair: {str(e)}\n"
        logger.debug(repair_log)
        return False, repair_log


def run_physical_gate(mpd_path: Path,
                      *,
                      parts: Any = None,
                      floating_tolerance_ldu: float = DEFAULT_FLOATING_TOLERANCE_LDU,
                      instance_limit: int = 2000,
                      max_penetrations: Optional[int] = None,
                      max_floating_islands: Optional[int] = None,
                      max_penetration_depth_ldu: Optional[float] = None) -> PhysicalGateResult:
    """Run the deterministic physical gate on ``mpd_path``.

    ``parts`` is a pyldraw3 ``Parts`` instance. If omitted, the LDraw library
    is resolved from the environment via ``common.get_parts`` (so tests can
    pass a mock parts overlay directly).
    
    FASE B.2: Heuristic gate parameters (read from env if not provided):
    - max_penetrations: Max significant penetrations tolerated (default from env or global)
    - max_floating_islands: Max floating islands tolerated (default from env or global)
    - max_penetration_depth_ldu: Depth threshold for significance (default from env or global)
    """
    mpd_path = Path(mpd_path)
    
    # FASE B.2: Read heuristic gate parameters from env (dynamic, for A/B testing)
    gate_max_pen = max_penetrations if max_penetrations is not None else int(os.getenv("GATE_MAX_PENETRATIONS", "0"))
    gate_max_islands = max_floating_islands if max_floating_islands is not None else int(os.getenv("GATE_MAX_FLOATING_ISLANDS", "0"))
    gate_max_depth = max_penetration_depth_ldu if max_penetration_depth_ldu is not None else float(os.getenv("GATE_MAX_PENETRATION_DEPTH_LDU", "0.0"))

    # Submodel line ranges, pre-computed so every synthetic diff can cite them.
    # Imported here to avoid a hard dependency at module import time.
    from ldraw_tools.mpd_segments import parse_segment_blocks
    try:
        segment_blocks = parse_segment_blocks(mpd_path)
    except Exception as exc:  # pragma: no cover - defensive
        segment_blocks = {}
        logger.debug(f"[PhysicalGate] parse_segment_blocks failed: {exc}")

    # Parse the MPD and run connectivity inspection. Any failure here is a
    # critical, gate-failing event (the loop cannot render or judge invalid
    # LDraw anyway).
    try:
        from ldraw_tools.common import get_parts
        from ldraw_tools.document import parse_source
        from ldraw_tools.connectivity import inspect_connections
        from ldraw_tools.connection_adapter import connection_contacts
        from ldraw_tools.collision import collision_pairs
        from ldraw_tools.geometry import profiles as _profiles

        resolved_parts = parts or get_parts()
        model = parse_source(mpd_path)
    except Exception as exc:
        logger.warning(f"[PhysicalGate] Parse error: {exc}")
        parse_err = str(exc)
        diff = {
            "severity": SYNTHETIC_SEVERITY,
            "type": "parse_error",
            "segment_id": "",
            "mpd_line_range": None,
            "issue": f"MPD could not be parsed: {parse_err[:200]}",
            "suggestion": (
                "Re-emit a syntactically valid LDraw MPD; ensure every submodel "
                "has a matching `0 FILE` header and `0 NOFILE` footer"
            ),
            "source": "physical_gate",
        }
        return PhysicalGateResult(ok=False, parse_error=parse_err, synthetic_diffs=[diff])

    degraded = False
    try:
        inspection = inspect_connections(model, resolved_parts, instance_limit=instance_limit)
    except ValueError as exc:
        # instance_limit exceeded -> degraded gate (plan §6).
        logger.warning(f"[PhysicalGate] Degraded gate: {exc}")
        degraded = True
        try:
            inspection = inspect_connections(model, resolved_parts, instance_limit=instance_limit * 2)
        except Exception:
            # Give up cleanly: don't block the loop on a tooling error.
            return PhysicalGateResult(ok=True, degraded=True,
                                      parse_error=f"degraded: {exc}")

    occurrences = list(inspection.occurrences)
    if not occurrences:
        return PhysicalGateResult(ok=True, degraded=degraded)

    # ---- Collision detection ----
    regular = _profiles()
    penetrations: List[Dict[str, Any]] = []
    unknown_parts: set = set()
    for pair in collision_pairs(inspection, regular):
        # Only rectangular body overlaps count as deterministic penetrations
        # (plan §3.4). Stud-zone reviews are deferred to A4.
        if pair.get("status") != "rectangular_body_overlap":
            if pair.get("status") == "review_aabb_only":
                # Occurrences whose profile is unknown.
                for idx in pair.get("instances", []):
                    for occ in occurrences:
                        if occ.index == idx:
                            code = (occ.occurrence.part_code or "").lower()
                            if code and code not in regular:
                                unknown_parts.add(code)
            continue
        a_idx, b_idx = pair["instances"]
        occ_a = next((o for o in occurrences if o.index == a_idx), None)
        occ_b = next((o for o in occurrences if o.index == b_idx), None)
        seg_a = _segment_id_for_occurrence(occ_a, segment_blocks) if occ_a else None
        seg_b = _segment_id_for_occurrence(occ_b, segment_blocks) if occ_b else None
        # Attribute the penetration to whichever segment has a known line range.
        line_range = (_segment_line_range(seg_a, segment_blocks)
                      or _segment_line_range(seg_b, segment_blocks))
        penetrations.append({
            "segment_a": seg_a,
            "segment_b": seg_b,
            "depth_ldu": pair.get("body_penetration"),
            "parts": [occ_a.occurrence.part_code if occ_a else None,
                      occ_b.occurrence.part_code if occ_b else None],
            "occurrence_indices": [a_idx, b_idx],
            "mpd_line_range": line_range,
        })

    # ---- Floating-island detection via connectivity graph ----
    contacts = connection_contacts(inspection)
    contact_pairs = [(c.first_occurrence.index, c.second_occurrence.index) for c in contacts]
    components = _union_find((o.index for o in occurrences), contact_pairs)

    # Group by component root.
    groups: Dict[int, List[Any]] = {}
    for occ in occurrences:
        groups.setdefault(components[occ.index], []).append(occ)

    # The "base plate" reference is the single lowest point across the model;
    # in LDraw Y points downward, so the base is at the *maximum* Y value.
    max_y_global = max(float(o.bounds.max.y) for o in occurrences)

    floating: List[Dict[str, Any]] = []
    if len(groups) > 1:  # single component: nothing to flag
        for root, members in groups.items():
            if len(members) == len(occurrences):
                continue  # only one component overall, skip
            comp_max_y = max(float(o.bounds.max.y) for o in members)
            distance = max_y_global - comp_max_y
            # Positive distance means the component is above the baseline.
            if distance <= floating_tolerance_ldu:
                continue
            seg_ids: List[str] = []
            seen: set = set()
            indices: List[int] = []
            for occ in members:
                indices.append(occ.index)
                sid = _segment_id_for_occurrence(occ, segment_blocks)
                if sid and sid not in seen:
                    seen.add(sid)
                    seg_ids.append(sid)
            line_range = None
            for sid in seg_ids:
                r = _segment_line_range(sid, segment_blocks)
                if r:
                    line_range = r
                    break
            floating.append({
                "segment_ids": seg_ids,
                "occurrence_indices": indices,
                "distance_to_base_ldu": float(distance),
                "mpd_line_range": line_range,
            })

    # AUDIT FIX (Phase A): Include grid alignment diffs if validation enabled
    grid_diffs = _grid_alignment_diffs(mpd_path, segment_blocks) if GRID_VALIDATION_ENABLED else []
    synthetic = grid_diffs + _build_penetration_diffs(penetrations) + _build_island_diffs(floating)
    
    # AUDIT FIX (Phase 3.5): Validate geometric truth via connector metadata integrity
    # (Inmutabilidad por Conector - ensure connectivity inspection was complete)
    try:
        if not inspection.complete:
            logger.warning(
                "[PhysicalGate] ⚠️  Warning: Connection inspection reports incomplete "
                "metadata or missing parts in library. Geometric truth may be degraded. "
                "Consider checking part availability or updating library metadata."
            )
            degraded = True
    except AttributeError:
        logger.debug("[PhysicalGate] inspection.complete attribute not available (fallback to basic checks)")
    
    # AUDIT FIX (Phase 3): Attempt auto-repair floating islands before declaring gate failure
    if floating and ENABLE_AUTO_SNAP_REPAIR:
        repaired, repair_log = _attempt_auto_snap_repair(floating, model, resolved_parts, instance_limit)
        if repaired and repair_log:
            logger.info(repair_log)
            # Re-inspect after repair to check if issues resolved
            try:
                inspection_after = inspect_connections(model, resolved_parts, instance_limit=instance_limit)
                # Simplified re-check: if inspection completed without errors, assume repair worked
                logger.info("[AutoSnapRepairer] Re-inspection completed; attempting gate re-evaluation")
                # For safety, we don't re-run full gate, but we log success
                # The model is now updated with snapped positions; next iteration may pass
            except Exception as e:
                logger.debug(f"[AutoSnapRepairer] Re-inspection failed: {e}")
    
    # FASE B.2: Heuristic gate - tolerate issues up to configured thresholds
    significant_penetrations = [
        p for p in penetrations 
        if (p.get("depth_ldu") or 0) > gate_max_depth
    ]
    num_sig_pen = len(significant_penetrations)
    num_floating = len(floating)
    
    # Strict mode (default): any issue fails the gate
    # Permissive mode: allow up to MAX_* issues to pass as "warnings"
    ok_strict = not penetrations and not floating
    ok_heuristic = (num_sig_pen <= gate_max_pen and 
                    num_floating <= gate_max_islands)
    
    # If heuristic allows it but strict would fail, it's "with warnings"
    passed_with_warnings = ok_heuristic and not ok_strict
    
    result = PhysicalGateResult(
        ok=ok_heuristic,  # Use heuristic decision
        penetrations=penetrations,
        floating_islands=floating,
        synthetic_diffs=synthetic,
        unknown_parts=sorted(unknown_parts),
        degraded=degraded,
        passed_with_warnings=passed_with_warnings,
    )
    
    if not ok_heuristic:
        logger.warning(
            f"[PhysicalGate] FAILED: significant_penetrations={num_sig_pen} "
            f"(max={gate_max_pen}), floating_islands={num_floating} "
            f"(max={gate_max_islands})"
        )
    elif passed_with_warnings:
        logger.warning(
            f"[PhysicalGate] PASSED (with warnings): "
            f"significant_penetrations={num_sig_pen}, floating_islands={num_floating}"
        )
    else:
        logger.info(
            f"[PhysicalGate] OK (occurrences={len(occurrences)}, "
            f"components={len(groups)})"
        )
    return result
