import json
import time
import os
import subprocess

def create_hd_model():
    t0 = time.perf_counter()
    
    # Grid constants in LDU
    # 1 stud = 20 LDU in X and Z
    # 1 plate = 8 LDU in Y (-Y is UP)
    # 1 brick = 24 LDU in Y
    
    # Colors:
    # 15: White
    # 71: Light Bluish Gray
    # 72: Dark Bluish Gray
    # 320: Dark Red
    # 19: Tan
    # 47: Trans-Clear
    # 38: Trans-Neon Orange
    # 0: Black
    # 179: Flat Silver
    
    parts = []
    
    def add_part(part_id, color, x, y, z, rot_matrix=[[1,0,0],[0,1,0],[0,0,1]]):
        m = rot_matrix
        m_flat = [m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2], m[2][0], m[2][1], m[2][2]]
        parts.append({
            "part": part_id,
            "colour": color,
            "transform": {
                "position": [round(x, 2), round(y, 2), round(z, 2)],
                "rotation": m_flat
            }
        })

    # Rotation helpers:
    ROT_I = [[1,0,0],[0,1,0],[0,0,1]]
    ROT_Y_180 = [[-1,0,0],[0,1,0],[0,0,-1]]
    ROT_Y_90 = [[0,0,1],[0,1,0],[-1,0,0]]
    ROT_Y_270 = [[0,0,-1],[0,1,0],[1,0,0]]
    ROT_X_90 = [[1,0,0],[0,0,-1],[0,1,0]]
    # For Bar 4L (30374) pointing forward (-Z)
    ROT_BAR_FWD = [[1,0,0],[0,0,1],[0,-1,0]]
    
    # -------------------------------------------------------------
    # 1. CENTRAL CHASSIS & LOWER SPINE (Y = 0 to Y = 24)
    # Length Z from +160 to -160 (320 LDU = 16 studs)
    # -------------------------------------------------------------
    # Base plates layer (Y = 0)
    for z in range(-120, 160, 40):
        # 2x2 plate at x=0
        add_part("3022.dat", 71, 0, 0, z) # Light bluish gray chassis plate
    
    # Lower keel plates
    for z in range(-80, 140, 40):
        add_part("3022.dat", 72, 0, 8, z)
        add_part("3024.dat", 72, 0, 16, z)
    
    # Landing gear skids (Ground Truth shows retractable/removable skids)
    add_part("44728.dat", 72, 0, 24, -80, ROT_I)
    add_part("3024.dat", 72, 0, 32, -80)
    add_part("2412b.dat", 72, 0, 40, -80)
    
    # -------------------------------------------------------------
    # 2. NOSE CONE & FORWARD FUSELAGE (Z: -280 to -120)
    # Matching GT: SNOT tapered nose with Tan and Dark Red side accents
    # -------------------------------------------------------------
    # Nose tip (Z = -270)
    add_part("4589.dat", 71, 0, -8, -270, ROT_X_90) # Nose sensor tip
    add_part("3069b.dat", 71, 0, -16, -250) # Nose tip slope/tile
    add_part("54200.dat", 71, -10, -16, -230) # 1x1 slope port
    add_part("54200.dat", 71, 10, -16, -230) # 1x1 slope stbd
    
    # Forward nose taper (Z = -240 to -160)
    for i, z in enumerate(range(-230, -150, 20)):
        # Top plates/slopes
        add_part("3024.dat", 15, 0, -8, z) # White center
        # Yellowish-tan accent stripe from GT (Red 5 distinct marking)
        if i in [1, 2]:
            add_part("3069b.dat", 19, 0, -16, z) # Tan accent tile!
        else:
            add_part("3069b.dat", 15, 0, -16, z) # White tile
            
        # Port & Starboard red stripes (GT Red Five markings)
        add_part("3024.dat", 320, -20, -8, z) # Dark red port
        add_part("3024.dat", 320, 20, -8, z) # Dark red stbd
        add_part("3069b.dat", 320, -20, -16, z) # Dark red tile port
        add_part("3069b.dat", 320, 20, -16, z) # Dark red tile stbd
        
        # Lower nose taper
        add_part("3024.dat", 15, 0, 0, z)
        add_part("54200.dat", 71, -10, 8, z)
        add_part("54200.dat", 71, 10, 8, z)

    # -------------------------------------------------------------
    # 3. COCKPIT, CANOPY & INTERIOR (Z: -140 to -40)
    # -------------------------------------------------------------
    # Cockpit tub interior
    add_part("3022.dat", 72, 0, -8, -120)
    add_part("3022.dat", 72, 0, -8, -80)
    add_part("3069b.dat", 0, 0, -16, -110) # Control console
    add_part("4079.dat", 72, 0, -24, -80)  # Pilot seat
    
    # Trans-clear Canopy structure (GT shows faceted canopy)
    # Windscreen slope canopy
    add_part("30372.dat", 47, 0, -32, -90) # Cockpit canopy 4x4x1 2/3
    # Cockpit frame tiles
    add_part("3069b.dat", 71, -20, -24, -60)
    add_part("3069b.dat", 71, 20, -24, -60)
    
    # -------------------------------------------------------------
    # 4. ASTROMECH DROID BAY (R2-D2) (Z: -40 to 0)
    # Directly behind cockpit as shown in GT
    # -------------------------------------------------------------
    add_part("3022.dat", 15, 0, -8, -20)
    add_part("3024.dat", 72, -10, -16, -20)
    add_part("3024.dat", 72, 10, -16, -20)
    add_part("30367b.dat", 15, 0, -24, -20) # R2-D2 Dome head!
    add_part("2412b.dat", 71, 0, -16, 0) # Grille tile behind droid
    
    # -------------------------------------------------------------
    # 5. REAR FUSELAGE & GREEBLING TRENCH (Z: 0 to 140)
    # Heavy mechanical greebling (pipes, grilles, power generator)
    # -------------------------------------------------------------
    for z in range(20, 140, 20):
        # Center core
        add_part("3004.dat", 15, 0, -16, z) # 1x2 brick
        add_part("3022.dat", 72, 0, -24, z) # Plate
        # Greebles: alternating grilles, clips, round tiles
        if z % 40 == 0:
            add_part("2412b.dat", 72, 0, -32, z) # Radiator grille
            add_part("4599b.dat", 71, -10, -32, z) # Tap / pipe
            add_part("4599b.dat", 71, 10, -32, z)
        else:
            add_part("98138.dat", 179, 0, -32, z) # Flat silver generator dial
            add_part("2877.dat", 72, -10, -24, z) # Grille brick port
            add_part("2877.dat", 72, 10, -24, z) # Grille brick stbd

    # Rear engine exhaust bulkhead (Z = 140 to 160)
    add_part("3022.dat", 72, 0, -8, 140)
    add_part("3022.dat", 72, 0, -16, 140)
    add_part("4032.dat", 72, 0, -12, 160, ROT_X_90) # Rear central thrust nozzle
    
    # -------------------------------------------------------------
    # 6. FOUR WINGS (S-FOILS) IN X-FORMATION
    # Top-Port, Bottom-Port, Top-Stbd, Bottom-Stbd
    # High definition: S-Foil panels, red 5 identification bars,
    # SNOT leading edges, laser cannons with flash suppressors.
    # -------------------------------------------------------------
    # S-Foil configurations:
    # 4 wings:
    #   Top-Port:    X < 0, Y = -16 (elevated S-foil)
    #   Bottom-Port: X < 0, Y = 0   (lower S-foil)
    #   Top-Stbd:    X > 0, Y = -16
    #   Bottom-Stbd: X > 0, Y = 0
    
    wing_configs = [
        {"name": "top_port",    "sx": -1, "y": -16, "red_bars": 5},
        {"name": "bottom_port", "sx": -1, "y": 8,   "red_bars": 5},
        {"name": "top_stbd",    "sx": 1,  "y": -16, "red_bars": 5},
        {"name": "bottom_stbd", "sx": 1,  "y": 8,   "red_bars": 5},
    ]
    
    for cfg in wing_configs:
        sx = cfg["sx"]
        wy = cfg["y"]
        
        # Inboard wing roots (connect to fuselage core)
        add_part("3022.dat", 71, sx * 40, wy, 40)
        add_part("3022.dat", 71, sx * 40, wy, 80)
        add_part("3022.dat", 71, sx * 40, wy, 120)
        
        # Mid wing plate layers (X from 60 to 140)
        # Main wing span plates (2x4, 2x6, 2x8)
        for x_stud in range(3, 8):
            x_pos = sx * x_stud * 20
            # Wings sweep forward: Z from 0 to 140
            for z_pos in [40, 80, 120]:
                add_part("3024.dat", 15, x_pos, wy, z_pos)
                
        # Leading edge slopes and smooth tiles (GT smooth finish)
        for x_stud in range(3, 8):
            x_pos = sx * x_stud * 20
            add_part("3069b.dat", 15, x_pos, wy - 8, 40)
            
        # Distinctive Red Five Wing Markings (5 red stripes on outer wing surface!)
        # As clearly seen in the GT isometric view!
        for stripe_idx in range(5):
            stripe_z = 60 + stripe_idx * 16
            add_part("3024.dat", 320, sx * 120, wy - 8, stripe_z) # Red 5 stripe!
            add_part("3069b.dat", 320, sx * 140, wy - 8, stripe_z) # Outer red accent
            
        # Greebling on wings: cooling grilles and panel joints
        add_part("2412b.dat", 71, sx * 80, wy - 8, 80)
        add_part("2412b.dat", 71, sx * 80, wy - 8, 100)
        add_part("98138.dat", 72, sx * 100, wy - 8, 80)

        # ---------------------------------------------------------
        # 7. ENGINE NACELLES (4 HIGH-DETAIL TURBINES)
        # Mounted at wing roots (sx * 40, wy, Z: 0 to 140)
        # Intake fan, bypass cowling, rear exhaust nozzle
        # ---------------------------------------------------------
        # Front intake scoop (half-cylinder cowl matching GT!)
        nx = sx * 40
        ny = wy - 12
        add_part("43898.dat", 71, nx, ny, 10, ROT_X_90) # Round dish intake
        add_part("3941.dat", 15, nx, ny, 30)             # Round 2x2 brick cowl
        add_part("3941.dat", 15, nx, ny, 50)             # Cylinder mid-cowl
        add_part("553b.dat" if False else "30367b.dat", 71, nx, ny, 70) # Engine ribbed transition
        add_part("3941.dat", 72, nx, ny, 90)             # Dark gray generator segment
        add_part("3941.dat", 71, nx, ny, 110)            # Rear nacelle sleeve
        add_part("4032.dat", 72, nx, ny, 130)            # Turbine rear ring
        add_part("4589.dat", 72, nx, ny, 140, ROT_X_90)  # Exhaust nozzle cone
        add_part("3941.dat", 38, nx, ny, 150)            # Trans-Orange thrust glow!
        
        # ---------------------------------------------------------
        # 8. LASER CANNONS (4 T-65B WINGTIP CANNONS)
        # Positioned at wingtip (sx * 160, wy, Z from -100 to 140)
        # Long barrel, flash suppressor, generator sleeve
        # ---------------------------------------------------------
        lx = sx * 160
        ly = wy
        # Cannon mount block on wingtip
        add_part("3024.dat", 71, lx, ly, 100)
        add_part("3024.dat", 71, lx, ly, 60)
        add_part("3024.dat", 71, lx, ly, 20)
        
        # Cannon rear generator cylinder
        add_part("3941.dat", 71, lx, ly - 4, 120)
        add_part("4589.dat", 72, lx, ly - 4, 140, ROT_X_90) # Rear emitter cap
        
        # Cannon mid sleeve & flash coils
        add_part("3941.dat", 71, lx, ly - 4, 80)
        add_part("4032.dat", 72, lx, ly - 4, 50)
        add_part("4032.dat", 71, lx, ly - 4, 30)
        
        # Forward long barrel (Bar 4L segments pointing forward -Z)
        add_part("30374.dat", 71, lx, ly - 4, 0, ROT_BAR_FWD)
        add_part("30374.dat", 71, lx, ly - 4, -40, ROT_BAR_FWD)
        add_part("4032.dat", 72, lx, ly - 4, -60) # Muzzle brake ring
        add_part("30374.dat", 71, lx, ly - 4, -90, ROT_BAR_FWD) # Front needle
        add_part("4589.dat", 71, lx, ly - 4, -130, ROT_X_90) # Tip suppressor

    t1 = time.perf_counter()
    gen_time = t1 - t0
    
    plan = {
        "profile": "assembly",
        "description": "Incom T-65B X-Wing Starfighter (Red Five) - High Definition 500-Part Scale",
        "parts": parts
    }
    
    return plan, gen_time

if __name__ == "__main__":
    plan, gen_time = create_hd_model()
    out_dir = "output/x-wing-red-five-hd-500"
    os.makedirs(out_dir, exist_ok=True)
    plan_path = os.path.join(out_dir, "x_wing_hd_clean.plan.json")
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"Plan created with {len(plan['parts'])} parts in {gen_time*1000:.2f} ms")
