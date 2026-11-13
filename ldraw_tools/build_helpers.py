"""Build helpers: LDU-aware coordinate and assembly construction toolkit.

Provides grid-aligned coordinate generation, stacking, and angular arrangements
for robust, scale-correct LEGO assembly plans. All coordinates are in LDU.

LDRAW COORDINATE SYSTEM:
  +X = right, +Z = forward, -Y = UP (vertical, measured downward)

UNIT CONVERSIONS:
  1 stud (horizontal) = 20 LDU in X or Z
  1 plate (thickness) = 8 LDU in Y
  1 brick (height) = 24 LDU in Y (3 plates)
"""

from __future__ import annotations
import math
from typing import List, Dict, Any, Tuple, Optional

# CONSTANTS (LDU conversions)
STUD = 20        # 1 stud = 20 LDU (horizontal)
PLATE = 8        # 1 plate = 8 LDU (vertical)
BRICK = 24       # 1 brick = 24 LDU (= 3 plates)

def studs(n: float) -> float:
    """Convert studs to LDU (X/Z coordinates)."""
    return round(n * STUD, 1)

def plates(n: float) -> float:
    """Convert plates to LDU (Y coordinates)."""
    return round(n * PLATE, 1)

def bricks(n: float) -> float:
    """Convert bricks to LDU (Y coordinates). 1 brick = 3 plates."""
    return round(n * BRICK, 1)

def validate_grid_alignment(x: float, z: float, y: float, *, tolerance: float = 0.1) -> bool:
    """Verify that coordinates align to the LEGO grid."""
    x_aligned = abs(x % STUD) < tolerance or abs((STUD - (x % STUD))) < tolerance
    z_aligned = abs(z % STUD) < tolerance or abs((STUD - (z % STUD))) < tolerance
    y_aligned = abs(y % PLATE) < tolerance or abs((PLATE - (y % PLATE))) < tolerance
    return x_aligned and z_aligned and y_aligned

def placement(
    pid: str,
    ref: str,
    colour: int,
    x: float,
    y: float,
    z: float,
    *,
    yaw: float = 0.0,
    matrix: Optional[List[List[float]]] = None,
    purpose: Optional[str] = None
) -> Dict[str, Any]:
    """Create a part placement with LDU-aligned coordinates."""
    if not validate_grid_alignment(x, z, y):
        pass  # In production, log as warning
    
    result = {
        "id": pid,
        "ref": ref,
        "colour": colour,
        "at": [round(x, 1), round(y, 1), round(z, 1)]
    }
    
    if matrix is not None:
        result["matrix"] = matrix
    elif yaw != 0:
        result["yaw"] = yaw
    
    if purpose is not None:
        result["purpose"] = purpose
    
    return result

def stack_on(
    pid: str,
    support_id: str,
    ref: str,
    colour: int,
    *,
    offset_studs: Tuple[float, float] = (0, 0),
    purpose: Optional[str] = None
) -> Dict[str, Any]:
    """Create a placement stacked on top of a support piece using stud alignment."""
    result = {
        "id": pid,
        "ref": ref,
        "colour": colour,
        "on": support_id,
        "offset_studs": [round(offset_studs[0], 1), round(offset_studs[1], 1)]
    }
    if purpose is not None:
        result["purpose"] = purpose
    return result

def ring(
    pid_prefix: str,
    ref: str,
    colours: List[int],
    radius_studs: float,
    y: float,
    count: int = 8,
    *,
    start_angle_deg: float = 0.0,
    purpose_template: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Generate a ring of parts arranged in circular/octagonal pattern with yaw.
    
    Each part is rotated (yaw) to point outward from the ring center.
    """
    radius_ldu = studs(radius_studs)
    placements = []
    
    for i in range(count):
        angle_deg = start_angle_deg + (360 / count) * i
        angle_rad = math.radians(angle_deg)
        
        x = radius_ldu * math.cos(angle_rad)
        z = radius_ldu * math.sin(angle_rad)
        yaw = (angle_deg + 90) % 360  # Normalize to [0, 360) for schema compliance
        colour = colours[i % len(colours)]
        purpose = None
        if purpose_template:
            purpose = purpose_template.format(i=i, angle=angle_deg)
        
        placements.append(placement(
            f"{pid_prefix}_{i}",
            ref,
            colour,
            round(x, 1),
            y,
            round(z, 1),
            yaw=yaw,
            purpose=purpose
        ))
    
    return placements

def octagon(
    pid_prefix: str,
    ref: str,
    colours: List[int],
    radius_studs: float,
    y: float,
    *,
    start_angle_deg: float = 0.0,
    purpose_template: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Convenience function: generate an octagonal ring (8 parts)."""
    return ring(
        pid_prefix,
        ref,
        colours,
        radius_studs,
        y,
        count=8,
        start_angle_deg=start_angle_deg,
        purpose_template=purpose_template
    )

def pyramid(
    pid_prefix: str,
    ref_by_layer: List[str],
    colours_by_layer: List[List[int]],
    radii_studs: List[float],
    y_bottom: float,
    heights_studs: List[float],
    count_per_layer: int = 8,
    *,
    start_angle_deg: float = 0.0,
    purpose_template: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Generate a pyramid/cone structure with tapering rings."""
    if not (len(ref_by_layer) == len(colours_by_layer) == len(radii_studs) == len(heights_studs)):
        raise ValueError("All pyramid layer lists must have the same length")
    
    placements = []
    y_current = y_bottom
    
    for layer_idx, (ref, colours, radius_studs, height_studs) in enumerate(
        zip(ref_by_layer, colours_by_layer, radii_studs, heights_studs)
    ):
        layer_placements = ring(
            f"{pid_prefix}_layer_{layer_idx}",
            ref,
            colours,
            radius_studs,
            y_current,
            count=count_per_layer,
            start_angle_deg=start_angle_deg,
            purpose_template=purpose_template or f"Pyramid layer {layer_idx}"
        )
        placements.extend(layer_placements)
        y_current -= plates(height_studs / PLATE)
    
    return placements

def apex_point(
    pid: str,
    ref: str,
    colour: int,
    x: float,
    y: float,
    z: float,
    *,
    purpose: Optional[str] = None
) -> Dict[str, Any]:
    """Create a single pointed apex piece."""
    return placement(pid, ref, colour, x, y, z, purpose=purpose or "Apex point")
