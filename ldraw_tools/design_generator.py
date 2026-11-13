"""A2 Designer: code-LLM generation for LDraw designs.

Phase 1 of the loop-v2-physical-gate plan removes legacy truncations (only 5
segments in the prompt, max_tokens=1000) so A2 receives the full spec and can
emit a complete MPD. Phase 2 additionally instructs A2 to emit one
`0 FILE segment_<id>.ldr` submodel per spec segment, so later phases can target
feedback and partial rewrites at segment granularity.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Phase 1: lift the artificial output cap. 0 or empty means "no limit" (omit from payload).
# If set to a positive integer, that becomes the max_tokens in the LLM request.
# Default: 0 (no limit) — let the model/proxy decide based on context window.
# Previously (legacy): 4096, which caused truncation of large multi-segment designs.
_a2_max_tokens_env = os.getenv("A2_MAX_TOKENS", "0").strip()
A2_MAX_TOKENS = int(_a2_max_tokens_env) if _a2_max_tokens_env else 0
# If 0: we'll omit max_tokens from the payload (no limit).
# If >0: we'll include it in the payload.

# Expose the previous behavior behind a flag so operators can bisect regressions.
A2_PARTIAL_REWRITE = os.getenv("A2_PARTIAL_REWRITE", "true").lower() == "true"

# PHASE 4 (AUDIT FIX): Enable plan.json mode for A2 (default: false for backward compatibility)
A2_EMIT_PLAN_JSON = os.getenv("A2_EMIT_PLAN_JSON", "false").lower() == "true"


def _segment_id(seg: Dict[str, Any], index: int) -> str:
    """Pick a stable identifier for a spec segment (prefer id, fall back to name/index)."""
    raw = seg.get("id") or seg.get("name") or f"segment_{index}"
    # Sanitize for filesystem/LDraw: letters, digits, underscore, dash.
    cleaned = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(raw))
    return cleaned.strip("_") or f"segment_{index}"


def _build_ldraw_geometry_invariants_block(segments: List[Dict[str, Any]], profile_adapter: Any) -> str:
    """Build LDRAW_GEOMETRY_INVARIANTS block explaining coordinate system and part geometry.
    
    AUDIT FIX (Phase 2): Inyectar invariantes geométricos correctos (sin Z=i*40).
    """
    # Try to load part geometry from rectangular-parts.json (if available)
    geom_data = ""
    try:
        geom_path = Path(__file__).parent / "data" / "rectangular-parts.json"
        if geom_path.exists():
            geom_file = json.loads(geom_path.read_text())
            # Show a sample of available parts with their LDU dimensions
            sample_parts = list(geom_file.get("parts", {}).items())[:5]
            if sample_parts:
                geom_data = "\nSample part dimensions (from rectangular-parts.json):\n"
                for part_code, dims in sample_parts:
                    if isinstance(dims, dict):
                        x = dims.get("x", 0)
                        y = dims.get("y", 0)
                        z = dims.get("z", 0)
                        geom_data += f"  {part_code}: X={x} LDU, Y={y} LDU, Z={z} LDU\n"
    except Exception as e:
        logger.debug(f"[A2] Could not load geometry data: {e}")
    
    block = """LDRAW GEOMETRY INVARIANTS (IMMUTABLE - REQUIRED FOR CORRECTNESS):

1. COORDINATE SYSTEM:
   - +X = right (width), +Z = forward/away (depth), -Y = UP (vertical)
   - 1 stud = 20 LDU in X or Z
   - 1 brick height = 24 LDU in Y (measured downward from reference)
   - 1 plate height = 8 LDU in Y

2. DO NOT USE ARBITRARY Z-LAYER ASSIGNMENT (e.g., Z=i*40 for segments).
   The Z-axis represents DEPTH (front-back), NOT height. Vertical stacking uses Y.

