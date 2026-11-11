"""Brand Logo Profile Adapter - Specialized for logo design loop."""
from typing import Any, Dict, List, Tuple
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from profile_adapter import ProfileAdapter


class BrandLogoAdapter(ProfileAdapter):
    """Profile adapter for brand_logo domain."""

    def __init__(self, whitelist_path: Path, palette_path: Path):
        super().__init__("brand_logo", whitelist_path, palette_path)
        
        # Brand logo prioritizes color + proportion
        self.scoring_weights = {
            "color_fidelity": 0.35,        # Color is CRITICAL for logos
            "geometry_accuracy": 0.20,
            "proportion_accuracy": 0.30,
            "completeness": 0.10,
            "structure_integrity": 0.05,
        }
        
        self.evaluation_rubric = (
            "BRAND LOGO EVALUATION RUBRIC:\n"
            "1. COLOR FIDELITY (ΔE < 20 per segment is target)\n"
            "2. PROPORTION ACCURACY (bbox aspect ratio within ±5%)\n"
            "3. GEOMETRY: No overlaps, component_count=1, proper chaflanes\n"
            "4. COMPLETENESS: All segments present, no missing elements\n"
            "5. KERNING/SPACING: Uniform stroke thickness, proper letter spacing\n"
            "6. CURVATURE ACCURACY: Macaroni radii (R=1..4) match target\n"
            "7. LAYER STRATIFICATION: Relief depth matches GT (0, -8, -16, -24 LDU)\n"
        )

    def volume_to_part_matcher(self, segment: Dict[str, Any]) -> List[Tuple[str, float, str]]:
        """
        Match segment's inferred_volume to candidate parts from whitelist.
        
        For brand logos:
        - flat_tile → tiles from tiles_flat category
        - curved_arc → macaroni tiles (R=1,2,3,4 mapped to part IDs)
        - slope → curved slopes (11477, 15068, 50950)
        """
        candidates = []
        inferred = segment.get("inferred_volume", {})
        primitive = inferred.get("primitive", "flat_tile")
        
        if primitive == "flat_tile":
            # Flat tiles are always good matches for logos
            for part in self.whitelist.get("categories", {}).get("tiles_flat", []):
                candidates.append((part["id"], 95.0, "flat tile match"))
        
        elif primitive == "curved_arc":
            radius = inferred.get("curvature_radius_studs", 2)
            # Map radius to macaroni tile (R=1→25269, R=2→27925, R=3→27507, R=4→48092)
            radius_to_part = {1: "25269.dat", 2: "27925.dat", 3: "27507.dat", 4: "48092.dat"}
            part_id = radius_to_part.get(int(radius), "27925.dat")
            fit_score = 100.0 if int(radius) == int(inferred.get("curvature_radius_studs", 2)) else 80.0
            candidates.append((part_id, fit_score, f"macaroni R={radius}"))
        
        elif primitive == "slope":
            # Curved slopes for organic transitions
            angle = inferred.get("slope_angle_degrees", 45)
            # 11477 (2x1), 15068 (2x2), 50950 (3x1) are common choices
            candidates.extend([
                ("11477.dat", 85.0, "curved slope 2x1"),
                ("15068.dat", 90.0, "curved slope 2x2"),
                ("50950.dat", 80.0, "curved slope 3x1"),
            ])
        
        else:
            # Default: offer flat tiles as fallback
            for part in self.whitelist.get("categories", {}).get("tiles_flat", [])[:3]:
                candidates.append((part["id"], 70.0, "fallback flat"))
        
        return candidates[:5]  # Return top 5 candidates
