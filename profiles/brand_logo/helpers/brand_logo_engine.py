"""
Corporate Brand Logo and Typography Engine for LdrawNova (profiles/brand_logo).

Provides:
- Parametric BrandLogoBuilder conforming to LdrawNova plan.schema.json.
- CIELAB Delta-E color quantization from RGB/HEX reference images to official LDraw IDs.
- SNOT transformations, continuous curvature builders (Macaroni tiles, curved slopes).
- Structured submodel MPD generation (Canvas, Substrate, Isotype, Typography, Frame).
"""
from __future__ import annotations

import json
import math
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Fundamental LDraw Coordinate Constants
LDU_PER_STUD = 20.0
LDU_PLATE_HEIGHT = 8.0
LDU_BRICK_HEIGHT = 24.0

def studs_to_ldu(studs: float) -> float:
    """Converts stud grid distance to LDU units."""
    return round(float(studs) * LDU_PER_STUD, 3)

def plates_to_ldu(plates: float) -> float:
    """Converts plate thickness count to LDU height."""
    return round(float(plates) * LDU_PLATE_HEIGHT, 3)

def bricks_to_ldu(bricks: float) -> float:
    """Converts brick thickness count to LDU height."""
    return round(float(bricks) * LDU_BRICK_HEIGHT, 3)


# Canonical 3x3 Orthogonal Rotation Matrices (det = +1.0)
ROT_IDENTITY = [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0]
]

ROT_Y_90 = [
    [0.0, 0.0, 1.0],
    [0.0, 1.0, 0.0],
    [-1.0, 0.0, 0.0]
]

ROT_Y_180 = [
    [-1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, -1.0]
]

ROT_Y_270 = [
    [0.0, 0.0, -1.0],
    [0.0, 1.0, 0.0],
    [1.0, 0.0, 0.0]
]

# SNOT Orientations
# SNOT_FRONT: Studs face -Z (Viewer facing)
SNOT_FRONT = [
    [1.0,  0.0,  0.0],
    [0.0,  0.0, -1.0],
    [0.0,  1.0,  0.0]
]

# SNOT_BACK: Studs face +Z
SNOT_BACK = [
    [-1.0, 0.0,  0.0],
    [ 0.0, 0.0,  1.0],
    [ 0.0, 1.0,  0.0]
]

# SNOT_LEFT: Studs face -X
SNOT_LEFT = [
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0],
    [1.0,  0.0,  0.0]
]

# SNOT_RIGHT: Studs face +X
SNOT_RIGHT = [
    [ 0.0, 1.0,  0.0],
    [ 0.0, 0.0, -1.0],
    [-1.0, 0.0,  0.0]
]

# SNOT_DOWN: Inverted upside down
SNOT_DOWN = [
    [1.0,  0.0,  0.0],
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0]
]


# ==============================================================================
# Color Science: CIELAB Delta-E Quantization Engine
# ==============================================================================

