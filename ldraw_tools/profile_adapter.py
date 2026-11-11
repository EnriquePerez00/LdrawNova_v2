"""Profile Adapter - Base interface for domain-specific loop customization."""
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import json


class ProfileAdapter:
    """Base adapter for profile-specific loop customization."""

    def __init__(self, profile_name: str, whitelist_path: Path, palette_path: Path):
        self.profile_name = profile_name
        self.whitelist_path = whitelist_path
        self.palette_path = palette_path
        self.whitelist: Dict[str, Any] = {}
        self.palette: Dict[str, Any] = {}
        self.scoring_weights: Dict[str, float] = {
            "color_fidelity": 0.30,
            "geometry_accuracy": 0.25,
            "proportion_accuracy": 0.25,
            "completeness": 0.10,
            "structure_integrity": 0.10,
        }
        self.evaluation_rubric: str = "Default rubric"
        self._load_resources()

    def _load_resources(self) -> None:
        """Load whitelist and palette from disk."""
        if self.whitelist_path.exists():
            self.whitelist = json.loads(self.whitelist_path.read_text())
        if self.palette_path.exists():
            self.palette = json.loads(self.palette_path.read_text())

    def get_scoring_weights(self) -> Dict[str, float]:
        """Return scoring weights for this profile."""
        return self.scoring_weights

    def get_evaluation_rubric(self) -> str:
        """Return evaluation rubric for the judge (A4)."""
        return self.evaluation_rubric

    def volume_to_part_matcher(self, segment: Dict[str, Any]) -> List[Tuple[str, float, str]]:
        """
        Match inferred_volume to candidate LEGO parts.
        
        Returns: [(part_id, fit_score, reason)]
        Override in subclasses to customize.
        """
        return []

    def get_color_by_hex(self, hex_code: str) -> Optional[Dict[str, Any]]:
        """Lookup LDraw color by hex code from palette."""
        colors = self.palette.get("colors", [])
        for color in colors:
            if color.get("hex", "").upper() == hex_code.upper():
                return color
        return None

    def validate_part_in_whitelist(self, part_id: str) -> bool:
        """Check if part_id is in whitelist."""
        for category, parts in self.whitelist.get("categories", {}).items():
            for part in parts:
                if part.get("id") == part_id:
                    return True
        return False
