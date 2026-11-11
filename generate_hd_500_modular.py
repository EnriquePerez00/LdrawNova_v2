import json
import time
import os
import subprocess

def build_hd_plan():
    t0 = time.perf_counter()

    # Matrix helpers
    # LDraw standard coordinates:
    # +X: Right, +Y: Down, +Z: Backward (-Z: Forward towards nose)
    ROT_I = [1,0,0, 0,1,0, 0,0,1]
    ROT_Y_180 = [-1,0,0, 0,1,0, 0,0,-1]
    ROT_X_90 = [1,0,0, 0,0,-1, 0,1,0]
    ROT_BAR_FWD = [1,0,0, 0,0,1, 0,-1,0]

    # Sections will contain submodels
    sections = []

    # -------------------------------------------------------------
    # 01: SPINE & LOWER CHASSIS
    # -------------------------------------------------------------
    steps_spine = []
    # Chassis bottom plates (Dark Bluish Gray 72 & Light Bluish Gray 71)
    chassis_parts = []
    # Base plates
    for z in range(-120, 160, 40):
        chassis_parts.append({
            "id": f"chassis_base_{z}",
            "ref": "3022.dat", # Plate 2x2
            "colour": 71,
            "at": [0, 0, z]
        })
    for z in range(-80, 140, 40):
        chassis_parts.append({
            "id": f"chassis_keel_{z}",
            "ref": "3022.dat",
            "colour": 72,
            "at": [0, 8, z]
        })
        chassis_parts.append({
            "id": f"chassis_keel_tile_{z}",
            "ref": "3024.dat",
            "colour": 72,
            "at": [0, 16, z]
        })
    # Front landing gear skid (removable / display)
    chassis_parts.append({"id": "skid_bracket", "ref": "44728.dat", "colour": 72, "at": [0, 24, -80]})
    chassis_parts.append({"id": "skid_plate", "ref": "3024.dat", "colour": 72, "at": [0, 32, -80]})
    chassis_parts.append({"id": "skid_foot", "ref": "2412b.dat", "colour": 72, "at": [0, 40, -80]})

    steps_spine.append(chassis_parts)
    sections.append({
        "name": "01_spine_chassis.ldr",
        "description": "Heavy Central Spine and Lower Chassis Keel",
        "steps": steps_spine
    })

    # -------------------------------------------------------------
    # 02: NOSE & FORWARD FUSELAGE
    # High-detail Red Five markings (Dark Red stripes & Tan patch from GT)
    # -------------------------------------------------------------
    steps_nose = []
    nose_parts = []
    # Tip sensor
    nose_parts.append({"id": "nose_sensor", "ref": "4589.dat", "colour": 71, "at": [0, -8, -270], "matrix": ROT_X_90})
    nose_parts.append({"id": "nose_cap_tile", "ref": "3069b.dat", "colour": 71, "at": [0, -16, -250]})
    nose_parts.append({"id": "nose_wedge_l", "ref": "54200.dat", "colour": 71, "at": [-10, -16, -230]})
    nose_parts.append({"id": "nose_wedge_r", "ref": "54200.dat", "colour": 71, "at": [10, -16, -230]})

    # Forward tapered body with alternating tan and dark red accents
    for i, z in enumerate(range(-230, -130, 20)):
        # Central spine plate
        nose_parts.append({"id": f"nose_core_{z}", "ref": "3024.dat", "colour": 15, "at": [0, -8, z]})
        # GT signature tan patch
        if i in [1, 2]:
            nose_parts.append({"id": f"nose_tan_{z}", "ref": "3069b.dat", "colour": 19, "at": [0, -16, z]})
        else:
            nose_parts.append({"id": f"nose_white_{z}", "ref": "3069b.dat", "colour": 15, "at": [0, -16, z]})

        # Port & Starboard dark red stripes (Red Five squadron heraldry)
        nose_parts.append({"id": f"nose_red_l_{z}", "ref": "3024.dat", "colour": 320, "at": [-20, -8, z]})
        nose_parts.append({"id": f"nose_red_r_{z}", "ref": "3024.dat", "colour": 320, "at": [20, -8, z]})
        nose_parts.append({"id": f"nose_tile_l_{z}", "ref": "3069b.dat", "colour": 320, "at": [-20, -16, z]})
        nose_parts.append({"id": f"nose_tile_r_{z}", "ref": "3069b.dat", "colour": 320, "at": [20, -16, z]})

        # Lower chine taper
        nose_parts.append({"id": f"nose_lower_{z}", "ref": "3024.dat", "colour": 15, "at": [0, 0, z]})
        nose_parts.append({"id": f"nose_slope_l_{z}", "ref": "54200.dat", "colour": 71, "at": [-10, 8, z]})
        nose_parts.append({"id": f"nose_slope_r_{z}", "ref": "54200.dat", "colour": 71, "at": [10, 8, z]})

    steps_nose.append(nose_parts)
    sections.append({
        "name": "02_nose_fuselage.ldr",
        "description": "T-65B SNOT Tapered Nose with Red Five Markings",
        "steps": steps_nose
    })

    # -------------------------------------------------------------
    # 03: COCKPIT & CANOPY
    # -------------------------------------------------------------
    steps_cockpit = []
    cockpit_parts = [
        {"id": "cockpit_floor_1", "ref": "3022.dat", "colour": 72, "at": [0, -8, -120]},
        {"id": "cockpit_floor_2", "ref": "3022.dat", "colour": 72, "at": [0, -8, -80]},
        {"id": "cockpit_console", "ref": "3069b.dat", "colour": 0, "at": [0, -16, -110]},
        {"id": "cockpit_seat", "ref": "4079.dat", "colour": 72, "at": [0, -24, -80]},
        {"id": "cockpit_windscreen", "ref": "30372.dat", "colour": 47, "at": [0, -32, -90]},
        {"id": "canopy_sill_l", "ref": "3069b.dat", "colour": 71, "at": [-20, -24, -60]},
        {"id": "canopy_sill_r", "ref": "3069b.dat", "colour": 71, "at": [20, -24, -60]},
    ]
    steps_cockpit.append(cockpit_parts)
    sections.append({
        "name": "03_cockpit_canopy.ldr",
        "description": "Cockpit Tub, Flight Controls and Trans-Clear Canopy",
        "steps": steps_cockpit
    })

    # -------------------------------------------------------------
    # 04: DROID SOCKET (R2-D2)
    # -------------------------------------------------------------
    steps_droid = []
    droid_parts = [
        {"id": "droid_well", "ref": "3022.dat", "colour": 15, "at": [0, -8, -20]},
        {"id": "droid_collar_l", "ref": "3024.dat", "colour": 72, "at": [-10, -16, -20]},
        {"id": "droid_collar_r", "ref": "3024.dat", "colour": 72, "at": [10, -16, -20]},
        {"id": "r2d2_head", "ref": "30367b.dat", "colour": 15, "at": [0, -24, -20]},
        {"id": "droid_after_grille", "ref": "2412b.dat", "colour": 71, "at": [0, -16, 0]}
    ]
    steps_droid.append(droid_parts)
    sections.append({
        "name": "04_astromech_socket.ldr",
        "description": "Astromech Droid Bay with R2-D2 Dome",
        "steps": steps_droid
    })

    # -------------------------------------------------------------
    # 05: AFT FUSELAGE & GREEBLING TRENCH
    # -------------------------------------------------------------
    steps_aft = []
    aft_parts = []
    for z in range(20, 140, 20):
        aft_parts.append({"id": f"aft_core_{z}", "ref": "3004.dat", "colour": 15, "at": [0, -16, z]})
        aft_parts.append({"id": f"aft_plate_{z}", "ref": "3022.dat", "colour": 72, "at": [0, -24, z]})
        if z % 40 == 0:
            aft_parts.append({"id": f"trench_grille_{z}", "ref": "2412b.dat", "colour": 72, "at": [0, -32, z]})
            aft_parts.append({"id": f"pipe_l_{z}", "ref": "4599b.dat", "colour": 71, "at": [-10, -32, z]})
            aft_parts.append({"id": f"pipe_r_{z}", "ref": "4599b.dat", "colour": 71, "at": [10, -32, z]})
        else:
            aft_parts.append({"id": f"dial_{z}", "ref": "98138.dat", "colour": 179, "at": [0, -32, z]})
            aft_parts.append({"id": f"rib_l_{z}", "ref": "2877.dat", "colour": 72, "at": [-10, -24, z]})
            aft_parts.append({"id": f"rib_r_{z}", "ref": "2877.dat", "colour": 72, "at": [10, -24, z]})

    # Central thrust nozzle
    aft_parts.append({"id": "bulkhead_low", "ref": "3022.dat", "colour": 72, "at": [0, -8, 140]})
    aft_parts.append({"id": "bulkhead_mid", "ref": "3022.dat", "colour": 72, "at": [0, -16, 140]})
    aft_parts.append({"id": "rear_thruster", "ref": "4032.dat", "colour": 72, "at": [0, -12, 160], "matrix": ROT_X_90})

    steps_aft.append(aft_parts)
    sections.append({
        "name": "05_aft_fuselage.ldr",
        "description": "Rear Greebling Trench, Shield Generator and Exhaust Bulkhead",
        "steps": steps_aft
    })

    # -------------------------------------------------------------
    # 06, 07, 08, 09: FOUR HIGH-DEFINITION S-FOIL WINGS
    # Complete with 4 Nacelles and 4 T-65B Laser Cannons
    # -------------------------------------------------------------
    wing_specs = [
        {"sec_name": "06_wing_top_port.ldr", "desc": "Top Port S-Foil Wing and Turbine", "sx": -1, "y": -16},
        {"sec_name": "07_wing_bottom_port.ldr", "desc": "Bottom Port S-Foil Wing and Turbine", "sx": -1, "y": 8},
        {"sec_name": "08_wing_top_starboard.ldr", "desc": "Top Starboard S-Foil Wing and Turbine", "sx": 1, "y": -16},
        {"sec_name": "09_wing_bottom_starboard.ldr", "desc": "Bottom Starboard S-Foil Wing and Turbine", "sx": 1, "y": 8},
    ]

    for w in wing_specs:
        sec_name = w["sec_name"]
        sx = w["sx"]
        wy = w["y"]
        steps_wing = []
        wp = []

        # Inboard wing roots
        for z in [40, 80, 120]:
            wp.append({"id": f"root_{z}", "ref": "3022.dat", "colour": 71, "at": [sx * 40, wy, z]})

        # Main wing plates (span X from 60 to 140)
        for x_stud in range(3, 8):
            x_pos = sx * x_stud * 20
            for z_pos in [40, 80, 120]:
                wp.append({"id": f"wing_plate_{x_stud}_{z_pos}", "ref": "3024.dat", "colour": 15, "at": [x_pos, wy, z_pos]})

        # Smooth leading edges
        for x_stud in range(3, 8):
            x_pos = sx * x_stud * 20
            wp.append({"id": f"wing_tile_{x_stud}", "ref": "3069b.dat", "colour": 15, "at": [x_pos, wy - 8, 40]})

        # Red 5 identification stripes (5 distinctive red bars on wing surface)
        for s_idx in range(5):
            sz = 60 + s_idx * 16
            wp.append({"id": f"red5_stripe_{s_idx}", "ref": "3024.dat", "colour": 320, "at": [sx * 120, wy - 8, sz]})
            wp.append({"id": f"red5_outer_{s_idx}", "ref": "3069b.dat", "colour": 320, "at": [sx * 140, wy - 8, sz]})

        # Cooling grilles and access panels
        wp.append({"id": "grille_1", "ref": "2412b.dat", "colour": 71, "at": [sx * 80, wy - 8, 80]})
        wp.append({"id": "grille_2", "ref": "2412b.dat", "colour": 71, "at": [sx * 80, wy - 8, 100]})
        wp.append({"id": "round_dial", "ref": "98138.dat", "colour": 72, "at": [sx * 100, wy - 8, 80]})

        # Engine Nacelle
        nx = sx * 40
        ny = wy - 12
        wp.append({"id": "engine_intake_dish", "ref": "43898.dat", "colour": 71, "at": [nx, ny, 10], "matrix": ROT_X_90})
        wp.append({"id": "engine_cowl_1", "ref": "3941.dat", "colour": 15, "at": [nx, ny, 30]})
        wp.append({"id": "engine_cowl_2", "ref": "3941.dat", "colour": 15, "at": [nx, ny, 50]})
        wp.append({"id": "engine_rib", "ref": "30367b.dat", "colour": 71, "at": [nx, ny, 70]})
        wp.append({"id": "engine_mid", "ref": "3941.dat", "colour": 72, "at": [nx, ny, 90]})
        wp.append({"id": "engine_aft", "ref": "3941.dat", "colour": 71, "at": [nx, ny, 110]})
        wp.append({"id": "engine_exhaust_ring", "ref": "4032.dat", "colour": 72, "at": [nx, ny, 130]})
        wp.append({"id": "engine_exhaust_cone", "ref": "4589.dat", "colour": 72, "at": [nx, ny, 140], "matrix": ROT_X_90})
        wp.append({"id": "engine_thrust_glow", "ref": "3941.dat", "colour": 38, "at": [nx, ny, 150]})

        # Wingtip T-65B Laser Cannon
        lx = sx * 160
        ly = wy
        wp.append({"id": "cannon_base_1", "ref": "3024.dat", "colour": 71, "at": [lx, ly, 100]})
        wp.append({"id": "cannon_base_2", "ref": "3024.dat", "colour": 71, "at": [lx, ly, 60]})
        wp.append({"id": "cannon_base_3", "ref": "3024.dat", "colour": 71, "at": [lx, ly, 20]})
        wp.append({"id": "cannon_gen_rear", "ref": "3941.dat", "colour": 71, "at": [lx, ly - 4, 120]})
        wp.append({"id": "cannon_emitter_cap", "ref": "4589.dat", "colour": 72, "at": [lx, ly - 4, 140], "matrix": ROT_X_90})
        wp.append({"id": "cannon_gen_mid", "ref": "3941.dat", "colour": 71, "at": [lx, ly - 4, 80]})
        wp.append({"id": "cannon_coil_1", "ref": "4032.dat", "colour": 72, "at": [lx, ly - 4, 50]})
        wp.append({"id": "cannon_coil_2", "ref": "4032.dat", "colour": 71, "at": [lx, ly - 4, 30]})
        wp.append({"id": "cannon_barrel_1", "ref": "30374.dat", "colour": 71, "at": [lx, ly - 4, 0], "matrix": ROT_BAR_FWD})
        wp.append({"id": "cannon_barrel_2", "ref": "30374.dat", "colour": 71, "at": [lx, ly - 4, -40], "matrix": ROT_BAR_FWD})
        wp.append({"id": "cannon_brake", "ref": "4032.dat", "colour": 72, "at": [lx, ly - 4, -60]})
        wp.append({"id": "cannon_barrel_3", "ref": "30374.dat", "colour": 71, "at": [lx, ly - 4, -90], "matrix": ROT_BAR_FWD})
        wp.append({"id": "cannon_suppressor", "ref": "4589.dat", "colour": 71, "at": [lx, ly - 4, -130], "matrix": ROT_X_90})

        steps_wing.append(wp)
        sections.append({
            "name": sec_name,
            "description": w["desc"],
            "steps": steps_wing
        })

    # -------------------------------------------------------------
    # 00: MASTER ASSEMBLY
    # -------------------------------------------------------------
    master_steps = [[
        {"id": "inst_spine", "ref": "01_spine_chassis.ldr", "colour": 16, "at": [0,0,0]},
        {"id": "inst_nose", "ref": "02_nose_fuselage.ldr", "colour": 16, "at": [0,0,0]},
        {"id": "inst_cockpit", "ref": "03_cockpit_canopy.ldr", "colour": 16, "at": [0,0,0]},
        {"id": "inst_droid", "ref": "04_astromech_socket.ldr", "colour": 16, "at": [0,0,0]},
        {"id": "inst_aft", "ref": "05_aft_fuselage.ldr", "colour": 16, "at": [0,0,0]},
        {"id": "inst_wing_tp", "ref": "06_wing_top_port.ldr", "colour": 16, "at": [0,0,0]},
        {"id": "inst_wing_bp", "ref": "07_wing_bottom_port.ldr", "colour": 16, "at": [0,0,0]},
        {"id": "inst_wing_ts", "ref": "08_wing_top_starboard.ldr", "colour": 16, "at": [0,0,0]},
        {"id": "inst_wing_bs", "ref": "09_wing_bottom_starboard.ldr", "colour": 16, "at": [0,0,0]},
    ]]

    master_section = {
        "name": "x_wing_red_five_hd.ldr",
        "description": "Incom T-65B X-Wing Starfighter (Red Five) HD 500-Scale Master Assembly",
        "anchors": {"origin": {"at": [0,0,0]}},
        "steps": master_steps
    }

    all_sections = [master_section] + sections

    t1 = time.perf_counter()
    gen_time = t1 - t0

    plan = {
        "version": 1,
        "profile": "starwars",
        "author": "LdrawNova Gemini Engine",
        "sections": all_sections
    }

    # Count primitive parts
    part_count = 0
    for s in sections:
        for st in s["steps"]:
            part_count += len(st)

    return plan, gen_time, part_count

if __name__ == "__main__":
    plan, gen_time, part_count = build_hd_plan()
    out_dir = "output/x-wing-red-five-hd-500"
    os.makedirs(out_dir, exist_ok=True)
    plan_path = os.path.join(out_dir, "x_wing_hd_valid.plan.json")
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"Modular Plan created with {part_count} primitive parts across {len(plan['sections'])} submodels in {gen_time*1000:.2f} ms")
