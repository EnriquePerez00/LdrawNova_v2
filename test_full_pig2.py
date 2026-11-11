import json, subprocess, os

def generate_mpd():
    mpd_lines = []
    
    # 01_spine_torso
    torso = [
        "0 FILE 01_spine_torso.ldr",
        "0 Torso Subassembly",
        "0 Name: 01_spine_torso.ldr",
        "0 Author: Antigravity",
        # Underbelly Plate 4x6 at Y = -8:
        "1 29 0 -8 0 0 0 1 0 1 0 -1 0 0 3032.dat"
    ]
    # Brick layer 1 at Y = -32:
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        torso.append(f"1 {c} 0 -32 {z} 1 0 0 0 1 0 0 0 1 3004.dat")
        torso.append(f"1 {c} -30 -32 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        torso.append(f"1 {c} 30 -32 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        
    # Brick layer 2 at Y = -56:
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        torso.append(f"1 {c} 0 -56 {z} 1 0 0 0 1 0 0 0 1 3004.dat")
        torso.append(f"1 {c} -30 -56 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        torso.append(f"1 {c} 30 -56 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        
    # Dorsal plate 4x6 at Y = -64:
    torso.append("1 29 0 -64 0 0 0 1 0 1 0 -1 0 0 3032.dat")
    
    # Dorsal tiles at Y = -72:
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        torso.append(f"1 {c} 0 -72 {z} 1 0 0 0 1 0 0 0 1 3069b.dat")
        torso.append(f"1 {c} -30 -72 {z} 1 0 0 0 1 0 0 0 1 3070b.dat")
        torso.append(f"1 {c} 30 -72 {z} 1 0 0 0 1 0 0 0 1 3070b.dat")
        
    torso.append("0 NOFILE")
    mpd_lines.extend(torso)
    
    # Legs (4 limbs)
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
            f"1 308 {x} 48 {z} 0 0 1 0 1 0 -1 0 0 3023.dat",
            f"1 29 {x} 24 {z} 0 0 1 0 1 0 -1 0 0 3004.dat",
            f"1 29 {x} 0 {z} 0 0 1 0 1 0 -1 0 0 3004.dat",
            "0 NOFILE"
        ]
        mpd_lines.extend(lines)
        
    # Head at Z = -80 (front of torso is at Z = -60):
    # Neck plate: Y = -16, Z = -70 (spans Z [-80, -60], connects torso front and head base)
    # Lower cranium brick 2x2: Y = -40, Z = -80 (spans Z [-100, -60], Y [-40, -16])
    # Upper cranium brick 2x2: Y = -64, Z = -80 (spans Z [-100, -60], Y [-64, -40])
    # Brow curved slope 2x2: Y = -80, Z = -80 (spans Y [-80, -64])
    # Cheeks: Plate 1x2 at X = -30, 30 at Y = -40, Z = -80
    # Snout at Z = -110:
    # Snout brick 1x2: Y = -40, Z = -110 (spans Z [-120, -100], Y [-40, -16])
    # Snout plate 1x2: Y = -48, Z = -110
    # Nostrils: Cheese slopes at Y = -56, Z = -110
    head = [
        "0 FILE 02_cranial_head.ldr",
        "0 Head Subassembly",
        "0 Name: 02_cranial_head.ldr",
        "0 Author: Antigravity",
        "1 29 0 -8 -80 1 0 0 0 1 0 0 0 1 3022.dat",
        "1 29 0 -32 -80 1 0 0 0 1 0 0 0 1 3003.dat",
        "1 29 0 -56 -80 1 0 0 0 1 0 0 0 1 3003.dat",
        "1 29 -30 -32 -80 0 0 1 0 1 0 -1 0 0 3023.dat",
        "1 29 30 -32 -80 0 0 1 0 1 0 -1 0 0 3023.dat",
        "1 0 -30 -40 -80 1 0 0 0 1 0 0 0 1 98138.dat",
        "1 0 30 -40 -80 1 0 0 0 1 0 0 0 1 98138.dat",
        "1 29 0 -72 -80 1 0 0 0 1 0 0 0 1 15068.dat",
        "1 5 0 -32 -110 1 0 0 0 1 0 0 0 1 3004.dat",
        "1 5 0 -40 -110 1 0 0 0 1 0 0 0 1 3023.dat",
        "1 5 -10 -48 -110 1 0 0 0 1 0 0 0 1 54200.dat",
        "1 5 10 -48 -110 1 0 0 0 1 0 0 0 1 54200.dat",
        "0 NOFILE"
    ]
    mpd_lines.extend(head)
    
    # Tail at Z = 70:
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
    
    # Master
    master = [
        "0 FILE pig_sculpture.ldr",
        "0 Master Pig Sculpture",
        "0 Name: pig_sculpture.ldr",
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
    with open("output/pig_sculpture/pig_sculpture.mpd", "w") as f:
        f.write("\n".join(full_mpd) + "\n")

generate_mpd()