3. PART-TO-PART CONNECTIVITY:
   - Male stud at (x, y, z) connects to female receptacle at (x, y-24, z) for 1-brick height
   - Male stud at (x, y, z) connects to female receptacle at (x, y-8, z) for 1-plate height
   - All coordinates must align to stud grid: multiples of 20 LDU in X/Z

4. ASSEMBLY ORDER (from spec attached_to/attachment_face):"""
    
    # Add assembly topology if available
    for seg in segments:
        seg_id = seg.get("id") or seg.get("name", "unknown")
        attached_to = seg.get("attached_to", "base_plate")
        face = seg.get("attachment_face", "bottom")
        block += f"\n   - {seg_id}: attach to {attached_to} at {face}"
    
    block += f"\n\n5. PART LIBRARY CONSTRAINT:\n   Use ONLY standard LDraw library parts (.dat files).{geom_data}"
    
    
    # AUDIT FIX (Phase D): Strengthen geometric invariants
    block += """

6. SCALE CONVERSION (CRITICAL):
   - ALWAYS compute coordinates in studs first, then convert to LDU
   - Use helpers: studs(n) = n*20, plates(n) = n*8, bricks(n) = n*24
   - NEVER emit 0.6, 1.2, 2.5 directly (=sub-stud floats; appear as 0.03 studs)
   - WRONG: x = 0.6 (renders as 0.6 LDU); RIGHT: x = studs(2.5) = 50

7. ANGULAR ARRANGEMENTS (rings/octagons):
   - For N-part ring: position = (radius_ldu*cos(angle), y, radius_ldu*sin(angle))
   - Emit YAW for each: yaw = angle_deg + 90 (points outward)
   - DO NOT use identity matrix for all parts; yaw must vary
   - Cycle colors through parts for visual depth

8. STACKING & CONNECTIVITY:
   - Stacked pieces: use "on" mechanism (builder validates stud alignment)
   - Define support first, then stack with "on": support_id
   - For arbitrary angles: use "attach" with anchors
   - NEVER emit "at" for stacked parts; builder computes Y offset

9. GRID VALIDATION:
   - X/Z must be multiples of 20 LDU; Y multiples of 8 LDU
   - Any deviation > 0.1 LDU from grid fails validation (post-generation)
   - Use build_helpers.validate_grid_alignment(x, z, y) to check before emitting
"""

    return block + "\n"


def _format_segment_line(index: int, seg: Dict[str, Any]) -> str:
    """Compact human-readable description of a spec segment for the A2 prompt."""
    sid = _segment_id(seg, index)
    name = seg.get("name") or seg.get("type") or sid
    desc = seg.get("description") or seg.get("position_description") or ""
    color = seg.get("color_dominant") or seg.get("color") or ""
    size = seg.get("estimated_size_studs") or seg.get("size_studs") or ""
    parts = [f"id={sid}", f"name={name}"]
    if size:
        parts.append(f"size_studs={size}")
    if color:
        parts.append(f"color={color}")
    if desc:
        parts.append(f"desc={desc}")
    return "- " + "; ".join(parts)


def _submodel_instructions(segments: list) -> str:
    """Instruction block that forces A2 to emit one submodel per spec segment."""
    if not segments:
        return ""
    ids = [_segment_id(s, i) for i, s in enumerate(segments)]
    example_main_refs = "\n".join(
        f"1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_{sid}.ldr" for sid in ids[:2]
    ) or "1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_<id>.ldr"
    example_sub = ids[0] if ids else "example"
    return f"""
MPD STRUCTURE (REQUIRED):
Emit ONE submodel per spec segment using the following convention:

0 FILE design.ldr
0 Name: design.ldr
0 Author: LdrawNova A2
{example_main_refs}
... (one line per segment)
0 NOFILE

0 FILE segment_<id>.ldr
0 // SEGMENT_ID: <id>
0 // SEGMENT_SOURCE: spec.segments[<index>]
0 Name: segment_<id>.ldr
1 <color> <x> <y> <z> 1 0 0 0 1 0 0 0 1 <part>.dat
...
0 NOFILE

