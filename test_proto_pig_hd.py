import json
import subprocess
import os
import sys

def build_hd_pig():
    mpd_lines = []
    part_count = 0

    # We will build submodels:
    # 01_spine_torso.ldr
    # 02_cranial_head.ldr
    # 04_forelimbs_left.ldr
    # 05_forelimbs_right.ldr
    # 06_hindlimbs_left.ldr
    # 07_hindlimbs_right.ldr
    # 08_caudal_tail.ldr

    # 1. TORSO (01_spine_torso.ldr)
    torso = [
        "0 FILE 01_spine_torso.ldr",
        "0 Torso Subassembly HD",
        "0 Name: 01_spine_torso.ldr",
        "0 Author: Antigravity"
    ]
    
    # Underbelly plates at Y = -8:
    # Main platform Plate 4x6 at Y = -8:
    torso.append("1 29 0 -8 0 0 0 1 0 1 0 -1 0 0 3032.dat")
    
    # Flank inverted curved slopes 24201 (Slope 2x1 Curved Inverted) along belly edges at Y = -8:
    # Left belly curve (X = -30, Z in [-40, -20, 20, 40]):
    # Note: 24201 has size [20, 19.9, 40]
    
    # Brick Layer 1 at Y = -32 (Z slices: -50, -30, -10, 10, 30, 50):
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        # Center brick 1x2 (X in [-20, 20])
        torso.append(f"1 {c} 0 -32 {z} 1 0 0 0 1 0 0 0 1 3004.dat")
        # Left flank brick 1x1 (X in [-40, -20])
        torso.append(f"1 {c} -30 -32 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        # Right flank brick 1x1 (X in [20, 40])
        torso.append(f"1 {c} 30 -32 {z} 1 0 0 0 1 0 0 0 1 3005.dat")

    # Brick Layer 2 at Y = -56 (Z slices: -50, -30, -10, 10, 30, 50):
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        torso.append(f"1 {c} 0 -56 {z} 1 0 0 0 1 0 0 0 1 3004.dat")
        torso.append(f"1 {c} -30 -56 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        torso.append(f"1 {c} 30 -56 {z} 1 0 0 0 1 0 0 0 1 3005.dat")

    # Dorsal plate 4x6 at Y = -64:
    torso.append("1 29 0 -64 0 0 0 1 0 1 0 -1 0 0 3032.dat")

    # Dorsal Arched Roof Layer at Y = -72 & -80:
    # Central spine tiles 1x2 (3069b) along Z:
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        torso.append(f"1 {c} 0 -72 {z} 1 0 0 0 1 0 0 0 1 3069b.dat")

    # Lateral Curved Slopes 2x1 (11477) sloping down to the sides:
    # Left flank top curved slopes at X = -30 (ROT_Y_90 curves down to -X):
    # Right flank top curved slopes at X = +30 (ROT_Y_270 curves down to +X):
    for z in [-40, -20, 20, 40]:
        torso.append(f"1 29 -30 -64 {z} 0 0 1 0 1 0 -1 0 0 11477.dat")
        torso.append(f"1 29 30 -64 {z} 0 0 -1 0 1 0 1 0 0 11477.dat")

    # Saddle accent curved slopes at Z = 0:
    torso.append("1 5 -30 -64 0 0 0 1 0 1 0 -1 0 0 11477.dat")
    torso.append("1 5 30 -64 0 0 0 -1 0 1 0 1 0 0 11477.dat")

    torso.append("0 NOFILE")
    mpd_lines.extend(torso)

    # 2. LIMBS (4 limbs)
    leg_defs = [
        ("04_forelimbs_left.ldr", -30.0, -40.0),
        ("05_forelimbs_right.ldr", 30.0, -40.0),
        ("06_hindlimbs_left.ldr", -30.0, 40.0),
        ("07_hindlimbs_right.ldr", 30.0, 40.0)
    ]
    for sub, x, z in leg_defs:
        lines = [
            f"0 FILE {sub}",
            f"0 Leg {sub}",
            f"0 Name: {sub}",
            "0 Author: Antigravity",
            # Sole plate 1x2 Dark Brown at Y = 48:
            f"1 308 {x} 48 {z} 0 0 1 0 1 0 -1 0 0 3023.dat",
            # Front hoof toe cheese slope 54200 forward (Z - 10):
            f"1 308 {x} 40 {z - 10} 1 0 0 0 1 0 0 0 1 54200.dat",
            # Rear hoof heel cheese slope 54200 backward (Z + 10):
            f"1 308 {x} 40 {z + 10} -1 0 0 0 1 0 0 0 -1 54200.dat",
            # Lower ankle brick 1x2 at Y = 24:
            f"1 29 {x} 24 {z} 0 0 1 0 1 0 -1 0 0 3004.dat",
            # Lateral ankle curved slopes 11477 at Y = 32:
            # Upper thigh brick 1x2 at Y = 0:
            f"1 29 {x} 0 {z} 0 0 1 0 1 0 -1 0 0 3004.dat",
            "0 NOFILE"
        ]
        mpd_lines.extend(lines)

    # 3. CRANIAL HEAD (02_cranial_head.ldr)
    head = [
        "0 FILE 02_cranial_head.ldr",
        "0 Head Subassembly HD",
        "0 Name: 02_cranial_head.ldr",
        "0 Author: Antigravity",
        # Neck plate 2x2 at Y = -8, Z = -80:
        "1 29 0 -8 -80 1 0 0 0 1 0 0 0 1 3022.dat",
        # Lower cranium core brick 2x2 at Y = -32, Z = -80:
        "1 29 0 -32 -80 1 0 0 0 1 0 0 0 1 3003.dat",
        # Upper cranium core brick 2x2 at Y = -56, Z = -80:
        "1 29 0 -56 -80 1 0 0 0 1 0 0 0 1 3003.dat",
        # Cheeks: Curved slopes 2x1 11477 on Left & Right at Y = -40, Z = -80:
        "1 29 -30 -32 -80 0 0 1 0 1 0 -1 0 0 3023.dat",
        "1 29 30 -32 -80 0 0 1 0 1 0 -1 0 0 3023.dat",
        # Expressive Black Round Eye Tiles 1x1:
        "1 0 -30 -40 -80 1 0 0 0 1 0 0 0 1 98138.dat",
        "1 0 30 -40 -80 1 0 0 0 1 0 0 0 1 98138.dat",
        # Curved Forehead Brow 2x2 (15068) at Y = -72, Z = -80:
        "1 29 0 -72 -80 1 0 0 0 1 0 0 0 1 15068.dat",
        # Ears: Folded triangular cheese slopes at Y = -80, Z = -70:
        "1 29 -20 -80 -70 0 0 -1 0 1 0 1 0 0 54200.dat",
        "1 29 20 -80 -70 0 0 1 0 1 0 -1 0 0 54200.dat",
        # Snout (Z = -110):
        # Snout core brick 1x2 Dark Pink:
        "1 5 0 -32 -110 1 0 0 0 1 0 0 0 1 3004.dat",
        # Snout top plate 1x2 Dark Pink:
        "1 5 0 -40 -110 1 0 0 0 1 0 0 0 1 3023.dat",
        # Nostrils: Dark Pink cheese slopes:
        "1 5 -10 -48 -110 1 0 0 0 1 0 0 0 1 54200.dat",
        "1 5 10 -48 -110 1 0 0 0 1 0 0 0 1 54200.dat",
        # Snout lower curved slope / chin (Plate 1x2 + curved slope 11477):
        "1 5 0 -24 -110 1 0 0 0 1 0 0 0 1 3023.dat",
        "0 NOFILE"
    ]
    mpd_lines.extend(head)

    # 4. TAIL (08_caudal_tail.ldr)
    tail = [
        "0 FILE 08_caudal_tail.ldr",
        "0 Tail Subassembly",
        "0 Name: 08_caudal_tail.ldr",
        "0 Author: Antigravity",
        "1 29 0 -32 70 0 0 1 0 1 0 -1 0 0 4085c.dat",
        "1 29 0 -32 90 0 0 1 0 1 0 -1 0 0 89522.dat",
        "0 NOFILE"
    ]
    mpd_lines.extend(tail)

    # Master Section
    master = [
        "0 FILE pig_sculpture_hd.ldr",
        "0 Master Pig Sculpture HD",
        "0 Name: pig_sculpture_hd.ldr",
        "0 Author: Antigravity",
        "1 16 0 0 0 1 0 0 0 1 0 0 0 1 01_spine_torso.ldr",
        "1 16 0 0 0 1 0 0 0 1 0 0 0 1 02_cranial_head.ldr",
        "1 16 0 0 0 1 0 0 0 1 0 0 0 1 04_forelimbs_left.ldr",
        "1 16 0 0 0 1 0 0 0 1 0 0 0 1 05_forelimbs_right.ldr",
        "1 16 0 0 0 1 0 0 0 1 0 0 0 1 06_hindlimbs_left.ldr",
        "1 16 0 0 0 1 0 0 0 1 0 0 0 1 07_hindlimbs_right.ldr",
        "1 16 0 0 0 1 0 0 0 1 0 0 0 1 08_caudal_tail.ldr",
        "0 NOFILE"
    ]

    full_mpd = master + mpd_lines
    with open("output/pig_sculpture/pig_sculpture_hd.mpd", "w") as f:
        f.write("\r\n".join(full_mpd) + "\r\n")

build_hd_pig()
