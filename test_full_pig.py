import json
import subprocess
import os
import sys

def build_full_pig():
    # Write complete MPD
    # Layers:
    # Hoof base at Y = 40 (bottom at Y = 48)
    # Leg ankle at Y = 16 (bottom at 40)
    # Leg thigh at Y = -8 (bottom at 16)
    # Underbelly plate at Y = -16 (bottom at -8, top at -16)
    # Torso brick layer 1 at Y = -40 (bottom at -16, top at -40)
    # Torso brick layer 2 at Y = -64 (bottom at -40, top at -64)
    # Torso dorsal plate at Y = -72 (bottom at -64, top at -72)
    # Dorsal tiles at Y = -80 (bottom at -72, top at -80)
    
    mpd_lines = []
    
    # 01_spine_torso
    torso_lines = [
        "0 FILE 01_spine_torso.ldr",
        "0 Torso Subassembly",
        "0 Name: 01_spine_torso.ldr",
        "0 Author: Antigravity",
        # Underbelly Plate 4x6 at Y = -16 (Z in [-60, 60], X in [-40, 40])
        "1 29 0 -16 0 0 0 1 0 1 0 -1 0 0 3032.dat"
    ]
    
    # Torso brick layer 1 (Y = -40, Z slices from -50 to +50):
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        # Center brick 1x2 (X: [-20, 20])
        torso_lines.append(f"1 {c} 0 -40 {z} 1 0 0 0 1 0 0 0 1 3004.dat")
        # Left flank brick 1x1 (X: [-40, -20])
        torso_lines.append(f"1 {c} -30 -40 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        # Right flank brick 1x1 (X: [20, 40])
        torso_lines.append(f"1 {c} 30 -40 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        
    # Torso brick layer 2 (Y = -64, Z slices from -50 to +50):
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        torso_lines.append(f"1 {c} 0 -64 {z} 1 0 0 0 1 0 0 0 1 3004.dat")
        torso_lines.append(f"1 {c} -30 -64 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        torso_lines.append(f"1 {c} 30 -64 {z} 1 0 0 0 1 0 0 0 1 3005.dat")
        
    # Dorsal plate 4x6 at Y = -72:
    torso_lines.append("1 29 0 -72 0 0 0 1 0 1 0 -1 0 0 3032.dat")
    
    # Dorsal roof tiles at Y = -80 (Tiles 1x2 and 1x1):
    for z in [-50, -30, -10, 10, 30, 50]:
        c = 5 if z == -10 else 29
        # Center tile 1x2 (X [-20, 20], Z [z-10, z+10])
        torso_lines.append(f"1 {c} 0 -80 {z} 1 0 0 0 1 0 0 0 1 3069b.dat")
        # Left tile 1x1 (X [-40, -20], Z [z-10, z+10])
        torso_lines.append(f"1 {c} -30 -80 {z} 1 0 0 0 1 0 0 0 1 3070b.dat")
        # Right tile 1x1 (X [20, 40], Z [z-10, z+10])
        torso_lines.append(f"1 {c} 30 -80 {z} 1 0 0 0 1 0 0 0 1 3070b.dat")
        
    torso_lines.append("0 NOFILE")
    mpd_lines.extend(torso_lines)
    
    # Submodels 04, 05 (Forelegs at Z = -40, X = -30 and +30)
    # Submodels 06, 07 (Hindlegs at Z = 40, X = -30 and +30)
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
            # Sole plate 1x2 at Y = 40 (X: [x-10, x+10] if ROT_Y_90 -> X [-10, 10], Z [-20, 20])
            # At ROT_Y_90: Plate 1x2 (3023) has X [x-10, x+10], Z [z-20, z+20]
            f"1 308 {x} 40 {z} 0 0 1 0 1 0 -1 0 0 3023.dat",
            # Ankle brick 1x2 at Y = 16 (X [x-10, x+10], Z [z-20, z+20])
            f"1 29 {x} 16 {z} 0 0 1 0 1 0 -1 0 0 3004.dat",
            # Thigh brick 1x2 at Y = -8 (X [x-10, x+10], Z [z-20, z+20])
            f"1 29 {x} -8 {z} 0 0 1 0 1 0 -1 0 0 3004.dat",
            "0 NOFILE"
        ]
        mpd_lines.extend(lines)
        
    # Head Submodel 02 at Z < -60 (extends to -120):
    head_lines = [
        "0 FILE 02_cranial_head.ldr",
        "0 Head Subassembly",
        "0 Name: 02_cranial_head.ldr",
        "0 Author: Antigravity",
        # Neck plate 2x2 at Y = -24, Z = -80 (X [-20, 20], Z [-80, -60])
        # Connects to underbelly plate (Y=-16) and torso front (Z=-60)
        "1 29 0 -24 -80 1 0 0 0 1 0 0 0 1 3022.dat",
        # Lower cranium brick 2x2 at Y = -48, Z = -80 (X [-20, 20], Z [-80, -60])
        "1 29 0 -48 -80 1 0 0 0 1 0 0 0 1 3003.dat",
        # Upper cranium brick 2x2 at Y = -72, Z = -80 (X [-20, 20], Z [-80, -60])
        "1 29 0 -72 -80 1 0 0 0 1 0 0 0 1 3003.dat",
        # Cheeks: Plate 1x2 Pink on Left & Right at Y = -48:
        # Left cheek plate 1x2 at X = -30, Z = -80 (X [-40, -20], Z [-110, -50] if ROT_Y_90):
        "1 29 -30 -48 -80 0 0 1 0 1 0 -1 0 0 3023.dat",
        "1 29 30 -48 -80 0 0 1 0 1 0 -1 0 0 3023.dat",
        # Eyes: Black round tiles at Y = -56, Z = -80:
        "1 0 -30 -56 -80 1 0 0 0 1 0 0 0 1 98138.dat",
        "1 0 30 -56 -80 1 0 0 0 1 0 0 0 1 98138.dat",
        # Brow: Curved slope 2x2 Pink at Y = -88, Z = -80:
        "1 29 0 -88 -80 1 0 0 0 1 0 0 0 1 15068.dat",
        # Snout (Z in [-110, -80], center Z = -110):
        # Snout brick 1x2 Dark Pink at Y = -48, Z = -110 (X [-20, 20], Z [-110, -80])
        "1 5 0 -48 -110 1 0 0 0 1 0 0 0 1 3004.dat",
        # Snout top plate 1x2 Dark Pink at Y = -56, Z = -110
        "1 5 0 -56 -110 1 0 0 0 1 0 0 0 1 3023.dat",
        # Nostrils: 2 Dark Pink cheese slopes at Y = -64, Z = -110
        "1 5 -10 -64 -110 1 0 0 0 1 0 0 0 1 54200.dat",
        "1 5 10 -64 -110 1 0 0 0 1 0 0 0 1 54200.dat",
        "0 NOFILE"
    ]
    mpd_lines.extend(head_lines)
    
    # Tail Submodel 08 at Z > +60:
    tail_lines = [
        "0 FILE 08_caudal_tail.ldr",
        "0 Tail Subassembly",
        "0 Name: 08_caudal_tail.ldr",
        "0 Author: Antigravity",
        # Plate 1x1 with Clip at Y = -40, Z = 70 (X [-10, 10], Z [60, 80])
        "1 29 0 -40 70 0 0 1 0 1 0 -1 0 0 4085c.dat",
        # Spiral curly tail horn at Y = -40, Z = 90
        "1 29 0 -40 90 0 0 1 0 1 0 -1 0 0 89522.dat",
        "0 NOFILE"
    ]
    mpd_lines.extend(tail_lines)
    
    # Master Assembly
    master_lines = [
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
    
    full_mpd = master_lines + mpd_lines
    with open("output/pig_sculpture/pig_sculpture.mpd", "w") as f:
        f.write("\n".join(full_mpd) + "\n")
        
    print(f"Generated MPD with {len(full_mpd)} lines")

build_full_pig()
