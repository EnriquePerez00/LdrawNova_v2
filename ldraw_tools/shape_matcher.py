"""Shape Matcher - Quantitative matching of inferred volumes to LEGO parts."""
from typing import Any, Dict, List, Tuple
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class ShapeMatcher:
    """
    Matches inferred 3D volumes to LEGO parts from whitelist.
    Uses quantitative fit scoring based on geometric properties.
    """

    def __init__(self, whitelist_path: Path):
        self.whitelist_path = whitelist_path
        self.parts_index: List[Dict[str, Any]] = []
        self._load_and_index_parts()

    def _load_and_index_parts(self) -> None:
        """Load whitelist and build indexed part catalog."""
        if not self.whitelist_path.exists():
            logger.warning(f"Whitelist not found: {self.whitelist_path}")
            return
        
        data = json.loads(self.whitelist_path.read_text())
        for category, parts in data.get("categories", {}).items():
            for part in parts:
                indexed_part = {
                    "part_id": part.get("id"),
                    "name": part.get("name", ""),
                    "category": category,
                    "dims": part.get("dims", []),
                    "role": part.get("role", ""),
                }
                self.parts_index.append(indexed_part)

    def match(self, inferred_volume: Dict[str, Any]) -> List[Tuple[str, float, str]]:
        """
        Match an inferred volume to candidate parts.
        
        Args:
            inferred_volume: dict with {primitive, depth_plates, curvature_radius_studs, slope_angle_degrees, top_finish}
        
        Returns:
            [(part_id, fit_score 0-100, reason)]
        """
        candidates = []
        primitive = inferred_volume.get("primitive", "flat_tile")
        
        if primitive == "flat_tile":
            candidates = self._match_flat_tile(inferred_volume)
        elif primitive == "curved_arc":
            candidates = self._match_curved_arc(inferred_volume)
        elif primitive == "slope":
            candidates = self._match_slope(inferred_volume)
        elif primitive == "rounded_corner":
            candidates = self._match_rounded_corner(inferred_volume)
        else:
            # Fallback: return any tile
            candidates = [(p["part_id"], 50.0, "fallback") for p in self.parts_index if "tile" in p.get("category", "").lower()][:3]
        
        return sorted(candidates, key=lambda x: -x[1])[:5]  # Return top 5 sorted by score

    def _match_flat_tile(self, volume: Dict) -> List[Tuple[str, float, str]]:
        """Match to flat tiles."""
        candidates = []
        target_dims = volume.get("dims", [1, 1])
        
        for part in self.parts_index:
            if "tiles_flat" not in part.get("category", ""):
                continue
            part_dims = part.get("dims", [1, 1])
            
            # Score based on dimension match
            dim_diff = abs(part_dims[0] - target_dims[0]) + abs(part_dims[1] - target_dims[1])
            fit_score = max(0, 100 - dim_diff * 10)
            
            if fit_score > 50:
                candidates.append((part["part_id"], fit_score, f"flat tile {part_dims[0]}x{part_dims[1]}"))
        
        return candidates

    def _match_curved_arc(self, volume: Dict) -> List[Tuple[str, float, str]]:
        """Match to macaroni tiles (curved arcs)."""
        candidates = []
        target_radius = volume.get("curvature_radius_studs", 2)
        
        # Map radii to known macaroni tiles
        radius_map = {
            1: ("25269.dat", "Round 1/4"),
            2: ("27925.dat", "Macaroni 2x2"),
            3: ("27507.dat", "Macaroni 3x3"),
            4: ("48092.dat", "Macaroni 4x4"),
        }
        
        for radius, (part_id, name) in radius_map.items():
            diff = abs(radius - target_radius)
            fit_score = max(0, 100 - diff * 20)
            candidates.append((part_id, fit_score, f"{name} (R={radius})"))
        
        return candidates

    def _match_slope(self, volume: Dict) -> List[Tuple[str, float, str]]:
        """Match to curved slopes."""
        candidates = []
        target_angle = volume.get("slope_angle_degrees", 45)
        
        # Known curved slopes with approximate angles
        slope_map = [
            ("11477.dat", 45, "Curved 2x1"),
            ("15068.dat", 30, "Curved 2x2"),
            ("50950.dat", 20, "Curved 3x1"),
            ("24201.dat", 315, "Inverted 2x1"),
        ]
        
        for part_id, angle, name in slope_map:
            angle_diff = abs(angle - target_angle)
            fit_score = max(0, 100 - angle_diff)
            candidates.append((part_id, fit_score, f"{name} (~{angle}°)"))
        
        return candidates

    def _match_rounded_corner(self, volume: Dict) -> List[Tuple[str, float, str]]:
        """Match to rounded corner tiles."""
        candidates = []
        for part in self.parts_index:
            if "rounded" in part.get("role", "").lower() or "corner" in part.get("role", "").lower():
                candidates.append((part["part_id"], 90.0, part.get("role", "corner")))
        
        return candidates