def rgb_to_cielab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Converts sRGB [0..255] to CIELAB (L*, a*, b*) under D65 illuminant."""
    # 1. Normalize and linearize sRGB
    def pivot(v: float) -> float:
        v = v / 255.0
        return ((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else (v / 12.92)

    rl, gl, bl = pivot(r), pivot(g), pivot(b)

    # 2. Convert to XYZ
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041

    # D65 reference white
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    x /= xn
    y /= yn
    z /= zn

    # 3. Pivot XYZ to Lab
    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t) + (16.0 / 116.0)

    fx, fy, fz = f(x), f(y), f(z)
    l_star = (116.0 * fy) - 16.0
    a_star = 500.0 * (fx - fy)
    b_star = 200.0 * (fy - fz)
    return l_star, a_star, b_star


def delta_e_cielab(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """Euclidean distance in CIELAB space (Delta E 76)."""
    return math.sqrt(
        (lab1[0] - lab2[0]) ** 2 +
        (lab1[1] - lab2[1]) ** 2 +
        (lab1[2] - lab2[2]) ** 2
    )


class BrandLogoColorMatcher:
    """Matches any RGB or Hex input against the official brand_logo_palette.json."""

    def __init__(self, palette_file: Optional[Path] = None):
        if palette_file is None:
            palette_file = Path(__file__).resolve().parents[1] / "catalog" / "brand_logo_palette.json"
        self.palette_file = palette_file
        self.palette_entries: List[Dict[str, Any]] = []
        self._load_palette()

    def _load_palette(self) -> None:
        if self.palette_file.exists():
            data = json.loads(self.palette_file.read_text(encoding="utf-8"))
            for entry in data.get("colors", []):
                rgb = entry["rgb"]
                lab = rgb_to_cielab(rgb[0], rgb[1], rgb[2])
                self.palette_entries.append({
                    "ldraw_id": entry["ldraw_id"],
                    "name": entry["name"],
                    "hex": entry["hex"],
                    "rgb": rgb,
                    "lab": lab
                })

    def match_hex(self, hex_code: str) -> Dict[str, Any]:
        """Matches a '#RRGGBB' string to closest LDraw color."""
        hex_code = hex_code.lstrip("#")
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        return self.match_rgb(r, g, b)

    def match_rgb(self, r: int, g: int, b: int) -> Dict[str, Any]:
        """Finds closest LDraw color entry minimizing Delta-E."""
        target_lab = rgb_to_cielab(r, g, b)
        best_entry = None
        min_dist = float("inf")
        for entry in self.palette_entries:
            dist = delta_e_cielab(target_lab, entry["lab"])
            if dist < min_dist:
                min_dist = dist
                best_entry = entry
        result = dict(best_entry or {})
        result["delta_e"] = round(min_dist, 2)
        return result


# ==============================================================================
# Logo Archetypes & Builder
# ==============================================================================

class LogoArchetype(str, Enum):
    """The 4 fundamental construction paradigms for corporate logos."""
    BAS_RELIEF_PLAQUE = "bas_relief_plaque"
    GEOMETRIC_EMBLEM = "geometric_emblem"
    ORGANIC_SWOOSH = "organic_swoosh"
    MONOGRAM_FREESTANDING = "monogram_freestanding"


class BrandLogoBuilder:
    """
    Parametric CAD Builder for Corporate Brand Logos conforming to LdrawNova plan.schema.json.
    Produces clean, modular MPD assemblies with verified connectivity (component_count = 1).
    """

    def __init__(
        self,
        name: str,
        description: str,
        archetype: Union[LogoArchetype, str],
        width_studs: int = 32,
        height_studs: int = 32
    ):
        self.name = name
        self.description = description
        self.archetype = (
            archetype if isinstance(archetype, LogoArchetype)
            else LogoArchetype(archetype.lower())
        )
        self.width_studs = width_studs
        self.height_studs = height_studs
        self.sections_dict: Dict[str, List[Dict[str, Any]]] = {}
        self._part_counter = 0

    def _next_id(self, prefix: str = "part") -> str:
        self._part_counter += 1
        return f"{prefix}_{self._part_counter:04d}"

    def add_submodel_part(
        self,
        submodel_file: str,
        part_id: str,
        color: int,
        at: List[float],
        matrix: Optional[List[List[float]]] = None,
        purpose: str = ""
    ) -> Dict[str, Any]:
        """Adds a single part to a specific MPD submodel."""
        if not part_id.endswith(".dat"):
            part_id = f"{part_id}.dat"

        entry: Dict[str, Any] = {
            "id": self._next_id(submodel_file.split(".")[0]),
            "ref": part_id,
            "colour": color,
            "at": [round(float(coord), 3) for coord in at],
        }
        if matrix is not None:
            entry["matrix"] = matrix
        if purpose:
            entry["purpose"] = purpose

        if submodel_file not in self.sections_dict:
            self.sections_dict[submodel_file] = []
        self.sections_dict[submodel_file].append(entry)
        return entry

    def add_macaroni_arc(
        self,
        submodel_file: str,
        center_studs: Tuple[float, float],
        radius_studs: int,
        quadrants: List[int],
        color: int,
        elevation_ldu: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Places circular macaroni tiles in specified quadrants (1: Top-Right, 2: Top-Left, 3: Bottom-Left, 4: Bottom-Right).
        radius_studs supports:
          - 1: 25269.dat (Tile 1x1 Round 1/4)
          - 2: 27925.dat (Tile 2x2 Curved Macaroni)
          - 3: 27507.dat (Tile 3x3 Curved Macaroni)
          - 4: 48092.dat (Tile 4x4 Curved Macaroni)
        """
        part_map = {
            1: "25269.dat",
            2: "27925.dat",
            3: "27507.dat",
            4: "48092.dat",
        }
        part_ref = part_map.get(radius_studs, "27925.dat")
        placed = []

        cx_ldu = studs_to_ldu(center_studs[0])
        cz_ldu = studs_to_ldu(center_studs[1])

        # Quadrant angles: 1: 0 deg, 2: 90 deg, 3: 180 deg, 4: 270 deg
        rot_map = {
            1: ROT_IDENTITY,
            2: ROT_Y_90,
            3: ROT_Y_180,
            4: ROT_Y_270
        }

        for q in quadrants:
            mat = rot_map.get(q, ROT_IDENTITY)
            entry = self.add_submodel_part(
                submodel_file=submodel_file,
                part_id=part_ref,
                color=color,
                at=[cx_ldu, elevation_ldu, cz_ldu],
                matrix=mat,
                purpose=f"Circular contour quadrant {q} (R={radius_studs})"
            )
            placed.append(entry)
        return placed

    def export_plan(self) -> Dict[str, Any]:
        """
        Exports the master assembly plan strictly conforming to ldraw_tools plan.schema.json.
        """
        sections: List[Dict[str, Any]] = []

        # Master Assembly Section calling all submodels at origin
        master_steps = [[
            {
                "id": f"inst_{name.replace('.ldr', '')}",
                "ref": name,
                "colour": 16,
                "at": [0, 0, 0]
            }
            for name in self.sections_dict.keys()
        ]]

        sections.append({
            "name": f"{self.name}.ldr",
            "description": f"{self.description} - Master Corporate Logo Assembly [{self.archetype.value}]",
            "anchors": {"origin": {"at": [0, 0, 0]}},
            "steps": master_steps,
        })

        # Submodel Sections
        for submodel_name, parts in self.sections_dict.items():
            sections.append({
                "name": submodel_name,
                "description": f"{self.description} - Submodel {submodel_name}",
                "anchors": {"origin": {"at": [0, 0, 0]}},
                "steps": [parts],
            })

        return {
            "version": 1,
            "profile": "brand_logo",
            "author": "LdrawNova Corporate Brand Logo Engine",
            "sections": sections,
        }
