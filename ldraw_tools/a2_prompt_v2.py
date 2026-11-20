"""A2 Prompt Generator - LDraw Coordinate System Compliance (FASE D-FIXED)

This module provides improved prompt construction that correctly instructs A2
about the LDraw coordinate system and proper segment assembly without arbitrary
Z-layer separation (which was causing floating islands and broken models).

CRITICAL FIX (Audit):
- REMOVED: Incorrect Z=i×40 rule (mixed up axes, created floating islands)
- ADDED: Correct LDraw coordinate system explanation (-Y is up, not Z)
- ADDED: Topology-aware assembly instructions using attached_to/attachment_face
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

def build_ldraw_coordinate_system_block() -> str:
    """Explain the CORRECT LDraw coordinate system to A2."""
    return """LDRAW COORDINATE SYSTEM (IMMUTABLE - DO NOT IGNORE):
    
1. Axes:  +X = right,  +Z = forward/away,  -Y = UP (decreasing Y means higher)
2. Units: 1 stud = 20 LDU in X or Z direction
          1 brick height = 24 LDU in Y direction (down)
          1 plate height = 8 LDU in Y direction (down)
3. Rotation: Use right-hand rule. Standard brick at origin: position (0,0,0), no rotation.

⚠️ CRITICAL: The Z-axis is for DEPTH (front/back), NOT for vertical stacking.
Vertical stacking uses NEGATIVE Y values. Do NOT separate segments by Z coordinate.

4. Assembly:
   - If segment_head goes ON TOP OF segment_torso:
     segment_head's lowest Y should be <= segment_torso's highest Y
     Example: torso_bottom_Y=24, head_position_Y=0 (head sits ON torso)
   - Use actual geometric snapping (connectivity.snap_report) when available
   - If using raw coordinates, align studs/receptacles exactly:
     male stud at (x,y,z) ↔ female receptacle at (x,y-24,z)  [1 brick apart]
"""

def build_assembly_topology_block(segments: List[Dict[str, Any]]) -> str:
    """Generate instructions for semantic assembly: attached_to + attachment_face."""
    if not segments or len(segments) <= 1:
        return ""
    
    # Check if spec includes topology (attached_to, attachment_face) from A1
    has_topology = any(seg.get("attached_to") or seg.get("attachment_face") for seg in segments)
    
    if not has_topology:
        return """ASSEMBLY INSTRUCTION (when topology unavailable):
- All segments start at Z=0 (depth coordinate)
- Arrange segments in decreasing Y to stack vertically
- Use part-to-part connectivity: align studs (male) with receptacles (female)
"""
    
    # Build instructions from topology
    instructions = "ASSEMBLY TOPOLOGY (from Ground Truth analysis):\n"
    for seg in segments:
        seg_id = seg.get("id") or seg.get("name", "unknown")
        attached_to = seg.get("attached_to", "base_plate")
        face = seg.get("attachment_face", "bottom")
        instructions += f"- {seg_id}: attach to {attached_to} on {face} face\n"
    
    return instructions

def build_geometric_constraints_block(segments: List[Dict[str, Any]]) -> str:
    """Generate geometric constraints (WITHOUT the broken Z=i*40 rule).
    
    NEW APPROACH: Rely on LDraw coordinate system + connectivity snapping
    instead of arbitrary geometric layer assignment.
    """
    num_segs = len(segments)
    if num_segs <= 1:
        return ""
    
    constraints = "GEOMETRIC CONSTRAINTS (COLLISION AVOIDANCE):\n\n"
    
    constraints += "1. NO overlapping bounding boxes in 3D space\n"
    constraints += "2. Parts must snap at connection points (studs-to-receptacles)\n"
    constraints += "3. Use standard LDraw library parts only (.dat files)\n"
    constraints += "4. Each part's position must be aligned to stud grid (multiples of 20 LDU in X/Z, 8 or 24 LDU in Y)\n"
    constraints += "5. Do NOT artificially separate segments by Z-coordinate\n"
    constraints += "6. If segments must not touch, move them in X or Z (lateral), not Z (depth coordinate)\n"
    
    return constraints

if __name__ == "__main__":
    # Test
    test_segments = [{"id": "seg_0", "name": "torso"}, {"id": "seg_1", "name": "head", "attached_to": "seg_0", "attachment_face": "top"}]
    print("=== Coordinate System ===")
    print(build_ldraw_coordinate_system_block())
    print("\n=== Topology ===")
    print(build_assembly_topology_block(test_segments))
    print("\n=== Constraints ===")
    print(build_geometric_constraints_block(test_segments))
