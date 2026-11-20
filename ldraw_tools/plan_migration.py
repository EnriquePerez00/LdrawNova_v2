"""MPD to Plan.json Converter - Roadmap for Phase 4 Refactor (FUTURE)

AUDIT FIX (Phase 4 - Deferred for now): Currently A2 emits raw MPD lines.
This module provides utilities to support a future migration to plan.json-based
generation, where A2 outputs a declarative assembly plan instead of coordinates.

The migration would involve:
1. Modifying A2's prompt to request plan.json structure (on/snap/attach directives)
2. Parsing A2's plan.json in design_generator.py
3. Calling builder.build_plan() instead of directly parsing MPD
4. Updating A1 (describe_gt) to emit plan.json instead of ad-hoc structure

Benefits:
- Deterministic coordinate calculation from geometry
- Automatic collision detection before rendering
- Decoupling A2 from LDraw coordinate system details
- Cleaner feedback loops (A4 can suggest semantic "move segment X on top of Y")

Current state: RAW MPD (coordinates embedded in A2 output)
Future state: DECLARATIVE PLAN (A2 specifies logic; builder calculates coordinates)

This file is a placeholder for Phase 4 implementation.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def mpd_to_plan_skeleton(mpd_text: str, profile_name: str = "generic") -> Dict[str, Any]:
    """Convert a raw MPD file to a skeleton plan.json (for reference/migration testing).
    
    FUTURE USE: Once A2 matures, A1's spec.json could be converted to a full plan
    and passed to build_plan() directly instead of going through A2's coordinate emission.
    
    Args:
        mpd_text: Raw LDraw/MPD code from A2
        profile_name: Profile identifier
    
    Returns:
        A skeleton plan.json dict (not validated against schema, for reference only)
    """
    # This is a placeholder showing the structure.
    # Real implementation would parse MPD and infer placement logic.
    plan = {
        "author": "LdrawNova A2",
        "description": f"Converted from raw MPD ({profile_name})",
        "sections": [
            {
                "name": "design",
                "description": f"Design ({profile_name})",
                "steps": [
                    # Each step would contain "on"/"snap"/"attach" directives
                ]
            }
        ]
    }
    return plan


def plan_to_mpd(plan: Dict[str, Any], parts: Any, instance_limit: int = 100000) -> str:
    """Convert a plan.json to MPD using builder.build_plan().
    
    This is the INVERSE of mpd_to_plan_skeleton: it takes a semantic plan
    and generates the actual LDraw code.
    
    Args:
        plan: Validated plan.json dict
        parts: pyldraw3 Parts instance
        instance_limit: Budget for coordinate resolution
    
    Returns:
        MPD text (LDraw code) ready for rendering
    """
    from .builder import build_plan
    try:
        model = build_plan(plan, parts, instance_limit=instance_limit)
        # Render model to LDraw text
        from io import StringIO
        out = StringIO()
        model.write(out)
        return out.getvalue()
    except Exception as e:
        logger.error(f"[plan_to_mpd] Failed: {e}")
        raise


# PHASE 4 MIGRATION CHECKLIST (for future developers):
# [ ] Modify a2_prompt_v2.py: ask A2 to emit plan.json instead of MPD
# [ ] Add JSON parsing in design_generator.py after A2 response
# [ ] Call plan_to_mpd(a2_plan, parts) instead of direct MPD parsing
# [ ] Update A1 (agent_roles.describe_gt) to emit plan.json with topological structure
# [ ] Add tests to verify round-trip: spec.json → A2 plan → build_plan() → renders correctly
# [ ] Update physical_gate to work with plan.json before MPD generation
# [ ] Migrate learned_rules to emit plan.json fix directives, not raw coordinate assignments
