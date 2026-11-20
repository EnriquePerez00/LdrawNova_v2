"""Gate-specific diff enrichment: convert physical constraints into A2-actionable feedback.

When the physical gate detects issues (penetrations, floating islands), convert them
into concrete suggestions that A2 can use to fix the design in the next iteration.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["enrich_gate_diffs_with_suggestions"]


def enrich_gate_diffs_with_suggestions(
    diffs: List[Dict[str, Any]],
    gate_result: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Enrich gate-generated diffs with concrete A2-actionable suggestions.
    
    Args:
        diffs: List of diffs from PhysicalGate (has severity, but minimal guidance)
        gate_result: PhysicalGateResult object (optional, for context)
    
    Returns:
        Enhanced diffs with actionable suggestions for A2.
    """
    enriched = []
    
    for diff in (diffs or []):
        d = dict(diff)  # Copy
        sev = d.get("severity", 0)
        issue_type = d.get("type", d.get("issue", "unknown")).lower()
        
        # Generate actionable suggestion based on issue type
        if "penetration" in issue_type:
            d["suggestion"] = (
                "Reduce brick overlap: shift parts vertically or spatially to eliminate penetrations. "
                "Check stud alignment and ensure parts connect without overlapping."
            )
        elif "floating" in issue_type or "island" in issue_type:
            d["suggestion"] = (
                "Connect floating islands to the main structure using studs, plates, or connectors. "
                "Ensure all parts are physically connected via standard LEGO connectivity."
            )
        elif "orientation" in issue_type or "rotation" in issue_type:
            d["suggestion"] = (
                "Correct brick orientations to match LEGO assembly standards. "
                "Bricks should stack vertically on studs or plates, not float in arbitrary rotations."
            )
        elif "connection" in issue_type or "stud" in issue_type:
            d["suggestion"] = (
                "Use proper LEGO connections: studs, anti-studs, and plates must align. "
                "Add intermediate bricks or connectors if direct stud alignment is impossible."
            )
        else:
            # Generic fallback
            d["suggestion"] = (
                "Fix the identified issue by adjusting brick positions, orientations, or connections. "
                "Refer to standard LEGO assembly rules for proper part placement."
            )
        
        # Mark source for debugging
        d["source"] = "physical_gate"
        
        enriched.append(d)
    
    return enriched


if __name__ == "__main__":
    # Quick test
    test_diffs = [
        {"severity": 4, "type": "penetration", "issue": "Brick penetrates floor"},
        {"severity": 3, "type": "floating_island", "issue": "3 parts not connected"},
    ]
    
    enriched = enrich_gate_diffs_with_suggestions(test_diffs)
    for d in enriched:
        print(f"[{d['severity']}] {d['type']}: {d.get('suggestion')}")
