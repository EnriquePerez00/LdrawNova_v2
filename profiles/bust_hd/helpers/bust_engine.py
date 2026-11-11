"""
LdrawNova High Definition Human Bust Geometric Engine (profiles/bust_hd).

Core-and-Cladding Architecture for Sculpted Human Busts (Shoulders up).
Fully compliant with LDraw specifications, Three-Tier Assembly, and ldraw-nova pipeline.

Coordinate Convention & Anthropometric Rules:
- 1 stud = 20 LDU (X and Z spacing)
- 1 brick height = 24 LDU
- 1 plate height = 8 LDU
- Vertical axis Y: In LDraw coordinates, -Y is UP (cranium/sky), +Y is DOWN (gravity/pedestal).
  In authoring height parameter 'h', h >= 0 measures elevation upwards (LDraw Y = -h).
- Sagittal plane / Bilateral symmetry: X = 0 is the midline plane.
  +X is subject's anatomical left (model's right from front view).
  -X is subject's anatomical right (model's left from front view).
- Facial Front axis Z: In ldraw-nova convention, -Z is FACIAL FRONT (facing forward),
  and +Z is REAR (occipital/nape).
"""
from __future__ import annotations

import copy
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# -----------------------------------------------------------------------------
# LDU & ANTHROPOMETRIC CONSTANTS
# -----------------------------------------------------------------------------
LDU_PER_STUD: float = 20.0
LDU_PLATE_HEIGHT: float = 8.0
LDU_BRICK_HEIGHT: float = 24.0
PLATES_PER_BRICK: int = 3

HEAD_WIDTH_STUDS_DEFAULT: int = 18
HEAD_HEIGHT_BRICKS_DEFAULT: int = 16
HEAD_DEPTH_STUDS_DEFAULT: int = 20

# -----------------------------------------------------------------------------
# CANONICAL ROTATION MATRICES (Right-Handed, det = +1.0)
# -----------------------------------------------------------------------------
# Upright / Default (Studs facing -Y, front facing -Z)
ROT_UP: List[List[float]] = [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0]
]

# Inverted / Upside down (Studs facing +Y)
ROT_DOWN: List[List[float]] = [
    [1.0,  0.0,  0.0],
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0]
]

# Front facing (Pitch +90 deg: Studs facing -Z, bottom facing +Z)
ROT_FRONT: List[List[float]] = [
    [1.0,  0.0,  0.0],
    [0.0,  0.0, -1.0],
    [0.0,  1.0,  0.0]
]

# Rear facing (Pitch -90 deg: Studs facing +Z)
ROT_BACK: List[List[float]] = [
    [1.0,  0.0, 0.0],
    [0.0,  0.0, -1.0],
    [0.0,  1.0, 0.0]
]

# Left lateral facing (Yaw +90 deg: Studs facing +X)
ROT_LEFT: List[List[float]] = [
    [0.0, 0.0, -1.0],
    [0.0, 1.0,  0.0],
    [1.0, 0.0,  0.0]
]

# Right lateral facing (Yaw -90 deg: Studs facing -X)
ROT_RIGHT: List[List[float]] = [
    [ 0.0, 0.0, 1.0],
    [ 0.0, 1.0, 0.0],
    [-1.0, 0.0, 0.0]
]

# SNOT Front Orientation for vertical surface skinning (studs -Z, top +Y)
ROT_SNOT_FRONT: List[List[float]] = [
    [-1.0, 0.0, 0.0],
    [ 0.0, 0.0, 1.0],
    [ 0.0, 1.0, 0.0]
]

# SNOT Back Orientation (studs +Z, top +Y)
ROT_SNOT_BACK: List[List[float]] = [
    [1.0,  0.0,  0.0],
    [0.0,  0.0, -1.0],
    [0.0,  1.0,  0.0]
]

# -----------------------------------------------------------------------------
# CHIRAL PART MIRROR SWAP TABLE
# -----------------------------------------------------------------------------
DEFAULT_CHIRAL_SWAPS: Dict[str, str] = {
    # Wedge Plates 3 x 2
    "43722": "43723",
    "43723": "43722",
    "43722.dat": "43723.dat",
    "43723.dat": "43722.dat",
    # Wedge Plates 4 x 2
    "43710": "43711",
    "43711": "43710",
    "43710.dat": "43711.dat",
    "43711.dat": "43710.dat",
    # Wedge Plates 4 x 2 Inverted
    "41769": "41770",
    "41770": "41769",
    "41769.dat": "41770.dat",
    "41770.dat": "41769.dat",
    # Wedge Plates 2 x 2
    "24299": "24307",
    "24307": "24299",
    "24299.dat": "24307.dat",
    "24307.dat": "24299.dat",
    # Wedge Plates 4 x 4
    "65429": "65426",
    "65426": "65429",
    "65429.dat": "65426.dat",
    "65426.dat": "65429.dat",
    # Curved Slopes with Notch
    "29120": "29119",
    "29119": "29120",
    "29120.dat": "29119.dat",
    "29119.dat": "29120.dat",
    # Brackets 1 x 1 Up / Down
    "36840": "36841",
    "36841": "36840",
    "36840.dat": "36841.dat",
    "36841.dat": "36840.dat",
}


# -----------------------------------------------------------------------------
# GEOMETRIC CONVERSIONS
# -----------------------------------------------------------------------------
def studs_to_ldu(studs: float) -> float:
    """Convert studs into exact LDraw Units (20 LDU per stud)."""
    return studs * LDU_PER_STUD


def ldu_to_studs(ldu: float) -> float:
    """Convert LDraw Units into studs."""
    return ldu / LDU_PER_STUD


def plates_to_ldu(plates: int) -> float:
    """Convert plate layers into LDU height (8 LDU per plate)."""
    return plates * LDU_PLATE_HEIGHT


def bricks_to_ldu(bricks: int) -> float:
    """Convert brick courses into LDU height (24 LDU per brick)."""
    return bricks * LDU_BRICK_HEIGHT


def h_to_ldu_y(h: float) -> float:
    """Convert upward elevation h into LDraw Y coordinate (Y = -h)."""
    return -h


def ldu_y_to_h(y: float) -> float:
    """Convert LDraw Y coordinate into upward elevation h."""
    return -y


