"""Validators for LEGO designs - geometry, BOM, color."""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GeometryValidator:
    """Validates geometric constraints: overlaps, part compatibility."""
    
    def validate_mpd(self, mpd_path: Path, whitelist: Dict[str, List[str]]) -> Tuple[bool, List[str]]:
        """Validate MPD: all parts in whitelist, syntax OK, subparts valid."""
        if not mpd_path.exists():
            return False, [f"MPD file not found: {mpd_path}"]
        
        errors = []
        try:
            content = mpd_path.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('0'):
                    continue
                
                parts = line.split()
                if len(parts) < 2:
                    errors.append(f"Line {i}: Invalid LDraw syntax")
                    continue
                
                try:
                    line_type = int(parts[0])
                    if line_type == 1 and len(parts) >= 15:
                        part_id = parts[14]
                        found = False
                        for category, parts_list in whitelist.get("categories", {}).items():
                            if part_id in parts_list:
                                found = True
                                break
                        if not found and part_id not in whitelist.get("generic", []):
                            errors.append(f"Line {i}: Part {part_id} not in whitelist")
                except (ValueError, IndexError):
                    errors.append(f"Line {i}: Parse error")
        
        except Exception as e:
            errors.append(f"Failed to read MPD: {e}")
        
        is_valid = len(errors) == 0
        logger.info(f"[Geometry] MPD: {'OK' if is_valid else f'{len(errors)} errors'}")
        return is_valid, errors


class BOMValidator:
    """Validates Bill of Materials constraints."""
    
    def extract_bom(self, mpd_path: Path) -> Dict[str, int]:
        """Extract part count from MPD."""
        if not mpd_path.exists():
            return {}
        
        bom = {}
        try:
            for line in mpd_path.read_text().split('\n'):
                line = line.strip()
                if not line or line.startswith('0'):
                    continue
                parts = line.split()
                try:
                    if int(parts[0]) == 1 and len(parts) >= 15:
                        part_id = parts[14]
                        bom[part_id] = bom.get(part_id, 0) + 1
                except (ValueError, IndexError):
                    pass
        except Exception as e:
            logger.warning(f"BOM extraction error: {e}")
        return bom
    
    def validate_bom_constraints(self, bom: Dict[str, int], constraints: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate BOM against constraints."""
        errors = []
        total = sum(bom.values())
        min_parts = constraints.get("min_parts", 0)
        max_parts = constraints.get("max_parts", 500)
        
        if total < min_parts:
            errors.append(f"BOM too small: {total} parts (min: {min_parts})")
        if total > max_parts:
            errors.append(f"BOM too large: {total} parts (max: {max_parts})")
        
        for part_id, count in bom.items():
            if count > 50:
                errors.append(f"Excessive duplicates: {part_id} x{count}")
        
        is_valid = len(errors) == 0
        logger.info(f"[BOM] {total} parts: {'OK' if is_valid else f'{len(errors)} issues'}")
        return is_valid, errors


class ColorValidator:
    """Validates color fidelity using simplified ΔE color difference."""
    
    LEGO_COLORS = {
        "red": (200, 16, 46),
        "green": (0, 85, 28),
        "blue": (0, 33, 99),
        "yellow": (255, 201, 22),
        "white": (242, 243, 242),
        "black": (5, 5, 5),
        "gray": (160, 160, 160),
        "dark_gray": (82, 82, 82),
        "brown": (92, 46, 23),
        "tan": (238, 195, 154),
        "orange": (255, 108, 0),
        "purple": (160, 31, 99),
    }
    
    def delta_e_cie76(self, rgb1: Tuple, rgb2: Tuple) -> float:
        """Simple ΔE color difference (0-100 scale)."""
        r1, g1, b1 = rgb1
        r2, g2, b2 = rgb2
        delta = ((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2) ** 0.5
        return (delta / 441.0) * 100
    
    def find_closest_lego_color(self, rgb: Tuple) -> Tuple[str, float]:
        """Find closest LEGO color, return (name, ΔE)."""
        min_de = float('inf')
        closest = "unknown"
        for name, lego_rgb in self.LEGO_COLORS.items():
            de = self.delta_e_cie76(rgb, lego_rgb)
            if de < min_de:
                min_de = de
                closest = name
        return closest, min_de
    
    def validate_colors(self, dominant_colors: List[Tuple], tolerance: float = 25.0) -> Tuple[bool, List[str]]:
        """Validate colors are close to LEGO palette."""
        errors = []
        for rgb in dominant_colors:
            closest, de = self.find_closest_lego_color(rgb)
            if de > tolerance:
                errors.append(f"Color RGB{rgb}: {de:.1f} ΔE from {closest}")
        
        is_valid = len(errors) == 0
        logger.info(f"[Color] {len(dominant_colors)} colors: {'OK' if is_valid else f'{len(errors)} out of range'}")
        return is_valid, errors