Required segment ids (one submodel per id, in this order):
{', '.join(ids)}

Each submodel MUST start with `0 // SEGMENT_ID: <id>` matching one of the ids
above. The main file must reference every segment submodel exactly once.
Keep part codes (`.dat`) from the standard LDraw library.
Example first submodel header for segment '{example_sub}':
0 FILE segment_{example_sub}.ldr
0 // SEGMENT_ID: {example_sub}
0 // SEGMENT_SOURCE: spec.segments[0]
"""


def _build_prompt(spec: Dict[str, Any], feedback: Optional[Dict[str, Any]],
                  profile_adapter: Any, few_shot_recipes: Optional[List[Dict[str, Any]]] = None) -> Tuple[str, int]:
    """Assemble the A2 prompt and return (prompt_text, num_segments).
    
    Args:
        spec: Design specification
        feedback: Optional feedback from gate/A4 with diffs
        profile_adapter: Profile for instructions
        few_shot_recipes: Optional list of recipe dicts to inject as examples (FASE C)
    """
    segments = spec.get("segments", []) or []
    feedback_str = ""
    if feedback:
        diffs = feedback.get("diffs", []) or []
        if diffs:
            feedback_str = "\n\nFeedback from judge (fixes needed, highest severity first):\n"
            for d in diffs[:5]:
                sev = d.get("severity", "unknown")
                seg = d.get("segment_id") or d.get("segment") or ""
                issue = d.get("issue") or d.get("type") or "unknown"
                fix = d.get("suggestion") or d.get("suggested_fix") or "improve"
                suffix = f" (segment={seg})" if seg else ""
                feedback_str += f"- [sev={sev}] {issue}{suffix}\n  Fix: {fix}\n"

    segment_block = "\n".join(_format_segment_line(i, s) for i, s in enumerate(segments))
    if not segment_block:
        segment_block = "(no segments provided; emit a minimal valid MPD)"

    submodel_rules = _submodel_instructions(segments)
    
    # AUDIT FIX (Phase 2): Inject LDraw geometry invariants
    geometry_invariants_block = _build_ldraw_geometry_invariants_block(segments, profile_adapter)
    
    # FASE C: Format few-shot recipes into prompt block (optional)
    few_shot_block = ""
    if few_shot_recipes:
        try:
            from scripts.bench.recipe_bank import format_recipes_for_prompt
            few_shot_block = "\n" + format_recipes_for_prompt(few_shot_recipes) + "\n"
        except Exception as e:
            logger.debug(f"[A2] Failed to format few-shot recipes: {e}")
    
    # FASE D+: Inject learned constraints (cross-set generalizations)
    learned_constraints_block = ""
    try:
        # Read learned constraints from feedback (passed by improvement_loop via learned_constraints)
        if feedback and "learned_constraints" in feedback:
            learned_constraints = feedback.get("learned_constraints", [])
            if learned_constraints:
                learned_constraints_block = "\n\nLearned constraints from previous sets (apply to all segments):\n"
                for i, constraint in enumerate(learned_constraints, 1):
                    learned_constraints_block += f"{i}. {constraint}\n"
                logger.info(f"[A2] Injected {len(learned_constraints)} learned constraint(s)")
    except Exception as e:
        logger.debug(f"[A2] Error reading learned constraints: {e}")

    # PHASE 4: Conditional prompt format (MPD vs plan.json)
    if A2_EMIT_PLAN_JSON:
        from ldraw_tools.a2_output_parser import a2_plan_json_mode_prompt
        prompt = f"""Generate a plan.json assembly plan for a LEGO design based on this spec.

Profile: {profile_adapter.profile_name}
Description: {spec.get('canonical_description', 'LEGO model')}
Total segments: {len(segments)}

{geometry_invariants_block}