# -----------------------------------------------------------------------------
# VOXEL & SURFACE HELPERS
# -----------------------------------------------------------------------------
def generate_elliptical_layer(
    y_ldu: float,
    rx_studs: float,
    rz_studs: float,
    hollow: bool = True,
    wall_thickness_studs: float = 1.0,
    colour: int = 78,
    use_plates: bool = True,
    center_x: float = 0.0,
    center_z: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Rellena una sección transversal elíptica optimizando placas grandes en el interior
    y dejando resolución de 1x1 o 1x2 en el perímetro sin generar solapamientos.

    Args:
        y_ldu: Coordenada Y en LDU (ej. -h para elevación h).
        rx_studs: Semieje horizontal X en studs.
        rz_studs: Semieje antero-posterior Z en studs.
        hollow: Si True, ahueca el interior dejando una pared de grosor wall_thickness_studs.
        wall_thickness_studs: Grosor de pared en studs si hollow es True.
        colour: Código oficial de color LDraw.
        use_plates: Si True usa plates (8 LDU); si False usa bricks (24 LDU).
        center_x: Centro X en studs (por defecto 0, plano sagital).
        center_z: Centro Z en studs.

    Returns:
        Lista de diccionarios de piezas LDraw con claves:
        id, ref, colour, at: [X, Y, Z], yaw (o matrix), purpose.
    """
    if rx_studs <= 0 or rz_studs <= 0:
        return []

    # Determinar el rango de celdas unitarias enteras (cada celda es 1x1 stud)
    min_i = int(math.floor(center_x - rx_studs))
    max_i = int(math.ceil(center_x + rx_studs))
    min_k = int(math.floor(center_z - rz_studs))
    max_k = int(math.ceil(center_z + rz_studs))

    inner_rx = max(0.1, rx_studs - wall_thickness_studs)
    inner_rz = max(0.1, rz_studs - wall_thickness_studs)

    occupied_cells: Set[Tuple[int, int]] = set()

    for i in range(min_i, max_i):
        for k in range(min_k, max_k):
            # Centro de la celda [i, i+1] x [k, k+1]
            cx = i + 0.5 - center_x
            cz = k + 0.5 - center_z

            outer_val = (cx / rx_studs) ** 2 + (cz / rz_studs) ** 2
            if outer_val <= 1.0:
                if hollow:
                    inner_val = (cx / inner_rx) ** 2 + (cz / inner_rz) ** 2
                    if inner_val < 1.0:
                        continue
                occupied_cells.add((i, k))

    if not occupied_cells:
        return []

    # Teselado voraz en placas estándar LEGO para evitar colisiones
    # Formatos preferidos (ancho X, profundidad Z, ref plate, ref brick)
    standard_tiles = [
        (4, 2, "3020.dat", "3001.dat"),
        (2, 4, "3020.dat", "3001.dat"),
        (3, 2, "3021.dat", "3002.dat"),
        (2, 3, "3021.dat", "3002.dat"),
        (2, 2, "3022.dat", "3003.dat"),
        (4, 1, "3710.dat", "3010.dat"),
        (1, 4, "3710.dat", "3010.dat"),
        (3, 1, "3623.dat", "3622.dat"),
        (1, 3, "3623.dat", "3622.dat"),
        (2, 1, "3023.dat", "3004.dat"),
        (1, 2, "3023.dat", "3004.dat"),
        (1, 1, "3024.dat", "3005.dat"),
    ]

    parts: List[Dict[str, Any]] = []
    unplaced = set(occupied_cells)
    serial = 0

    # Ordenar celdas de NW a SE para empaquetado determinista
    sorted_unplaced = sorted(list(unplaced), key=lambda c: (c[1], c[0]))

    for cell in sorted_unplaced:
        if cell not in unplaced:
            continue
        ci, ck = cell

        # Probar el rectángulo más grande disponible
        best_w, best_d, best_ref, best_yaw = 1, 1, ("3024.dat" if use_plates else "3005.dat"), 0

        for w, d, plate_ref, brick_ref in standard_tiles:
            fits = True
            for di in range(w):
                for dk in range(d):
                    if (ci + di, ck + dk) not in unplaced:
                        fits = False
                        break
                if not fits:
                    break

            if fits:
                best_w = w
                best_d = d
                # Si w < d, la pieza se orienta girada 90 grados
                if w < d:
                    best_ref = plate_ref if use_plates else brick_ref
                    best_yaw = 90
                else:
                    best_ref = plate_ref if use_plates else brick_ref
                    best_yaw = 0
                break

        # Marcar celdas como cubiertas
        for di in range(best_w):
            for dk in range(best_d):
                unplaced.remove((ci + di, ck + dk))

        # Calcular coordenadas del centro de la pieza
        part_center_x = ci + best_w / 2.0
        part_center_z = ck + best_d / 2.0

        serial += 1
        part_entry: Dict[str, Any] = {
            "id": f"el_p{serial:04d}",
            "ref": best_ref,
            "colour": colour,
            "at": [
                round(part_center_x * LDU_PER_STUD, 2),
                round(y_ldu, 2),
                round(part_center_z * LDU_PER_STUD, 2),
            ],
            "purpose": f"Elliptical layer {best_w}x{best_d} contour fill",
        }
        if best_yaw != 0:
            part_entry["yaw"] = best_yaw

        parts.append(part_entry)

    return parts


def mirror_feature_x(
    parts_list: List[Dict[str, Any]],
    part_swap_dict: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Refleja automáticamente cualquier submodelo lateral (ojo izquierdo -> derecho,
    oreja izquierda -> derecha, pómulo izquierdo -> derecho) invirtiendo X -> -X,
    transformando la matriz de orientación 3x3 LDraw o ángulo yaw, y cambiando
    piezas asimétricas (wedges/curved slopes izq/der) según part_swap_dict.

    Args:
        parts_list: Lista de diccionarios de piezas o subensambles.
        part_swap_dict: Diccionario de intercambio de referencias quirales.

    Returns:
        Nueva lista de piezas reflejadas en X=0 con matrices válidas (det = +1.0).
    """
    swaps = dict(DEFAULT_CHIRAL_SWAPS)
    if part_swap_dict:
        swaps.update(part_swap_dict)

    mirrored_parts: List[Dict[str, Any]] = []

    for item in parts_list:
        p = copy.deepcopy(item)

        # 1. Invertir posición en X
        if "at" in p and len(p["at"]) >= 3:
            p["at"][0] = -p["at"][0]

        # 2. Reflejar rotación / matriz
        if "matrix" in p and p["matrix"] is not None:
            # Transformación M_ref * R * M_ref para reflexión conservando orientación SO(3)
            # R_mirrored = [[a, -b, -c], [-d, e, f], [-g, h, i]]
            m = p["matrix"]
            if len(m) == 3 and len(m[0]) == 3:
                p["matrix"] = [
                    [ m[0][0], -m[0][1], -m[0][2]],
                    [-m[1][0],  m[1][1],  m[1][2]],
                    [-m[2][0],  m[2][1],  m[2][2]]
                ]
            elif len(m) == 9:
                p["matrix"] = [
                     m[0], -m[1], -m[2],
                    -m[3],  m[4],  m[5],
                    -m[6],  m[7],  m[8]
                ]
        elif "yaw" in p:
            # En rotación pura yaw alrededor del eje Y: new_yaw = (-yaw) % 360
            p["yaw"] = (-p["yaw"]) % 360
        else:
            # Si no tenía rotación explícita, una pieza simétrica en yaw=0
            # puede requerir invertir X si es un bloque simétrico simple
            pass

        # 3. Intercambiar piezas quirales (wedges, slopes asimétricos)
        ref = p.get("ref", "")
        clean_ref = ref.replace(".dat", "")
        if ref in swaps:
            p["ref"] = swaps[ref]
        elif clean_ref in swaps:
            p["ref"] = swaps[clean_ref] + (".dat" if ref.endswith(".dat") else "")

        # 4. Actualizar ID si existe
        if "id" in p:
            p["id"] = f"{p['id']}_m"

        mirrored_parts.append(p)

    return mirrored_parts


def apply_beard_or_hair_texture(
    surface_points: List[Dict[str, Any]],
    palette_colors: List[int],
    roughness: float = 0.5,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Función determinista que distribuye plates 1x1, cheese slopes (54200.dat)
    y tiles redondos (98138.dat) alternando colores (ej. Dark Bluish Gray, Black,
    Reddish Brown, Light Bluish Gray) para simular textura orgánica de barba canosa
    o cabello rizado sin crear colisiones.

    Args:
        surface_points: Puntos ancla de la superficie con claves 'at' [X, Y, Z] y 'normal'.
        palette_colors: Lista de colores LDraw para salt-and-pepper / vello.
        roughness: Coeficiente de densidad / aspereza (0.0 a 1.0).
        seed: Semilla pseudoaleatoria determinista.

    Returns:
        Lista de piezas de micro-textura colocadas legalmente sin solapamientos.
    """
    if not surface_points or not palette_colors:
        return []

    rng = random.Random(seed)
    textured_parts: List[Dict[str, Any]] = []

    # Piezas de acabado de superficie orgánico
    # 54200: Cheese slope 1x1, 98138: Round tile 1x1, 3024: Plate 1x1, 24246: Half circle tile
    candidate_refs = [
        ("54200.dat", "Cheese slope 1x1 micro-follicle"),
        ("98138.dat", "Round tile 1x1 organic curly follicle"),
        ("3024.dat",  "Plate 1x1 follicle root"),
        ("25269.dat", "Quarter circle tile 1x1 wavy contour"),
    ]

    serial = 0
    for pt in surface_points:
        if rng.random() > roughness:
            continue

        at_pos = pt.get("at", [0.0, 0.0, 0.0])
        normal = pt.get("normal", [0.0, 0.0, -1.0])

        chosen_color = palette_colors[rng.randint(0, len(palette_colors) - 1)]
        ref_choice, purpose = candidate_refs[rng.randint(0, len(candidate_refs) - 1)]

        serial += 1
        entry: Dict[str, Any] = {
            "id": f"txt_p{serial:04d}",
            "ref": ref_choice,
            "colour": chosen_color,
            "at": [round(at_pos[0], 2), round(at_pos[1], 2), round(at_pos[2], 2)],
            "purpose": purpose,
        }

        # Orientar la pieza según el vector normal
        nx, ny, nz = normal
        if abs(nz) > 0.7:
            # Superficie frontal o trasera
            entry["matrix"] = ROT_FRONT if nz < 0 else ROT_BACK
        elif abs(nx) > 0.7:
            # Superficie lateral
            entry["matrix"] = ROT_LEFT if nx > 0 else ROT_RIGHT
        elif abs(ny) > 0.7:
            # Superficie superior o inferior
            if ny < 0:
                # Superficie superior (normal apuntando hacia arriba -Y)
                entry["yaw"] = 0
            else:
                entry["matrix"] = ROT_DOWN

        textured_parts.append(entry)

    return textured_parts


# -----------------------------------------------------------------------------
# ANATOMICAL CORE BUILDER
# -----------------------------------------------------------------------------
class AnatomicalCoreBuilder:
    """
    Constructor anatómico del núcleo craneal, cuello, hombros y pedestal.
    Garantiza continuidad estructural estricta (component_count = 1),
    ausencia de colisiones de cuerpos rectangulares y exposición de puntos
    de anclaje SNOT estandarizados para rasgos faciales.
    """

    def __init__(self, name: str = "canonical_bust", description: str = "HD Human Sculpted Bust"):
        self.name = name
        self.description = description
        self.pedestal_parts: List[Dict[str, Any]] = []
        self.shoulder_parts: List[Dict[str, Any]] = []
        self.neck_parts: List[Dict[str, Any]] = []
        self.cranium_parts: List[Dict[str, Any]] = []
        self.anchors: Dict[str, Dict[str, Any]] = {}
        self.serial = 0

    def _next_id(self, prefix: str = "core") -> str:
        self.serial += 1
        return f"{prefix}_{self.serial:04d}"

    def build_pedestal_and_shoulders(
        self,
        width_studs: int = 28,
        depth_studs: int = 16,
        collar_type: str = "crew_neck",
        color_clothing: int = 0,
        color_skin: int = 78,
        color_pedestal: int = 0,
    ) -> None:
        """
        Genera una base sólida de hombros con caída curva mediante slopes y cuello
        cilíndrico/elíptico sobre un pedestal arquitectónico de exposición.
        """
        # =====================================================================
        # 1. PEDESTAL ARQUITECTÓNICO DE MUSEO (h = 0 a h = 72 LDU)
        # =====================================================================
        # Nivel 1 (h = 0, espesor 8 LDU): Placa base ancha 10x10 studs
        # Cubre X: [-5, +5], Z: [-5, +5]. Bounds LDU: [-100, +100]
        # Realizado con 2 plates 6x10 y 4x10 o subdividido limpiamente
        # Usamos plates 2x4 y 2x2 para trabazón perfecta:
        # Fila Z de -5 a +5 (span 10), Fila X de -5 a +5 (span 10)
        # Para evitar fracciones, colocamos simétrico sobre el centro X=0, Z=0:
        # Base 10x10 studs:
        # 2x plates 4x10 -> Z [-5, -1] y Z [-1, +3] y 2x10 Z [+3, +5]
        # O utilizando Module slab estándar con boundary offsets enteros:
        self._add_plate_rect(-5, -5, 10, 10, h=0, colour=color_pedestal, purpose="Pedestal plinth base 10x10")

        # Nivel 2 (h = 8, espesor 8 LDU): Escalón 8x8 studs
        # Cubre X: [-4, +4], Z: [-4, +4]
        self._add_plate_rect(-4, -4, 8, 8, h=8, colour=color_pedestal, purpose="Pedestal plinth step 8x8")

        # Nivel 3 (h = 16, espesor 24 LDU): Columna central 6x6 bricks
        # Cubre X: [-3, +3], Z: [-3, +3]
        self._add_brick_rect(-3, -3, 6, 6, h=16, colour=color_pedestal, purpose="Pedestal central column tier 1")

        # Nivel 4 (h = 40, espesor 24 LDU): Columna central 6x6 cruzada (cross-bonded)
        self._add_brick_rect(-3, -3, 6, 6, h=40, colour=color_pedestal, purpose="Pedestal central column tier 2 cross-bonded", cross_orient=True)

        # Nivel 5 (h = 64, espesor 8 LDU): Cornisa de soporte 8x8 plates
        self._add_plate_rect(-4, -4, 8, 8, h=64, colour=color_pedestal, purpose="Pedestal capital cornice plate 8x8")

        # =====================================================================
        # 2. TORSO Y HOMBROS ESCULPIDOS (h = 72 a h = 144 LDU)
        # =====================================================================
        # Nivel 6 (h = 72, espesor 24 LDU): Base del pecho
        # Span X: 16 studs [-8, +8], Z: 8 studs [-4, +4]
        self._add_brick_rect(-8, -4, 16, 8, h=72, colour=color_clothing, purpose="Lower torso core 16x8")

        # Nivel 7 (h = 96, espesor 24 LDU): Expansión a 22 studs de hombro
        # Span X: 22 studs [-11, +11], Z: 10 studs [-5, +5]
        self._add_brick_rect(-11, -5, 22, 10, h=96, colour=color_clothing, purpose="Mid chest and back span 22x10", cross_orient=True)

        # Nivel 8 (h = 120, espesor 24 LDU): Amplitud máxima de hombros (width_studs, ej. 28)
        # Span X: [-w/2, +w/2], Z: [-d/2, +d/2]
        hw = width_studs // 2
        hd = depth_studs // 2
        self._add_brick_rect(-hw, -hd, width_studs, depth_studs, h=120, colour=color_clothing, purpose="Full clavicular shoulder span")

        # Caída curva de los hombros mediante Curved Slopes (50950.dat 1x3 y 11477.dat 1x2)
        # Colocadas en h = 144 en los extremos laterales del deltoides (altura 24 LDU, Y = -168)
        # Extremo izquierdo (+X): x de hw-3 a hw
        self.shoulder_parts.append({
            "id": self._next_id("sh_curve_l"),
            "ref": "50950.dat",
            "colour": color_clothing,
            "at": [round((hw - 1.5) * LDU_PER_STUD, 2), -(144 + LDU_BRICK_HEIGHT), round(0.0, 2)],
            "yaw": 90,
            "purpose": "Left shoulder deltoid curved falloff",
        })
        # Extremo derecho (-X): x de -hw a -hw+3
        self.shoulder_parts.append({
            "id": self._next_id("sh_curve_r"),
            "ref": "50950.dat",
            "colour": color_clothing,
            "at": [round((-hw + 1.5) * LDU_PER_STUD, 2), -(144 + LDU_BRICK_HEIGHT), round(0.0, 2)],
            "yaw": -90,
            "purpose": "Right shoulder deltoid curved falloff",
        })

        # =====================================================================
        # 3. ESCOTE Y CUELLO (h = 144 a h = 192 LDU)
        # =====================================================================
        # Nivel 9 (h = 144, espesor 24 LDU): Clavícula, cuello de prenda y base cervical
        # Núcleo del cuello central en tono de piel: 6 studs de ancho [-3, +3], 6 de prof [-3, +3]
        self._add_brick_rect(-3, -3, 6, 6, h=144, colour=color_skin, purpose="Cervical spine base core 6x6")

        # Ribete del cuello de la prenda (collar_type)
        if collar_type == "crew_neck":
            # Framing con losetas lisas en color_clothing alrededor del cuello (altura 8 LDU, Y = -152)
            # Frontal Z = -4
            self.shoulder_parts.append({
                "id": self._next_id("collar_front"),
                "ref": "2431.dat",
                "colour": color_clothing,
                "at": [0.0, -(144 + LDU_PLATE_HEIGHT), round(-3.5 * LDU_PER_STUD, 2)],
                "purpose": "Crew neck frontal collar rim tile 1x4",
            })
            # Trasero Z = +4
            self.shoulder_parts.append({
                "id": self._next_id("collar_back"),
                "ref": "2431.dat",
                "colour": color_clothing,
                "at": [0.0, -(144 + LDU_PLATE_HEIGHT), round(3.5 * LDU_PER_STUD, 2)],
                "purpose": "Crew neck dorsal collar rim tile 1x4",
            })

        # Nivel 10 (h = 168, espesor 24 LDU): Cuello medio cilíndrico/elíptico
        # Span X: 6 studs [-3, +3], Z: 6 studs [-3, +3] cross-bonded
        self._add_brick_rect(-3, -3, 6, 6, h=168, colour=color_skin, purpose="Mid cervical neck cylinder 6x6", cross_orient=True)

    def build_cranium_core(
        self,
        head_width_studs: int = 18,
        head_height_bricks: int = 16,
        head_depth_studs: int = 20,
        base_h: float = 192.0,
        color_core: int = 72,
        color_skin: int = 78,
    ) -> None:
        """
        Genera un núcleo estructural interno resistente con puntos de anclaje SNOT
        (Anchor Points) precalculados y expuestos hacia el frente y laterales.
        """
        # El núcleo interno ocupa un volumen sólido rectangular ligeramente menor
        # que las dimensiones exteriores (para alojar el cladding epidérmico de 1-2 studs)
        core_w = max(6, head_width_studs - 4)  # ej. 14 studs
        core_d = max(8, head_depth_studs - 4)  # ej. 16 studs
        hw = core_w // 2
        hd = core_d // 2

        current_h = base_h
        for layer_idx in range(head_height_bricks):
            cross = (layer_idx % 2 == 1)
            layer_h = current_h
            # Crear capa interna sólida
            self._add_brick_rect(
                -hw, -hd, core_w, core_d,
                h=layer_h,
                colour=color_core,
                purpose=f"Cranium core rigid layer {layer_idx + 1}/{head_height_bricks}",
                cross_orient=cross,
                cranium=True,
            )
            current_h += LDU_BRICK_HEIGHT

        total_cranium_top_h = current_h

        # =====================================================================
        # PUNTOS DE ANCLAJE SNOT EXPUESTOS EN EL PERÍMETRO DEL NÚCLEO
        # =====================================================================
        # Frente del cráneo Z = -hd (en studs: -hd * 20 LDU)
        # Línea horizontal media de ojos y cejas: capa ~7 de la cabeza
        eye_brow_h = base_h + 7 * LDU_BRICK_HEIGHT
        nose_bridge_h = base_h + 5 * LDU_BRICK_HEIGHT
        jaw_chin_h = base_h + 2 * LDU_BRICK_HEIGHT
        cheekbones_h = base_h + 4 * LDU_BRICK_HEIGHT
        ears_h = base_h + 6 * LDU_BRICK_HEIGHT
        hair_cap_h = total_cranium_top_h

        # 1. ANCHOR_EYES_BROW (Línea media horizontal del cráneo)
        front_z_ldu = -hd * LDU_PER_STUD
        self.anchors["ANCHOR_EYES_BROW"] = {
            "name": "ANCHOR_EYES_BROW",
            "at_ldu": [0.0, h_to_ldu_y(eye_brow_h), front_z_ldu],
            "at_studs": [0.0, eye_brow_h / LDU_PER_STUD, -hd],
            "normal": [0.0, 0.0, -1.0],
            "description": "Mid-cranium horizontal line for orbits, eyeballs and brow arches",
        }
        # Colocar adaptadores SNOT (11211.dat 1x2 con 2 studs laterales) para ojos izquierdo y derecho
        self._add_snot_adapter(-3, eye_brow_h, -hd, colour=color_skin, snot_face="front")
        self._add_snot_adapter(1, eye_brow_h, -hd, colour=color_skin, snot_face="front")

        # 2. ANCHOR_NOSE_BRIDGE (Eje X=0, entre ojos y philtrum)
        self.anchors["ANCHOR_NOSE_BRIDGE"] = {
            "name": "ANCHOR_NOSE_BRIDGE",
            "at_ldu": [0.0, h_to_ldu_y(nose_bridge_h), front_z_ldu],
            "at_studs": [0.0, nose_bridge_h / LDU_PER_STUD, -hd],
            "normal": [0.0, 0.0, -1.0],
            "description": "Sagittal axis X=0 anchor for nasal septum, bridge and cartilages",
        }
        # SNOT 87087.dat en X=0
        self._add_snot_adapter(0, nose_bridge_h, -hd, colour=color_skin, snot_face="front")

        # 3. ANCHOR_CHEEKBONES_L_R (Pómulos simétricos)
        cheek_x_studs = hw - 2
        self.anchors["ANCHOR_CHEEKBONES_L"] = {
            "name": "ANCHOR_CHEEKBONES_L",
            "at_ldu": [cheek_x_studs * LDU_PER_STUD, h_to_ldu_y(cheekbones_h), front_z_ldu],
            "at_studs": [cheek_x_studs, cheekbones_h / LDU_PER_STUD, -hd],
            "normal": [0.707, 0.0, -0.707],
            "description": "Anatomical Left Zygomatic bone / cheek apple anchor",
        }
        self.anchors["ANCHOR_CHEEKBONES_R"] = {
            "name": "ANCHOR_CHEEKBONES_R",
            "at_ldu": [-cheek_x_studs * LDU_PER_STUD, h_to_ldu_y(cheekbones_h), front_z_ldu],
            "at_studs": [-cheek_x_studs, cheekbones_h / LDU_PER_STUD, -hd],
            "normal": [-0.707, 0.0, -0.707],
            "description": "Anatomical Right Zygomatic bone / cheek apple anchor",
        }
        self._add_snot_adapter(cheek_x_studs - 1, cheekbones_h, -hd, colour=color_skin, snot_face="front")
        self._add_snot_adapter(-cheek_x_studs, cheekbones_h, -hd, colour=color_skin, snot_face="front")

        # 4. ANCHOR_JAW_CHIN_MOUTH (Tercio inferior facial, parametrizable para piel o barba)
        self.anchors["ANCHOR_JAW_CHIN_MOUTH"] = {
            "name": "ANCHOR_JAW_CHIN_MOUTH",
            "at_ldu": [0.0, h_to_ldu_y(jaw_chin_h), front_z_ldu],
            "at_studs": [0.0, jaw_chin_h / LDU_PER_STUD, -hd],
            "normal": [0.0, 0.0, -1.0],
            "description": "Lower facial third anchor for lips, chin apex and beard volume",
        }
        self._add_snot_adapter(-1, jaw_chin_h, -hd, colour=color_skin, snot_face="front")

        # 5. ANCHOR_EARS_L_R (Alineadas verticalmente entre arco superciliar y base de la nariz)
        left_ear_x_ldu = hw * LDU_PER_STUD
        right_ear_x_ldu = -hw * LDU_PER_STUD
        mid_z_stud = 0.0
        self.anchors["ANCHOR_EARS_L"] = {
            "name": "ANCHOR_EARS_L",
            "at_ldu": [left_ear_x_ldu, h_to_ldu_y(ears_h), mid_z_stud * LDU_PER_STUD],
            "at_studs": [hw, ears_h / LDU_PER_STUD, mid_z_stud],
            "normal": [1.0, 0.0, 0.0],
            "description": "Anatomical Left Auricle anchor at temporal bone",
        }
        self.anchors["ANCHOR_EARS_R"] = {
            "name": "ANCHOR_EARS_R",
            "at_ldu": [right_ear_x_ldu, h_to_ldu_y(ears_h), mid_z_stud * LDU_PER_STUD],
            "at_studs": [-hw, ears_h / LDU_PER_STUD, mid_z_stud],
            "normal": [-1.0, 0.0, 0.0],
            "description": "Anatomical Right Auricle anchor at temporal bone",
        }
        # SNOT bricks en laterales
        self._add_snot_adapter(hw - 1, ears_h, 0, colour=color_skin, snot_face="left")
        self._add_snot_adapter(-hw, ears_h, 0, colour=color_skin, snot_face="right")

        # 6. ANCHOR_HAIR_CAP (Casquete superior, sienes y nuca)
        self.anchors["ANCHOR_HAIR_CAP"] = {
            "name": "ANCHOR_HAIR_CAP",
            "at_ldu": [0.0, h_to_ldu_y(hair_cap_h), 0.0],
            "at_studs": [0.0, hair_cap_h / LDU_PER_STUD, 0.0],
            "normal": [0.0, -1.0, 0.0],
            "description": "Cranial vertex and parietal dome hair cap anchor",
        }
        self.anchors["ANCHOR_HAIR_NAPE"] = {
            "name": "ANCHOR_HAIR_NAPE",
            "at_ldu": [0.0, h_to_ldu_y(jaw_chin_h), hd * LDU_PER_STUD],
            "at_studs": [0.0, jaw_chin_h / LDU_PER_STUD, hd],
            "normal": [0.0, 0.0, 1.0],
            "description": "Occipital and nuchal hairline anchor",
        }

    @property
    def ANCHOR_MAP(self) -> Dict[str, Dict[str, Any]]:
        """Acceso directo al diccionario de coordenadas de anclaje."""
        return self.anchors

    def get_anchor_map(self) -> Dict[str, Dict[str, Any]]:
        """Devuelve una copia del mapa de anclajes anatómicos."""
        return copy.deepcopy(self.anchors)

    # -------------------------------------------------------------------------
    # MÉTODOS DE SOPORTE INTERNO (Construcción modular libre de colisiones)
    # -------------------------------------------------------------------------
    def _add_plate_rect(
        self,
        x0: int,
        z0: int,
        w: int,
        d: int,
        h: float,
        colour: int,
        purpose: str = "",
    ) -> None:
        """
        Cubre un rectángulo [x0, x0+w] x [z0, z0+d] con plates LEGO sin solapamientos.
        'h' es la elevación de la base de la capa. La posición LDraw Y de la placa es -(h + 8).
        """
        y_ldu = -(h + LDU_PLATE_HEIGHT)
        curr_z = z0
        while curr_z < z0 + d:
            step_d = 2 if (z0 + d - curr_z) >= 2 else 1
            curr_x = x0
            while curr_x < x0 + w:
                step_w = 4 if (x0 + w - curr_x) >= 4 else (2 if (x0 + w - curr_x) >= 2 else 1)

                if step_w == 4 and step_d == 2:
                    ref, yaw = "3020.dat", 0
                elif step_w == 2 and step_d == 2:
                    ref, yaw = "3022.dat", 0
                elif step_w == 2 and step_d == 1:
                    ref, yaw = "3023.dat", 0
                elif step_w == 1 and step_d == 2:
                    ref, yaw = "3023.dat", 90
                elif step_w == 4 and step_d == 1:
                    ref, yaw = "3710.dat", 0
                elif step_w == 1 and step_d == 4:
                    ref, yaw = "3710.dat", 90
                else:
                    ref, yaw = "3024.dat", 0

                cx = curr_x + step_w / 2.0
                cz = curr_z + step_d / 2.0

                part_data = {
                    "id": self._next_id("ped_plt"),
                    "ref": ref,
                    "colour": colour,
                    "at": [round(cx * LDU_PER_STUD, 2), round(y_ldu, 2), round(cz * LDU_PER_STUD, 2)],
                    "purpose": purpose,
                }
                if yaw:
                    part_data["yaw"] = yaw
                self.pedestal_parts.append(part_data)

                curr_x += step_w
            curr_z += step_d

    def _add_brick_rect(
        self,
        x0: int,
        z0: int,
        w: int,
        d: int,
        h: float,
        colour: int,
        purpose: str = "",
        cross_orient: bool = False,
        cranium: bool = False,
    ) -> None:
        """
        Cubre un rectángulo [x0, x0+w] x [z0, z0+d] con bricks LEGO sin solapamientos.
        'h' es la elevación de la base de la capa. La posición LDraw Y del ladrillo es -(h + 24).
        """
        y_ldu = -(h + LDU_BRICK_HEIGHT)
        target_list = self.cranium_parts if cranium else (self.shoulder_parts if h >= 72 else self.pedestal_parts)

        if not cross_orient:
            # Orientación principal a lo largo de X
            curr_z = z0
            while curr_z < z0 + d:
                step_d = 2 if (z0 + d - curr_z) >= 2 else 1
                curr_x = x0
                while curr_x < x0 + w:
                    step_w = 4 if (x0 + w - curr_x) >= 4 else (2 if (x0 + w - curr_x) >= 2 else 1)

                    if step_w == 4 and step_d == 2:
                        ref, yaw = "3001.dat", 0
                    elif step_w == 2 and step_d == 2:
                        ref, yaw = "3003.dat", 0
                    elif step_w == 2 and step_d == 1:
                        ref, yaw = "3004.dat", 0
                    elif step_w == 1 and step_d == 2:
                        ref, yaw = "3004.dat", 90
                    elif step_w == 4 and step_d == 1:
                        ref, yaw = "3010.dat", 0
                    elif step_w == 1 and step_d == 4:
                        ref, yaw = "3010.dat", 90
                    else:
                        ref, yaw = "3005.dat", 0

                    cx = curr_x + step_w / 2.0
                    cz = curr_z + step_d / 2.0

                    part_data = {
                        "id": self._next_id("crn_brk" if cranium else "brk"),
                        "ref": ref,
                        "colour": colour,
                        "at": [round(cx * LDU_PER_STUD, 2), round(y_ldu, 2), round(cz * LDU_PER_STUD, 2)],
                        "purpose": purpose,
                    }
                    if yaw:
                        part_data["yaw"] = yaw
                    target_list.append(part_data)

                    curr_x += step_w
                curr_z += step_d
        else:
            # Orientación cruzada (cross-bonding) a lo largo de Z
            curr_x = x0
            while curr_x < x0 + w:
                step_w = 2 if (x0 + w - curr_x) >= 2 else 1
                curr_z = z0
                while curr_z < z0 + d:
                    step_d = 4 if (z0 + d - curr_z) >= 4 else (2 if (z0 + d - curr_z) >= 2 else 1)

                    if step_w == 2 and step_d == 4:
                        ref, yaw = "3001.dat", 90
                    elif step_w == 2 and step_d == 2:
                        ref, yaw = "3003.dat", 0
                    elif step_w == 1 and step_d == 2:
                        ref, yaw = "3004.dat", 90
                    elif step_w == 2 and step_d == 1:
                        ref, yaw = "3004.dat", 0
                    elif step_w == 1 and step_d == 4:
                        ref, yaw = "3010.dat", 90
                    elif step_w == 4 and step_d == 1:
                        ref, yaw = "3010.dat", 0
                    else:
                        ref, yaw = "3005.dat", 0

                    cx = curr_x + step_w / 2.0
                    cz = curr_z + step_d / 2.0

                    part_data = {
                        "id": self._next_id("crn_brk" if cranium else "brk"),
                        "ref": ref,
                        "colour": colour,
                        "at": [round(cx * LDU_PER_STUD, 2), round(y_ldu, 2), round(cz * LDU_PER_STUD, 2)],
                        "purpose": purpose,
                    }
                    if yaw:
                        part_data["yaw"] = yaw
                    target_list.append(part_data)

                    curr_z += step_d
                curr_x += step_w

    def _add_snot_adapter(
        self,
        x_stud: int,
        h: float,
        z_stud: int,
        colour: int,
        snot_face: str = "front",
    ) -> None:
        """
        Añade un adaptador SNOT (87087.dat 1x1 con stud lateral) en la capa de elevación base h.
        La posición LDraw Y es -(h + 24).
        """
        y_ldu = -(h + LDU_BRICK_HEIGHT)
        yaw = 0
        if snot_face == "front":
            yaw = 0
        elif snot_face == "back":
            yaw = 180
        elif snot_face == "left":
            yaw = -90
        elif snot_face == "right":
            yaw = 90

        cx = x_stud + 0.5
        cz = z_stud + 0.5

        part_data = {
            "id": self._next_id("snot_adp"),
            "ref": "87087.dat",
            "colour": colour,
            "at": [round(cx * LDU_PER_STUD, 2), round(y_ldu, 2), round(cz * LDU_PER_STUD, 2)],
            "purpose": f"SNOT adapter brick facing {snot_face}",
        }
        if yaw:
            part_data["yaw"] = yaw
        self.cranium_parts.append(part_data)

    def build_canonical_submodels(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Genera los 7 submodelos canónicos requeridos por la especificación:
        01_base_shoulders_neck.ldr
        02_cranium_structural_core.ldr
        03_jaw_beard_mouth.ldr
        04_cheekbones_midface.ldr
        05_nose_bridge_snot.ldr
        06_eyes_brows_forehead.ldr
        07_ears_and_hair_sculpture.ldr
        """
        # Asegurarse de que el maniquí base y el núcleo están generados
        if not self.pedestal_parts:
            self.build_pedestal_and_shoulders()
        if not self.cranium_parts:
            self.build_cranium_core()

        submodels: Dict[str, List[Dict[str, Any]]] = {}

        # 01. BASE, HOMBROS Y CUELLO
        submodels["01_base_shoulders_neck.ldr"] = self.pedestal_parts + self.shoulder_parts

        # 02. NÚCLEO ESTRUCTURAL DEL CRÁNEO
        submodels["02_cranium_structural_core.ldr"] = self.cranium_parts

        # 03. MANDÍBULA, BARBA Y BOCA
        jaw_anchor = self.anchors.get("ANCHOR_JAW_CHIN_MOUTH", {"at_ldu": [0.0, -240.0, -160.0]})
        j_at = jaw_anchor["at_ldu"]
        jaw_parts: List[Dict[str, Any]] = [
            # Base del mentón (Tile 1x2 SNOT en Z = j_at[2] - 8.0, X spans [-20, 20], Y spans [j_at[1]-10, j_at[1]+10])
            {
                "id": self._next_id("jaw_chin_tile"),
                "ref": "3069b.dat",
                "colour": 78,
                "at": [j_at[0], j_at[1], j_at[2] - 8.0],
                "matrix": ROT_FRONT,
                "purpose": "Chin apex horizontal plate SNOT",
            },
            # Labio inferior y bermellón (slope 1x2 en Y = j_at[1] - 20, X spans [-20, 20], Y spans [j_at[1]-30, j_at[1]-10])
            {
                "id": self._next_id("jaw_lip_inf"),
                "ref": "85984.dat",
                "colour": 84,  # Medium Nougat in official LDConfig
                "at": [j_at[0], j_at[1] - 20.0, j_at[2] - 8.0],
                "matrix": ROT_FRONT,
                "purpose": "Lower vermilion border slope 1x2",
            },
        ]
        # Texturizado orgánico de barba con apply_beard_or_hair_texture
        # Puntos muestreados fuera del rectángulo [-20, 20] x [j_at[1]-30, j_at[1]+10]
        beard_sample_points = [
            {"at": [j_at[0] - 30.0, j_at[1], j_at[2] - 8.0], "normal": [0.0, 0.0, -1.0]},
            {"at": [j_at[0] + 30.0, j_at[1], j_at[2] - 8.0], "normal": [0.0, 0.0, -1.0]},
            {"at": [j_at[0], j_at[1] + 20.0, j_at[2] - 8.0], "normal": [0.0, 0.0, -1.0]},
        ]
        beard_texture = apply_beard_or_hair_texture(
            beard_sample_points,
            palette_colors=[0, 72, 71, 308],
            roughness=1.0,
            seed=42,
        )
        jaw_parts.extend(beard_texture)
        submodels["03_jaw_beard_mouth.ldr"] = jaw_parts

        # 04. PÓMULOS Y TERCIO MEDIO FACIAL
        cheek_l = self.anchors.get("ANCHOR_CHEEKBONES_L", {"at_ldu": [100.0, -288.0, -160.0]})
        cheek_r = self.anchors.get("ANCHOR_CHEEKBONES_R", {"at_ldu": [-100.0, -288.0, -160.0]})
        midface_parts: List[Dict[str, Any]] = [
            # Pómulo izquierdo
            {
                "id": self._next_id("cheek_l_slp"),
                "ref": "11477.dat",
                "colour": 78,
                "at": [cheek_l["at_ldu"][0], cheek_l["at_ldu"][1], cheek_l["at_ldu"][2] - 8.0],
                "matrix": ROT_FRONT,
                "purpose": "Left zygomatic cheek apple curved slope 1x2",
            },
            # Pómulo derecho simétrico
            {
                "id": self._next_id("cheek_r_slp"),
                "ref": "11477.dat",
                "colour": 78,
                "at": [cheek_r["at_ldu"][0], cheek_r["at_ldu"][1], cheek_r["at_ldu"][2] - 8.0],
                "matrix": ROT_FRONT,
                "purpose": "Right zygomatic cheek apple curved slope 1x2",
            },
        ]
        submodels["04_cheekbones_midface.ldr"] = midface_parts

        # 05. TABIQUE NASAL Y CARTÍLAGO SNOT
        nose_anchor = self.anchors.get("ANCHOR_NOSE_BRIDGE", {"at_ldu": [0.0, -312.0, -160.0]})
        n_at = nose_anchor["at_ldu"]
        nose_parts: List[Dict[str, Any]] = [
            # Dorso nasal SNOT
            {
                "id": self._next_id("nose_bridge_tile"),
                "ref": "3069b.dat",
                "colour": 78,
                "at": [n_at[0], n_at[1], n_at[2] - 12.0],
                "matrix": ROT_FRONT,
                "purpose": "Nasal bone bridge tile 1x2 SNOT",
            },
            # Punta nasal de queso 54200.dat
            {
                "id": self._next_id("nose_tip_cheese"),
                "ref": "54200.dat",
                "colour": 78,
                "at": [n_at[0], n_at[1] + 8.0, n_at[2] - 16.0],
                "matrix": ROT_FRONT,
                "purpose": "Nasal apex tip cheese slope 30 deg",
            },
        ]
        submodels["05_nose_bridge_snot.ldr"] = nose_parts

        # 06. OJOS, CEJAS Y FRENTE
        eye_anchor = self.anchors.get("ANCHOR_EYES_BROW", {"at_ldu": [0.0, -360.0, -160.0]})
        e_at = eye_anchor["at_ldu"]
        eyes_parts: List[Dict[str, Any]] = [
            # Ojo izquierdo: Esclerótica blanca (15) y pupila negra (0)
            {
                "id": self._next_id("eye_l_sclera"),
                "ref": "3024.dat",
                "colour": 15,
                "at": [e_at[0] + 40.0, e_at[1], e_at[2] - 8.0],
                "matrix": ROT_FRONT,
                "purpose": "Left eye sclera plate 1x1 White",
            },
            {
                "id": self._next_id("eye_l_pupil"),
                "ref": "98138.dat",
                "colour": 0,
                "at": [e_at[0] + 40.0, e_at[1], e_at[2] - 16.0],
                "matrix": ROT_FRONT,
                "purpose": "Left eye pupil round tile 1x1 Black",
            },
            # Ceja izquierda
            {
                "id": self._next_id("brow_l"),
                "ref": "85984.dat",
                "colour": 0,
                "at": [e_at[0] + 40.0, e_at[1] - 8.0, e_at[2] - 8.0],
                "matrix": ROT_FRONT,
                "purpose": "Left superciliary arch slope 1x2",
            },
        ]
        # Ojo derecho generado por simetría bilateral estricta con mirror_feature_x
        right_eye_mirrored = mirror_feature_x(eyes_parts)
        eyes_parts.extend(right_eye_mirrored)
        submodels["06_eyes_brows_forehead.ldr"] = eyes_parts

        # 07. OREJAS Y CASQUETE CAPILAR
        ear_l = self.anchors.get("ANCHOR_EARS_L", {"at_ldu": [140.0, -336.0, 0.0]})
        ear_r = self.anchors.get("ANCHOR_EARS_R", {"at_ldu": [-140.0, -336.0, 0.0]})
        hair_cap = self.anchors.get("ANCHOR_HAIR_CAP", {"at_ldu": [0.0, -576.0, 0.0]})
        ears_hair_parts: List[Dict[str, Any]] = [
            # Oreja izquierda (Pabellón auricular con tile redondeado)
            {
                "id": self._next_id("ear_l_helix"),
                "ref": "24246.dat",
                "colour": 78,
                "at": [ear_l["at_ldu"][0] + 8.0, ear_l["at_ldu"][1], ear_l["at_ldu"][2]],
                "matrix": ROT_LEFT,
                "purpose": "Left ear auricle helix tile half-round",
            },
            # Oreja derecha simétrica
            {
                "id": self._next_id("ear_r_helix"),
                "ref": "24246.dat",
                "colour": 78,
                "at": [ear_r["at_ldu"][0] - 8.0, ear_r["at_ldu"][1], ear_r["at_ldu"][2]],
                "matrix": ROT_RIGHT,
                "purpose": "Right ear auricle helix tile half-round",
            },
            # Casquete superior de pelo (cúpula parietal en tono 308 Dark Brown)
            {
                "id": self._next_id("hair_top_slp"),
                "ref": "15068.dat",
                "colour": 308,
                "at": [0.0, hair_cap["at_ldu"][1] - 8.0, 0.0],
                "purpose": "Cranial vertex hair cap curved slope 2x2",
            },
        ]
        submodels["07_ears_and_hair_sculpture.ldr"] = ears_hair_parts

        return submodels

    def export_plan(self) -> Dict[str, Any]:
        """
        Exporta el ensamblaje completo como un diccionario conforme a plan.schema.json
        con el archivo maestro y las 7 secciones de submódulos.
        """
        submodels = self.build_canonical_submodels()

        sections: List[Dict[str, Any]] = []

        # 1. Sección Maestra Principal (Ensambla los 7 submódulos)
        master_steps = [[
            {"id": f"inst_{name.replace('.ldr', '')}", "ref": name, "colour": 16, "at": [0, 0, 0]}
            for name in submodels.keys()
        ]]
        sections.append({
            "name": f"{self.name}.ldr",
            "description": f"{self.description} - Master Scene Assembly",
            "anchors": {"base": {"at": [0, 0, 0]}},
            "steps": master_steps,
        })

        # 2. Las 7 Secciones de Submódulos
        for sub_name, parts in submodels.items():
            sections.append({
                "name": sub_name,
                "description": f"Submodel {sub_name}",
                "anchors": {"base": {"at": [0, 0, 0]}},
                "steps": [parts],
            })

        return {
            "version": 1,
            "author": "LdrawNova HD Human Bust Domain Profile",
            "profile": "bust_hd",
            "sections": sections,
        }
