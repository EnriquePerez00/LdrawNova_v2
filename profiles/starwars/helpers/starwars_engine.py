"""
Star Wars Ship Construction Engine for LdrawNova.
Handles chiral wing symmetry, Technic spine generation, optical depth layering, and 8-submodel MPD plans.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

LDU_PER_STUD = 20.0
LDU_PLATE_HEIGHT = 8.0
LDU_BRICK_HEIGHT = 24.0

# Canonical Orthogonal Rotation Matrices (det = +1.0)
ROT_IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_UP       = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_Y_180    = [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]
ROT_Y_90     = [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]
ROT_Y_270    = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]

# SNOT Orientations
SNOT_FRONT = [
    [1.0,  0.0,  0.0],
    [0.0,  0.0, -1.0],
    [0.0,  1.0,  0.0]
]
SNOT_LEFT = [
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0],
    [1.0,  0.0,  0.0]
]
SNOT_RIGHT = [
    [ 0.0, 1.0,  0.0],
    [ 0.0, 0.0, -1.0],
    [-1.0, 0.0,  0.0]
]

CHIRAL_MAP = {
    # Left -> Right
    "41770": "41769",
    "43720": "43719",
    "43723": "43722",
    "24307": "24299",
    "50305": "50304",
    "24600": "24599",
    "6565": "6564",
    "42061": "42060",
    # Right -> Left
    "41769": "41770",
    "43719": "43720",
    "43722": "43723",
    "24299": "24307",
    "50304": "50305",
    "24599": "24600",
    "6564": "6565",
    "42060": "42061",
}


def studs_to_ldu(studs: float) -> float:
    return studs * LDU_PER_STUD


class StarshipCoreBuilder:
    """Builder for official LdrawNova Star Wars starships conforming to plan.schema.json."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.sections_dict: Dict[str, List[Dict[str, Any]]] = {}
        self.anchors: Dict[str, Dict[str, Any]] = {}
        self._part_counter = 0

    def _next_id(self, prefix: str = "part") -> str:
        self._part_counter += 1
        return f"{prefix}_{self._part_counter:04d}"

    @staticmethod
    def get_chiral_counterpart(part_num: str) -> str:
        base = part_num.replace(".dat", "").lower()
        if base in CHIRAL_MAP:
            return f"{CHIRAL_MAP[base]}.dat"
        return part_num

    def add_submodel_part(self, submodel_file: str, part_id: str, color: int,
                          at: List[float], matrix: Optional[List[List[float]]] = None,
                          purpose: str = "") -> Dict[str, Any]:
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

    def export_plan(self) -> Dict[str, Any]:
        """Exports the complete plan compatible with ./ldraw-agent build."""
        sections: List[Dict[str, Any]] = []

        # 1. Master assembly section
        master_steps = [[
            {"id": f"inst_{name.replace('.ldr', '')}", "ref": name, "colour": 16, "at": [0, 0, 0]}
            for name in self.sections_dict.keys()
        ]]
        sections.append({
            "name": f"{self.name}.ldr",
            "description": f"{self.description} - Master Starship Assembly",
            "anchors": {"origin": {"at": [0, 0, 0]}},
            "steps": master_steps,
        })

        # 2. Submodel sections
        for submodel_name, parts in self.sections_dict.items():
            sections.append({
                "name": submodel_name,
                "description": f"{self.description} - Submodel {submodel_name}",
                "anchors": {"origin": {"at": [0, 0, 0]}},
                "steps": [parts],
            })

        return {
            "version": 1,
            "profile": "starwars",
            "author": "LdrawNova Star Wars Domain Engine",
            "sections": sections,
        }
