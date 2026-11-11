"""Ldraw-Nova Generalist High-Fidelity Sculptor Engine (Strict Discrete Grid).

Every level has a strictly defined discrete Y level:
- Level 0 (Y = 0): Pedestal Baseplate (Plate 8x8) -> Top at Y = 0
- Level 1 (Y = -24): Pedestal lower column (Brick 2x2, H=24) -> Top at Y = -24
- Level 2 (Y = -48): Pedestal upper column (Brick 2x2, H=24) -> Top at Y = -48
- Level 3 (Y = -56): Torso Baseplate (Plate 2x6, H=8) -> Top at Y = -56
- Level 4 (Y = -80): Torso Main Infill (Bricks 2x4, H=24) -> Top at Y = -80
- Level 5 (Y = -88): Torso Top Shoulder Cross-Plate (Plate 2x6, H=8) -> Top at Y = -88
- Level 6 (Y = -112): Neck Base (Brick 2x2, H=24) -> Top at Y = -112
- Level 7 (Y = -136): Neck Upper (Brick 2x2, H=24) -> Top at Y = -136
- Level 8 (Y = -144): Jaw/Mandible Base Plate (Plate 2x4, H=8) -> Top at Y = -144
- Level 9 (Y = -168): Lower Face / Beard SNOT Base (Brick 2x2 + SNOT 87087, H=24) -> Top at Y = -168
- Level 10 (Y = -176): Mid Face / Cheeks / Nose Plate (Plate 2x4, H=8) -> Top at Y = -176
- Level 11 (Y = -200): Upper Face / Eyes / Skull Core (Brick 2x2, H=24) -> Top at Y = -200
- Level 12 (Y = -208): Forehead / Eyebrow Plate (Plate 2x4, H=8) -> Top at Y = -208
- Level 13 (Y = -232): Cranium Vault (Brick 2x4, H=24) -> Top at Y = -232
- Level 14 (Y = -240): Top Hair Surface Slopes (Curved Slopes 50950 / 11477, H=8/18) -> Top at Y = -258

In X and Z, parts are placed on strict integer stud coordinates:
- 1 stud = 20 LDU
- Brick 2x4 (3001): 80 LDU in X, 40 LDU in Z (when yaw=0) -> Centers must be multiples of 80 in X, 40 in Z.
- Brick 2x2 (3003): 40 LDU in X, 40 LDU in Z -> Centers must be multiples of 40 in X, 40 in Z.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

U = 20
PLATE_H = 8
BRICK_H = 24

def s(n: float) -> int:
    return int(round(n * U))


class LDrawPart:
    def __init__(
        self,
        pid: str,
        ref: str,
        colour: int,
        at: Tuple[float, float, float],
        yaw: int = 0,
        purpose: Optional[str] = None
    ):
        clean_id = str(pid).replace(".", "_").replace("-", "_").replace(" ", "_")
        self.pid = f"p_{clean_id}"
        self.ref = ref
        self.colour = int(colour)
        self.at = [int(round(at[0])), int(round(at[1])), int(round(at[2]))]
        self.yaw = yaw
        self.purpose = purpose

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.pid,
            "ref": self.ref,
            "colour": self.colour,
            "at": self.at
        }
        if self.yaw:
            d["yaw"] = self.yaw
        if self.purpose:
            d["purpose"] = self.purpose
        return d


class HighFidelitySculptEngine:
    def __init__(self, slug: str, brief_data: Dict[str, Any]):
        self.slug = slug
        self.brief_data = brief_data
        self.colors = brief_data.get("colors", [])
        self.palette = self._resolve_palette()

    def _resolve_palette(self) -> Dict[str, int]:
        codes = [c["code"] for c in self.colors] if self.colors else []
        return {
            "pedestal": next((c for c in codes if c in [0, 72, 70]), 0),
            "clothing": next((c for c in codes if c in [272, 1, 4, 2, 26, 25, 288, 70, 72]), 272),
            "skin_base": next((c for c in codes if c in [19, 78]), 19),
            "skin_shadow": next((c for c in codes if c in [28, 84]), 28),
            "beard_main": next((c for c in codes if c in [72, 71, 0]), 72),
            "beard_highlight": next((c for c in codes if c in [71, 15, 179]), 71),
            "hair_main": next((c for c in codes if c in [70, 308, 0]), 70),
            "hair_accent": next((c for c in codes if c in [308, 0, 70]), 308),
            "white": 15,
            "black": 0,
        }

    def generate_plan(self) -> Dict[str, Any]:
        sub_pedestal = self._build_pedestal_section()
        sub_torso = self._build_torso_section()
        sub_neck = self._build_neck_section()
        sub_beard = self._build_beard_section()
        sub_face = self._build_face_section()
        sub_hair = self._build_hair_section()

        root_steps = [[
            LDrawPart("m_ped", "01-pedestal.ldr", 16, (0, 0, 0), purpose="Submodelo Pedestal").to_dict(),
            LDrawPart("m_torso", "02-torso-jersey.ldr", 16, (0, 0, 0), purpose="Submodelo Torso").to_dict(),
            LDrawPart("m_neck", "03-cuello-soporte.ldr", 16, (0, 0, 0), purpose="Submodelo Cuello").to_dict(),
            LDrawPart("m_beard", "04-barba-bigote.ldr", 16, (0, 0, 0), purpose="Submodelo Barba SNOT").to_dict(),
            LDrawPart("m_face", "05-rostro-facciones.ldr", 16, (0, 0, 0), purpose="Submodelo Rostro").to_dict(),
            LDrawPart("m_hair", "06-cabello-craneo.ldr", 16, (0, 0, 0), purpose="Submodelo Cabello 360°").to_dict(),
        ]]

        root_sec = {
            "name": f"{self.slug}.ldr",
            "description": f"Main assembly {self.slug} - High Fidelity LEGO Sculpture",
            "steps": root_steps
        }

        return {
            "version": 1,
            "author": "Antigravity 2.0 (High-Fidelity Sculpt Engine)",
            "license": "CC-BY-4.0",
            "sections": [
                root_sec,
                sub_pedestal,
                sub_torso,
                sub_neck,
                sub_beard,
                sub_face,
                sub_hair
            ]
        }

    # 1. Pedestal (Y=0 a Y=-48)
    def _build_pedestal_section(self) -> Dict[str, Any]:
        c = self.palette["pedestal"]
        steps = [
            # Nivel 0 (Y=0): Baseplate 8x8 (160x160 LDU)
            [LDrawPart("pb_0", "41539.dat", c, (0, 0, 0), purpose="Baseplate 8x8").to_dict()],
            # Nivel 1 (Y=-24): Columna de Brick 2x2 + Biseles front/back
            [
                LDrawPart("p_col_1", "3003.dat", c, (0, -BRICK_H, 0), purpose="Columna central 2x2").to_dict(),
                LDrawPart("p_sl_f", "3039.dat", c, (0, -BRICK_H, s(3)), yaw=180).to_dict(),
                LDrawPart("p_sl_b", "3039.dat", c, (0, -BRICK_H, -s(3)), yaw=0).to_dict(),
            ],
            # Nivel 2 (Y=-48): Columna superior 2x2
            [LDrawPart("p_col_2", "3003.dat", c, (0, -2 * BRICK_H, 0), purpose="Columna superior 2x2").to_dict()],
        ]
        return {"name": "01-pedestal.ldr", "description": "Pedestal macizo escalonado", "steps": steps}

    # 2. Torso y Hombros (Y=-56 a Y=-88)
    # Envergadura: 24 studs en X (480 LDU), 8 studs en Z (160 LDU)
    def _build_torso_section(self) -> Dict[str, Any]:
        c = self.palette["clothing"]
        steps = [
            # Nivel 3 (Y=-56): Plate 2x6 trabadora sobre el pedestal
            [LDrawPart("t_b_c", "3795.dat", c, (0, -56, 0), yaw=0).to_dict()],
            # Nivel 4 (Y=-80): Capa maciza de hombros (Bricks 2x4 espaciados 80 LDU)
            [
                # Centro (X=0, Z=0)
                LDrawPart("t_m_c", "3001.dat", c, (0, -80, 0), yaw=0).to_dict(),
                # Hombro izquierdo (X=-80) y derecho (X=80)
                LDrawPart("t_m_l", "3001.dat", c, (-s(4), -80, 0), yaw=0).to_dict(),
                LDrawPart("t_m_r", "3001.dat", c, (s(4), -80, 0), yaw=0).to_dict(),
                # Hombro extremo izq (X=-140) y der (X=140) con Slopes 45°
                LDrawPart("t_sl_l", "3039.dat", c, (-s(7), -80, 0), yaw=270).to_dict(),
                LDrawPart("t_sl_r", "3039.dat", c, (s(7), -80, 0), yaw=90).to_dict(),
            ],
            # Nivel 5 (Y=-88): Traba superior de hombros (Plates 2x4 a X=-80 y +80)
            [
                LDrawPart("t_top_l", "3020.dat", c, (-s(4), -88, 0), yaw=0).to_dict(),
                LDrawPart("t_top_r", "3020.dat", c, (s(4), -88, 0), yaw=0).to_dict(),
                # Clavícula frontal y espalda (Plates 1x2 en Z=2 y Z=-2)
                LDrawPart("t_top_f", "3023.dat", c, (0, -88, s(1.5)), yaw=0).to_dict(),
                LDrawPart("t_top_b", "3023.dat", c, (0, -88, -s(1.5)), yaw=0).to_dict(),
            ]
        ]
        return {"name": "02-torso-jersey.ldr", "description": "Torso macizo de hombros anchos", "steps": steps}

    # 3. Cuello (Y=-112 a Y=-144)
    def _build_neck_section(self) -> Dict[str, Any]:
        c = self.palette["skin_base"]
        steps = [
            # Nivel 6 (Y=-112): Cuello base (Brick 2x2 apoyado sobre torso en Y=-88)
            [LDrawPart("n_b1", "3003.dat", c, (0, -112, 0), yaw=0).to_dict()],
            # Nivel 7 (Y=-136): Cuello superior (Brick 2x2)
            [LDrawPart("n_b2", "3003.dat", c, (0, -136, 0), yaw=0).to_dict()],
            # Nivel 8 (Y=-144): Placa base mandíbula (Plate 2x4 trabadora hacia el frente)
            [LDrawPart("n_jaw", "3020.dat", c, (0, -144, s(0.5)), yaw=0).to_dict()],
        ]
        return {"name": "03-cuello-soporte.ldr", "description": "Columna anatómica del cuello", "steps": steps}

    # 4. Barba y Bigote SNOT (Y=-168)
    def _build_beard_section(self) -> Dict[str, Any]:
        c_b = self.palette["beard_main"]
        c_hi = self.palette["beard_highlight"]
        steps = [
            # Nivel 9 (Y=-168): Ladrillos SNOT en mentón (Z=2 studs = 40 LDU)
            [
                LDrawPart("b_sn_c", "87087.dat", c_b, (0, -168, s(2)), yaw=0).to_dict(),
                LDrawPart("b_sn_l", "87087.dat", c_b, (-s(1), -168, s(2)), yaw=0).to_dict(),
                LDrawPart("b_sn_r", "87087.dat", c_b, (s(1), -168, s(2)), yaw=0).to_dict(),
                # Patillas en rejilla lateral a X=-40 y X=40
                LDrawPart("b_pat_l", "2412b.dat", c_b, (-s(2), -168, 0), yaw=90).to_dict(),
                LDrawPart("b_pat_r", "2412b.dat", c_b, (s(2), -168, 0), yaw=90).to_dict(),
            ],
            # Relieve de barba y bigote (Cheese slopes)
            [
                LDrawPart("b_must_c", "54200.dat", c_hi, (0, -174, s(2.6)), yaw=180).to_dict(),
                LDrawPart("b_must_l", "54200.dat", c_b, (-s(1), -174, s(2.6)), yaw=270).to_dict(),
                LDrawPart("b_must_r", "54200.dat", c_b, (s(1), -174, s(2.6)), yaw=90).to_dict(),
            ]
        ]
        return {"name": "04-barba-bigote.ldr", "description": "Barba y bigote SNOT con textura", "steps": steps}

    # 5. Rostro, Pómulos, Ojos y Nariz (Y=-176 a Y=-208)
    def _build_face_section(self) -> Dict[str, Any]:
        c_skin = self.palette["skin_base"]
        c_sh = self.palette["skin_shadow"]
        c_hair = self.palette["hair_main"]
        c_w = self.palette["white"]
        c_k = self.palette["black"]
        steps = [
            # Nivel 10 (Y=-176): Plate 2x4 mejillas y soporte nasal
            [
                LDrawPart("f_base", "3020.dat", c_skin, (0, -176, s(0.5)), yaw=0).to_dict(),
                # Pómulos curvados
                LDrawPart("f_pom_l", "11477.dat", c_skin, (-s(1.5), -176, s(1.5)), yaw=180).to_dict(),
                LDrawPart("f_pom_r", "11477.dat", c_skin, (s(1.5), -176, s(1.5)), yaw=180).to_dict(),
                # Nariz cheese slope
                LDrawPart("f_nose", "54200.dat", c_sh, (0, -176, s(2.5)), yaw=180).to_dict(),
            ],
            # Nivel 11 (Y=-200): Núcleo de ojos y cráneo (Brick 2x2 en X=0)
            [
                LDrawPart("f_eye_core", "3003.dat", c_skin, (0, -200, 0), yaw=0).to_dict(),
                # Ojos en Z=1.5
                LDrawPart("f_eye_l", "3024.dat", c_w, (-s(1), -200, s(1.5)), yaw=0).to_dict(),
                LDrawPart("f_eye_r", "3024.dat", c_w, (s(1), -200, s(1.5)), yaw=0).to_dict(),
            ],
            # Nivel 12 (Y=-208): Cejas y frente lisa (Plate 2x4 + Cejas)
            [
                LDrawPart("f_forehead", "2431.dat", c_skin, (0, -208, s(0.5)), yaw=0).to_dict(),
                LDrawPart("f_brow_l", "3023.dat", c_hair, (-s(1), -208, s(1.5)), yaw=0).to_dict(),
                LDrawPart("f_brow_r", "3023.dat", c_hair, (s(1), -208, s(1.5)), yaw=0).to_dict(),
            ]
        ]
        return {"name": "05-rostro-facciones.ldr", "description": "Facciones faciales esculpidas", "steps": steps}

    # 6. Cabello y Bóveda Craneal (Y=-232 a Y=-258)
    def _build_hair_section(self) -> Dict[str, Any]:
        c_hair = self.palette["hair_main"]
        c_acc = self.palette["hair_accent"]
        steps = [
            # Nivel 13 (Y=-232): Bóveda craneal (Brick 2x4 en X=0, Z=-1)
            [
                LDrawPart("h_cr_c", "3001.dat", c_hair, (0, -232, -s(1)), yaw=0).to_dict(),
                # Caída del cabello en nuca (Curved Slopes en Z=-3)
                LDrawPart("h_nape", "11477.dat", c_hair, (0, -232, -s(3)), yaw=0).to_dict(),
            ],
            # Nivel 14 (Y=-240): Tupé y mechones frontales (Curved Slopes 3x1 en Z=1)
            [
                LDrawPart("h_quiff_c", "50950.dat", c_acc, (0, -240, s(1)), yaw=180).to_dict(),
                LDrawPart("h_quiff_l", "50950.dat", c_acc, (-s(1), -240, s(1)), yaw=180).to_dict(),
                LDrawPart("h_quiff_r", "50950.dat", c_acc, (s(1), -240, s(1)), yaw=180).to_dict(),
                # Coronilla superior
                LDrawPart("h_top_c", "11477.dat", c_hair, (0, -248, 0), yaw=180).to_dict(),
            ]
        ]
        return {"name": "06-cabello-craneo.ldr", "description": "Bóveda craneal y peinado", "steps": steps}


def generate_high_fidelity_plan(slug: str, brief_data: Dict[str, Any], output_path: Path) -> Dict[str, Any]:
    engine = HighFidelitySculptEngine(slug, brief_data)
    plan = engine.generate_plan()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return plan
