"""Incident taxonomy: deterministic classification of root causes from diffs.

Maps physical_gate diffs (collisions, floating islands) to generalized categories
that can be learned and applied across multiple sets/MOCs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Semilla: categorías deterministas reconocidas
INCIDENT_CATEGORIES = {
    "SAME_Z_LAYER_COLLISION": {
        "description": "Multiple segments at same spatial depth (Z-axis in LDraw view) collide; requires semantic repositioning",
        "detector": "_detect_same_z_collision",
        "fix_pattern": "Use topology (attached_to + attachment_face) or apply snap_report/apply_snap to find valid encaje; do NOT assign arbitrary Z coordinates",
    },
    "INTRA_SEGMENT_OVERLAP": {
        "description": "Parts within same segment penetrate each other; requires internal geometry review",
        "detector": "_detect_intra_segment_overlap",
        "fix_pattern": "Review part placement within segment using connectivity constraints or apply snap_report; standardize spacing only after collision-free placement",
    },
    "FLOATING_ISLAND": {
        "description": "Connected component disconnected from base assembly",
        "detector": "_detect_floating_island",
        "fix_pattern": "Lower island by distance_to_base or add bridge piece to main",
    },
    "IRREGULAR_SPACING": {
        "description": "Parts use inconsistent spacing (mix of 20/40 LDU etc)",
        "detector": "_detect_irregular_spacing",
        "fix_pattern": "Standardize part spacing to uniform 40 LDU grid",
    },
}


def _detect_same_z_collision(diff: Dict[str, Any]) -> bool:
    """Match: collision between different segments at same Z."""
    if diff.get("type") != "collision":
        return False
    
    seg_a = diff.get("evidence", {}).get("segment_a", "")
    seg_b = diff.get("evidence", {}).get("segment_b", "")
    
    # Different segments = cross-segment collision
    if not seg_a or not seg_b or seg_a == seg_b:
        return False
    
    # Heuristic: depth > 10 LDU suggests same Z-layer issue (full brick overlap)
    depth = diff.get("evidence", {}).get("depth_ldu", 0)
    if depth and depth > 8:  # > 1 stud
        return True
    
    return False


def _detect_intra_segment_overlap(diff: Dict[str, Any]) -> bool:
    """Match: collision within same segment."""
    if diff.get("type") != "collision":
        return False
    
    seg_a = diff.get("evidence", {}).get("segment_a", "")
    seg_b = diff.get("evidence", {}).get("segment_b", "")
    
    return seg_a == seg_b and bool(seg_a)


def _detect_floating_island(diff: Dict[str, Any]) -> bool:
    """Match: floating island (disconnected component)."""
    return diff.get("type") == "floating_island"


def _detect_irregular_spacing(diff: Dict[str, Any]) -> bool:
    """Match: parts with non-uniform spacing (future: extract from MPD analysis).
    
    Currently placeholder; will be populated via root_cause_analyzer if needed.
    """
    # Could expand this by analyzing coordinate histograms from MPD
    return False


# Build detector map
DETECTORS = {
    name: globals()[cat["detector"]]
    for name, cat in INCIDENT_CATEGORIES.items()
}


class IncidentClassifier:
    """Classify diffs into generalized root-cause categories."""
    
    def __init__(self):
        self.known_categories = set(INCIDENT_CATEGORIES.keys())
        logger.info(f"[IncidentClassifier] Initialized with {len(self.known_categories)} categories")
    
    def classify(self, diff: Dict[str, Any]) -> Tuple[Optional[str], float]:
        """Classify a diff into a known category.
        
        Args:
            diff: Diff dict from loop (type, evidence, severity, etc)
        
        Returns:
            (category_name, confidence) where confidence is 0.0-1.0
            or (None, 0.0) if no category matches
        """
        for category_name, detector_fn in DETECTORS.items():
            if detector_fn(diff):
                # Known category detected with high confidence
                return (category_name, 0.95)
        
        # No known category
        logger.debug(f"[IncidentClassifier] Diff unclassified: {diff.get('type')}")
        return (None, 0.0)
    
    def get_category_info(self, category: str) -> Optional[Dict[str, Any]]:
        """Get info for a category (description, fix pattern)."""
        return INCIDENT_CATEGORIES.get(category)
    
    def register_new_category(
        self,
        name: str,
        description: str,
        fix_pattern: str,
        detector_fn=None,
    ) -> None:
        """Register a new category (typically from root_cause_analyzer).
        
        Args:
            name: category identifier (e.g. "WEIRD_BRICK_STACKING")
            description: human-readable description
            fix_pattern: generalized fix (template without IDs/coords)
            detector_fn: optional callable to detect future incidences of this type
        """
        if name in self.known_categories:
            logger.warning(f"[IncidentClassifier] Category {name} already exists")
            return
        
        INCIDENT_CATEGORIES[name] = {
            "description": description,
            "detector": f"custom_{name}",
            "fix_pattern": fix_pattern,
        }
        
        if detector_fn:
            DETECTORS[name] = detector_fn
        else:
            # Fallback: no detector; will need LLM for future matches
            DETECTORS[name] = lambda diff: False
        
        self.known_categories.add(name)
        logger.info(f"[IncidentClassifier] Registered new category: {name}")