Segment details (one line per segment, keep the ids exact):
{segment_block}
{feedback_str}{learned_constraints_block}{few_shot_block}{a2_plan_json_mode_prompt()}
Return ONLY valid JSON (plan.json format), no explanation, no markdown fences.
"""
    else:
        # Legacy MPD mode (default, backward compatible)
        prompt = f"""Generate valid LDraw/MPD code for a LEGO design based on this spec.

Profile: {profile_adapter.profile_name}
Description: {spec.get('canonical_description', 'LEGO model')}
Total segments: {len(segments)}

{geometry_invariants_block}

Segment details (one line per segment, keep the ids exact):
{segment_block}
{feedback_str}{learned_constraints_block}{few_shot_block}{submodel_rules}
Return ONLY the MPD code, no explanation, no markdown fences.
"""
    return prompt, len(segments)


def _count_submodels(mpd_code: str, expected_ids: list) -> Tuple[int, float]:
    """Return (matched_count, coverage) over the expected segment ids."""
    if not expected_ids:
        return 0, 1.0
    matched = 0
    text = mpd_code
    for sid in expected_ids:
        # Accept either the FILE header or the SEGMENT_ID comment.
        needles = (f"FILE segment_{sid}.ldr", f"SEGMENT_ID: {sid}", f"SEGMENT_ID:{sid}")
        if any(n in text for n in needles):
            matched += 1
    return matched, matched / len(expected_ids)


def _diffs_with_segments(feedback: Optional[Dict[str, Any]]) -> list:
    """Return the feedback diffs that carry a segment_id and mpd_line_range."""
    if not feedback:
        return []
    out = []
    for d in feedback.get("diffs") or []:
        if not isinstance(d, dict):
            continue
        sid = (d.get("segment_id") or "").strip()
        rng = d.get("mpd_line_range")
        if sid and rng:
            out.append(d)
    return out


def _parse_returned_submodels(text: str) -> Dict[str, str]:
    """Extract ``{segment_id: block_text}`` from an A2 partial-rewrite response.

    Accepts one or more ``0 FILE segment_<id>.ldr ... 0 NOFILE`` blocks.
    Returns an empty dict if no submodel block is found (full-MPD fallback).
    """
    # Strip optional markdown fences.
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    import re
    file_re = re.compile(r"^\s*0\s+FILE\s+(\S+)\s*$", re.IGNORECASE)
    nofile_re = re.compile(r"^\s*0\s+NOFILE\s*$", re.IGNORECASE)
    segid_re = re.compile(r"^\s*0\s*//\s*SEGMENT_ID\s*:\s*(\S+)", re.IGNORECASE)

    blocks: Dict[str, str] = {}
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        m = file_re.match(lines[i])
        if not m:
            i += 1
            continue
        filename = m.group(1).strip()
        start = i
        # Find matching NOFILE (or EOF / next FILE).
        j = i + 1
        while j < len(lines) and not nofile_re.match(lines[j]) and not file_re.match(lines[j]):
            j += 1
        if j < len(lines) and nofile_re.match(lines[j]):
            j += 1  # include NOFILE
        block_text = "".join(lines[start:j])
        # Derive segment id.
        seg_id: Optional[str] = None
        for line in lines[start:j]:
            sm = segid_re.match(line)
            if sm:
                seg_id = sm.group(1).strip()
                break
        if seg_id is None:
            stem = filename.rsplit(".", 1)[0].lower()
            if stem.startswith("segment_"):
                seg_id = stem[len("segment_"):]
        if seg_id:
            blocks[seg_id] = block_text
        i = j
    return blocks


def _build_partial_prompt(spec: Dict[str, Any],
                          targeted_diffs: list,
                          affected_segments: Dict[str, str],
                          profile_adapter: Any) -> str:
    """Prompt A2 to rewrite ONLY the submodels referenced by ``targeted_diffs``."""
    segments_by_id = {}
    for i, s in enumerate(spec.get("segments", []) or []):
        sid = _segment_id(s, i)
        segments_by_id[sid] = {"index": i, **s}

    lines = [
        "Rewrite ONLY the LDraw submodels listed below to address the following",
        "critical issues. Do NOT emit the full MPD: return one or more",
        "`0 FILE segment_<id>.ldr ... 0 NOFILE` blocks and nothing else.",
        "",
        f"Profile: {profile_adapter.profile_name}",
        "",
        "Diffs to fix (one per affected segment):",
    ]
    for d in targeted_diffs:
        sid = d.get("segment_id")
        sev = d.get("severity", "")
        issue = d.get("issue") or d.get("type") or "unspecified"
        fix = d.get("suggestion") or d.get("suggested_fix") or ""
        lines.append(f"- segment={sid} [sev={sev}]: {issue}")
        if fix:
            lines.append(f"    Suggested fix: {fix}")

    lines.append("")
    lines.append("Spec entries for the affected segments:")
    for sid in affected_segments:
        entry = segments_by_id.get(sid)
        if entry:
            lines.append(f"- {_format_segment_line(entry['index'], entry)}")

    lines.append("")
    lines.append("Current submodel content (verbatim). Return rewritten blocks with")
    lines.append("the same `0 // SEGMENT_ID: <id>` marker and the same filename:")
    for sid, block in affected_segments.items():
        lines.append(f"--- segment_{sid}.ldr ---")
        lines.append(block.rstrip())
        lines.append("--- end segment_" + sid + ".ldr ---")
        lines.append("")

    lines.append("Return ONLY the rewritten MPD submodel blocks. No prose, no fences.")
    return "\n".join(lines)


def _partial_rewrite(spec: Dict[str, Any],
                     feedback: Dict[str, Any],
                     profile_adapter: Any,
                     output_dir: Path,
                     llm_config: Dict[str, Any],
                     prev_mpd_path: Path,
                     targeted_diffs: list) -> Optional[Tuple[Dict[str, Any], Path]]:
    """Attempt a surgical partial rewrite. Returns None on any fallback trigger."""
    from ldraw_tools.mpd_segments import parse_segment_blocks, rewrite_segment

    try:
        blocks = parse_segment_blocks(prev_mpd_path)
    except Exception as exc:
        logger.warning(f"[A2] Partial rewrite skipped: cannot parse previous MPD ({exc})")
        return None
    if not blocks:
        logger.info("[A2] Partial rewrite skipped: previous MPD has no submodels")
        return None

    affected_ids = []
    affected_blocks: Dict[str, str] = {}
    for d in targeted_diffs:
        sid = d.get("segment_id")
        if sid and sid in blocks and sid not in affected_blocks:
            _, _, raw = blocks[sid]
            affected_blocks[sid] = raw
            affected_ids.append(sid)
    if not affected_blocks:
        logger.info("[A2] Partial rewrite skipped: no diff references a known segment")
        return None

    prompt = _build_partial_prompt(spec, targeted_diffs, affected_blocks, profile_adapter)
    logger.info(f"[A2] Partial rewrite: targeting segments={affected_ids}, "
                f"{len(prompt)} bytes")

    base_url = (llm_config.get("base_url") or "http://localhost:6655/litellm").rstrip("/")
    secret = llm_config.get("secret", "")
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    model_name = ((llm_config.get("models") or {}).get("A2")) or "claude-haiku-4-5"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    if A2_MAX_TOKENS > 0:
        payload["max_tokens"] = A2_MAX_TOKENS
    url = f"{base_url}/v1/chat/completions"
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    except Exception as exc:
        logger.warning(f"[A2] Partial rewrite LLM call failed, falling back: {exc}")
        return None

    returned = _parse_returned_submodels(content)
    if not returned:
        logger.warning("[A2] Partial rewrite: model returned no submodel blocks; "
                       "falling back to full rewrite")
        return None
    # Must have rewritten at least one of the requested segments.
    overlap = set(affected_ids) & set(returned.keys())
    if not overlap:
        logger.warning(f"[A2] Partial rewrite: returned segments {sorted(returned)} "
                       f"do not overlap requested {affected_ids}; falling back")
        return None

    # Clone the previous MPD into the new iter dir and apply rewrites.
    import shutil
    new_mpd = output_dir / "design.mpd"
    shutil.copyfile(prev_mpd_path, new_mpd)
    rewritten = []
    for sid in overlap:
        try:
            rewrite_segment(new_mpd, sid, returned[sid])
            rewritten.append(sid)
        except Exception as exc:
            logger.warning(f"[A2] rewrite_segment({sid}) failed: {exc}; keeping previous block")

    mpd_text = new_mpd.read_text()
    segments = spec.get("segments", []) or []
    expected_ids = [_segment_id(s, i) for i, s in enumerate(segments)]
    matched, coverage = _count_submodels(mpd_text, expected_ids)

    plan = {
        "version": 1,
        "profile": profile_adapter.profile_name,
        "spec_segments": len(segments),
        "feedback_applied": True,
        "llm_model": model_name,
        "max_tokens": A2_MAX_TOKENS,
        "submodel_coverage": round(coverage, 3),
        "expected_segment_ids": expected_ids,
        "a2_prompt_bytes": len(prompt),
        "a2_mode": "partial_rewrite",
        "a2_rewritten_segments": rewritten,
        "sections": [{
            "name": "design.ldr",
            "description": "Partial rewrite of previous MPD",
            "lines": len(mpd_text.split("\n")),
        }],
    }
    (output_dir / "design.plan.json").write_text(json.dumps(plan, indent=2))
    logger.info(f"[A2] Partial rewrite applied to segments {rewritten}")
    return plan, new_mpd


def design_3d_with_llm(
    spec: Dict[str, Any],
    feedback: Optional[Dict[str, Any]],
    profile_adapter: Any,
    output_dir: Path,
    llm_config: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Path]:
    """
    A2: Designer 3D (code LLM, not VLM).
    Generates an LDraw MPD from spec + feedback, structured as one submodel per
    spec segment so Phases 3-4 can target physical gate and partial rewrites.

    When ``A2_PARTIAL_REWRITE`` is enabled and the feedback carries diffs with a
    ``segment_id`` and ``mpd_line_range`` pointing into a previous MPD
    (feedback['prev_mpd_path']), the generator attempts a surgical rewrite of
    only the affected submodels. Any inconsistency (parse failure, model not
    returning submodel blocks, overlap mismatch) falls back to a full rewrite
    with a WARN log.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    llm_config = llm_config or {}

    # Attempt partial rewrite when possible (plan §4 Phase 4).
    prev_mpd_path = None
    if feedback:
        pmp = feedback.get("prev_mpd_path")
        if pmp:
            prev_mpd_path = Path(pmp)
    targeted = _diffs_with_segments(feedback)
    if A2_PARTIAL_REWRITE and prev_mpd_path and prev_mpd_path.exists() and targeted:
        attempted = _partial_rewrite(
            spec=spec,
            feedback=feedback,
            profile_adapter=profile_adapter,
            output_dir=output_dir,
            llm_config=llm_config,
            prev_mpd_path=prev_mpd_path,
            targeted_diffs=targeted,
        )
        if attempted is not None:
            return attempted
        logger.info("[A2] Falling back to full rewrite")

    base_url = (llm_config.get("base_url") or "http://localhost:6655/litellm").rstrip("/")
    secret = llm_config.get("secret", "")

    segments = spec.get("segments", []) or []
    
    # FASE C: Extract few-shot recipes from llm_config if provided
    few_shot_recipes = None
    if llm_config and llm_config.get("few_shot_recipes"):
        few_shot_recipes = llm_config["few_shot_recipes"]
    
    prompt, num_segments = _build_prompt(spec, feedback, profile_adapter, few_shot_recipes)
    logger.info(f"[A2] Prompt built: {num_segments} segments, {len(prompt)} bytes")

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    model_name = ((llm_config.get("models") or {}).get("A2")) or "claude-haiku-4-5"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    if A2_MAX_TOKENS > 0:
        payload["max_tokens"] = A2_MAX_TOKENS

    url = f"{base_url}/v1/chat/completions"

    completion_tokens = 0
    try:
        log_msg = f"[A2] Calling {url} with {model_name}"
        if A2_MAX_TOKENS > 0:
            log_msg += f" (max_tokens={A2_MAX_TOKENS})"
        else:
            log_msg += " (max_tokens=unlimited)"
        logger.debug(log_msg)
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("No response from LLM")

        mpd_code = (choices[0].get("message", {}).get("content") or "").strip()
        usage = data.get("usage") or {}
        completion_tokens = int(usage.get("completion_tokens") or 0)
        
        # PHASE 4: Handle plan.json output from A2
        plan_json_data = None
        if A2_EMIT_PLAN_JSON:
            try:
                plan_json_data = json.loads(mpd_code)
                # If we got valid JSON, convert to MPD for gate/rendering
                from ldraw_tools.plan_migration import plan_to_mpd
                from ldraw_tools.geometry import profiles as get_geometry_profiles
                parts = get_geometry_profiles()
                mpd_code = plan_to_mpd(plan_json_data, parts)
                logger.info(f"[A2] Converted plan.json to MPD ({len(mpd_code)} chars)")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"[A2] plan.json conversion failed: {e}. Treating as raw MPD.")
                plan_json_data = None
        
        logger.info(f"[A2] Generated {len(mpd_code)} chars of LDraw code "
                    f"(completion_tokens={completion_tokens or 'n/a'}, mode={'plan.json' if plan_json_data else 'MPD'})")
        if completion_tokens and A2_MAX_TOKENS > 0 and completion_tokens >= 0.9 * A2_MAX_TOKENS:
            logger.warning(
                f"[A2] Output used {completion_tokens}/{A2_MAX_TOKENS} tokens "
                f"(>=90%); consider raising A2_MAX_TOKENS."
            )

    except Exception as e:
        logger.error(f"[A2] LLM call failed: {e}")
        # Fallback: simple placeholder (keeps the loop alive).
        mpd_code = """0 FILE design.ldr
0 Name: design.ldr
0 Placeholder generated after LLM failure
1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE
"""

    # Strip stray markdown fences if the model wrapped the MPD in ``` blocks.
    if mpd_code.startswith("```"):
        lines = mpd_code.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        mpd_code = "\n".join(lines)

    mpd_path = output_dir / "design.mpd"
    mpd_path.write_text(mpd_code)
    
    # PHASE 4: Save plan.json if A2 emitted it
    if plan_json_data:
        plan_json_path = output_dir / "a2_plan.json"
        plan_json_path.write_text(json.dumps(plan_json_data, indent=2))
        logger.info(f"[A2] Saved plan.json to {plan_json_path}")

    # Submodel coverage is a metric, not a gate (plan §4 Phase 2).
    expected_ids = [_segment_id(s, i) for i, s in enumerate(segments)]
    matched, coverage = _count_submodels(mpd_code, expected_ids)
    if expected_ids:
        logger.info(f"[A2] Submodel coverage: {matched}/{len(expected_ids)} "
                    f"({coverage:.0%})")

    plan = {
        "version": 1,
        "profile": profile_adapter.profile_name,
        "spec_segments": len(segments),
        "feedback_applied": feedback is not None,
        "llm_model": model_name,
        "max_tokens": A2_MAX_TOKENS,
        "submodel_coverage": round(coverage, 3),
        "expected_segment_ids": expected_ids,
        "a2_prompt_bytes": len(prompt),
        "a2_completion_tokens": completion_tokens,
        "a2_mode": "full_rewrite",
        "sections": [{
            "name": "design.ldr",
            "description": "Generated LDraw model",
            "lines": len(mpd_code.split("\n")),
        }],
    }

    plan_path = output_dir / "design.plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))

    logger.info(f"[A2] Generated {mpd_path.name} and {plan_path.name}")
    return plan, mpd_path
