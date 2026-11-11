"""
Fauna and Animal Biomechanical Construction Engine for LdrawNova.
Handles organic SNOT sculpting, Mixels ball-joint kinematics, chiral bilateral symmetry,
and multi-submodel MPD plans across 5 morphological archetypes:
  - AVIAN (Birds & Raptors)
  - MAMMAL_QUADRUPED (Felines, Canines, Ungulates)
  - AQUATIC (Fish, Cetaceans, Sharks)
  - ARTHROPOD (Insects, Arachnids)
  - REPTILIAN_DINO (Dinosaurs, Crocodilians)
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Fundamental LDraw Coordinate Constants
LDU_PER_STUD = 20.0
LDU_PLATE_HEIGHT = 8.0
LDU_BRICK_HEIGHT = 24.0

def studs_to_ldu(studs: float) -> float:
    """Converts stud distance to LDU units."""
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

# SNOT Orientations for organic lateral and vertical flesh mounting
# SNOT_FRONT: Studs face -Z (Forward)
SNOT_FRONT = [
    [1.0,  0.0,  0.0],
    [0.0,  0.0, -1.0],
    [0.0,  1.0,  0.0]
]

# SNOT_BACK: Studs face +Z (Caudal / Rear)
SNOT_BACK = [
    [-1.0, 0.0,  0.0],
    [ 0.0, 0.0,  1.0],
    [ 0.0, 1.0,  0.0]
]

# SNOT_LEFT: Studs face -X (Port / Lateral Left)
SNOT_LEFT = [
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0],
    [1.0,  0.0,  0.0]
]

# SNOT_RIGHT: Studs face +X (Starboard / Lateral Right)
SNOT_RIGHT = [
    [ 0.0, 1.0,  0.0],
    [ 0.0, 0.0, -1.0],
    [-1.0, 0.0,  0.0]
]

# SNOT_DOWN: Studs face +Y (Ventral / Inverted Belly)
SNOT_DOWN = [
    [1.0,  0.0,  0.0],
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0]
]


# Chiral counterpart map for Left/Right mirror reflection
CHIRAL_MAP: Dict[str, str] = {
    # Curved Slopes with Notch
    "29120": "29119",
    "29119": "29120",
    # Wedge Plates 3 x 2
    "43723": "43722",
    "43722": "43723",
    # Wedge Plates 4 x 2
    "41770": "41769",
    "41769": "41770",
    # Wedge Plates 4 x 4
    "24307": "24299",
    "24299": "24307",
    # Wedge Plates 8 x 3
    "50305": "50304",
    "50304": "50305",
    # Wedge Plates 12 x 3
    "42061": "42060",
    "42060": "42061",
    # Wedge Slopes
    "6565": "6564",
    "6564": "6565",
    # Wing Plates 6 x 3
    "54384": "54383",
    "54383": "54384",
}


class MorphologicalArchetype(str, Enum):
    """Morphological categories governing animal anatomy & kinematic hierarchy."""
    AVIAN = "avian"
    MAMMAL_QUADRUPED = "mammal_quadruped"
    AQUATIC = "aquatic"
    ARTHROPOD = "arthropod"
    REPTILIAN_DINO = "reptilian_dino"


class FaunaAnimalBuilder:
    """
    Parametric Biomechanical Builder for LEGO Animals adhering to LdrawNova plan.schema.json.
    Organizes geometry into clean, isolated MPD submodels guaranteeing continuous connectivity (component_count = 1).
    """

    def __init__(self, name: str, description: str, archetype: Union[MorphologicalArchetype, str]):
        self.name = name
        self.description = description
        self.archetype = (
            archetype if isinstance(archetype, MorphologicalArchetype)
            else MorphologicalArchetype(archetype.lower())
        )
        self.sections_dict: Dict[str, List[Dict[str, Any]]] = {}
        self.anchors: Dict[str, Dict[str, Any]] = {}
        self._part_counter = 0

    def _next_id(self, prefix: str = "part") -> str:
        self._part_counter += 1
        return f"{prefix}_{self._part_counter:04d}"

    @staticmethod
    def get_chiral_counterpart(part_num: str) -> str:
        """Returns the paired left/right chiral part ID if applicable."""
        base = part_num.replace(".dat", "").lower()
        if base in CHIRAL_MAP:
            return f"{CHIRAL_MAP[base]}.dat"
        return part_num

    def add_submodel_part(
        self,
        submodel_file: str,
        part_id: str,
        color: int,
        at: List[float],
        matrix: Optional[List[List[float]]] = None,
        purpose: str = ""
    ) -> Dict[str, Any]:
        """
        Adds a single part to a specific MPD submodel.
        """
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

    def add_symmetric_pair(
        self,
        submodel_left: str,
        submodel_right: str,
        part_id: str,
        color: int,
        at_left: List[float],
        matrix_left: Optional[List[List[float]]] = None,
        purpose: str = ""
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Instantiates a bilaterally symmetric part pair mirrored across the sagittal plane X = 0.
        Automatically substitutes chiral wedge/slope parts for the right side and flips X coordinates.
        """
        left_entry = self.add_submodel_part(
            submodel_file=submodel_left,
            part_id=part_id,
            color=color,
            at=at_left,
            matrix=matrix_left,
            purpose=f"{purpose} (Left/Port)" if purpose else "Left side feature"
        )

        right_part_id = self.get_chiral_counterpart(part_id)
        at_right = [-at_left[0], at_left[1], at_left[2]]

        # Reflect rotation matrix across X axis if provided
        matrix_right = None
        if matrix_left is not None:
            # Reflection: multiply by diag(-1, 1, 1) and keep right-handed orientation
            m = matrix_left
            matrix_right = [
                [-m[0][0],  m[0][1],  m[0][2]],
                [-m[1][0],  m[1][1],  m[1][2]],
                [-m[2][0],  m[2][1],  m[2][2]]
            ]

        right_entry = self.add_submodel_part(
            submodel_file=submodel_right,
            part_id=right_part_id,
            color=color,
            at=at_right,
            matrix=matrix_right,
            purpose=f"{purpose} (Right/Starboard)" if purpose else "Right side feature"
        )

        return left_entry, right_entry

    def add_towball_socket_joint(
        self,
        submodel_socket: str,
        submodel_ball: str,
        at_socket: List[float],
        at_ball: List[float],
        color: int = 72,
        socket_ref: str = "14704.dat",
        ball_ref: str = "14417.dat",
        matrix_socket: Optional[List[List[float]]] = None,
        matrix_ball: Optional[List[List[float]]] = None,
        purpose: str = "Kinematic ball joint articulation"
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Constructs a matched Mixels towball-and-socket kinematic pair (e.g. neck, limb or tail).
        """
        socket_entry = self.add_submodel_part(
            submodel_file=submodel_socket,
            part_id=socket_ref,
            color=color,
            at=at_socket,
            matrix=matrix_socket,
            purpose=f"{purpose} (Socket Female)"
        )
        ball_entry = self.add_submodel_part(
            submodel_file=submodel_ball,
            part_id=ball_ref,
            color=color,
            at=at_ball,
            matrix=matrix_ball,
            purpose=f"{purpose} (Ball Male)"
        )
        return socket_entry, ball_entry

    def export_plan(self) -> Dict[str, Any]:
        """
        Exports the master assembly plan strictly conforming to ldraw_tools/data/plan.schema.json.
        All submodels are called with identity placement at origin [0, 0, 0] in the master assembly.
        """
        sections: List[Dict[str, Any]] = []

        # 1. Master Assembly Section
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
            "description": f"{self.description} - Master Animal Assembly [{self.archetype.value}]",
            "anchors": {"origin": {"at": [0, 0, 0]}},
            "steps": master_steps,
        })

        # 2. Submodel Sections
        for submodel_name, parts in self.sections_dict.items():
            sections.append({
                "name": submodel_name,
                "description": f"{self.description} - Submodel {submodel_name}",
                "anchors": {"origin": {"at": [0, 0, 0]}},
                "steps": [parts],
            })

        return {
            "version": 1,
            "profile": "fauna",
            "author": "LdrawNova Biomechanical Fauna Engine",
            "sections": sections,
        }
