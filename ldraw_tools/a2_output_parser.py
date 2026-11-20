"""A2 Output Parser: Convert raw MPD or structured output to plan.json (PHASE 4).

AUDIT FIX (Phase 4 - Implementation):
Previously, A2 emitted raw MPD lines with embedded coordinates.
Now, A2 either:
  a) Outputs plan.json directly (ideal), or
  b) Outputs structured placement directives we parse into plan.json

This module bridges MPD→plan.json and provides deterministic coordinate calculation.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_a2_mpd_to_plan(mpd_text: str, segments: List[Dict[str, Any]], 
                         profile_name: str = "generic") -> Dict[str, Any]:
    """Convert raw A2 MPD output to plan.json structure.
    
    STRATEGY: Extract part placements from MPD and infer assembly topology
    from spec segments' attached_to/attachment_face.
    
    Args:
        mpd_text: Raw LDraw/MPD code from A2
        segments: Spec segments list with id, name, attached_to, attachment_face
        profile_name: Profile identifier
    
    Returns:
        plan.json dict (may be incomplete if topology is not discoverable)
    """
    plan = {
        "author": "LdrawNova A2",
        "description": f"Auto-converted from MPD ({profile_name})",
        "sections": [
            {
                "name": "design",
                "description": f"Design ({profile_name})",
                "author": "LdrawNova A2",
                "steps": [],
            }
        ]
    }
    
    # Parse MPD to extract placements (lines like "1 <color> <x> <y> <z> <matrix> <part>")
    placements = _extract_placements_from_mpd(mpd_text, segments)
    
    # Build steps from segments (each segment gets a "step" with its placements)
    if placements:
        plan["sections"][0]["steps"] = _build_steps_from_placements(placements, segments)
    
    logger.info(f"[A2OutputParser] Converted MPD to plan.json: {len(placements)} placements in {len(plan['sections'][0]['steps'])} steps")
    return plan


def _extract_placements_from_mpd(mpd_text: str, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract part placements from raw MPD code.
    
    Format: 1 <color> <x> <y> <z> <m00> <m01> <m02> <m10> <m11> <m12> <m20> <m21> <m22> <part.dat>
    """
    placements = []
    
    # Regex to match LDraw type-1 (part placement) lines
    # 1 <colour> <x> <y> <z> <a> <b> <c> <d> <e> <f> <g> <h> <i> <part>
    pattern = r'^\s*1\s+(\d+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\d\-\.eE]+)\s+([\\w\\.\\-]+\\.dat)$'
    
    for line in mpd_text.split('\n'):
        match = re.match(pattern, line)
        if not match:
            continue
        
        color, x, y, z, m00, m01, m02, m10, m11, m12, m20, m21, m22, part = match.groups()
        
        placement = {
            "id": f"part_{len(placements)}",
            "ref": part,
            "colour": int(color),
            "at": [float(x), float(y), float(z)],
            "matrix": [
                [float(m00), float(m01), float(m02)],
                [float(m10), float(m11), float(m12)],
                [float(m20), float(m21), float(m22)],
            ]
        }
        placements.append(placement)
    
    return placements


def _build_steps_from_placements(placements: List[Dict[str, Any]], 
                                  segments: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group placements into steps based on segment topology.
    
    If spec has attached_to/attachment_face, use that to order steps.
    Otherwise, emit one step with all placements.
    """
    # Heuristic: check if we have meaningful topology
    has_topology = any(seg.get("attached_to") or seg.get("attachment_face") for seg in segments)
    
    if not has_topology or len(segments) <= 1:
        # Simple case: all parts in one step
        return [placements]
    
    # TODO: Advanced: partition placements by segment topology
    # For now, return all in one step
    return [placements]


def a2_plan_json_mode_prompt() -> str:
    """Return instruction block for A2 to emit plan.json instead of raw MPD.
    
    Use this in design_generator._build_prompt() when A2_EMIT_PLAN_JSON=true
    """
    return """PLAN.JSON OUTPUT FORMAT (REQUIRED FOR PHASE 4):

Instead of emitting raw LDraw MPD, emit a structured plan.json that describes
the assembly topology and placement logic. This allows deterministic coordinate
calculation and collision detection BEFORE rendering.

Example plan.json structure:
{
  "author": "LdrawNova A2",
  "description": "Design assembly",
  "sections": [
    {
      "name": "design",
      "description": "Main assembly",
      "author": "LdrawNova A2",
      "steps": [
        [
          {"id": "part_0", "ref": "3001.dat", "colour": 16, "at": [0, 0, 0], "matrix": [[1,0,0],[0,1,0],[0,0,1]]},
          {"id": "part_1", "ref": "3002.dat", "colour": 4, "at": [0, -24, 0], "matrix": [[1,0,0],[0,1,0],[0,0,1]]}
        ]
      ]
    }
  ]
}

RULES:
1. Each part placement has: id, ref (part code), colour (LDraw color ID), at (x,y,z), matrix (3x3 rotation)
2. Group placements into "steps" representing assembly order
3. Use "on" directive in steps if part should snap: {"on": [part_id, feature_id]} 
4. Return ONLY valid JSON, no markdown, no explanation
"""
