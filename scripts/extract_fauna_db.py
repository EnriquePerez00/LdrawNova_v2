"""
Extract Animal and Fauna sets (Creator 3-in-1, Ideas, Icons, etc.) and parts inventory from Brickclinic DB.
Outputs curated whitelists, color palettes, and part-color combinations for organic animal generation.
"""
import json
import subprocess
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = REPO_ROOT / "profiles" / "fauna" / "catalog"
CATALOG_DIR.mkdir(parents=True, exist_ok=True)

def run_psql(query: str) -> str:
    # Connect directly to local postgres on 54342
    cmd = [
        "psql", "postgresql://postgres:postgres@127.0.0.1:54342/postgres",
        "-t", "-A", "-c", query
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"PSQL Error: {res.stderr}")
    return res.stdout.strip()

print("1. Fetching Animal & Fauna sets from Brickclinic DB...")
# Curated target list + keyword matching for high-quality animal/creature sets
sets_query = """
WITH target_sets AS (
    SELECT s.set_num, s.name, s.year, s.num_parts, s.img_url, t.name as theme_name
    FROM sets s
    JOIN themes t ON s.theme_id = t.id
    WHERE s.set_num IN (
        '31129-1', '31150-1', '31136-1', '31144-1', '31157-1', '31125-1', '31137-1', 
        '31154-1', '31133-1', '31121-1', '31031-1', '31019-1', '31021-1', '31044-1', 
        '31170-1', '31171-1', '31165-1', '31088-1', '31128-1', '31158-1', '31058-1', 
        '31151-1', '21349-1', '21342-1', '10331-1', '21301-1', '21320-1', '76394-1', 
        '75979-1', '43249-1', '43247-1', '31032-1', '31159-1', '76968-1', '76964-1'
    )
    OR (
        s.year >= 2010 
        AND s.num_parts >= 80 
        AND (
            s.name ILIKE '%animal%' OR s.name ILIKE '%creature%' OR 
            s.name ILIKE '%dinosaur%' OR s.name ILIKE '%bird%' OR 
            s.name ILIKE '%insect%' OR s.name ILIKE '%safari%' OR 
            s.name ILIKE '%tiger%' OR s.name ILIKE '%lion%' OR 
            s.name ILIKE '%dolphin%' OR s.name ILIKE '%shark%' OR 
            s.name ILIKE '%parrot%' OR s.name ILIKE '%peacock%'
        )
    )
)
SELECT json_agg(target_sets ORDER BY year DESC, num_parts DESC) FROM target_sets;
"""

sets_json = run_psql(sets_query)
sets_data = json.loads(sets_json) if sets_json else []
print(f"Total animal sets cataloged: {len(sets_data)}")

# Save sets summary
sets_summary_file = CATALOG_DIR / "fauna_sets_summary.json"
with open(sets_summary_file, "w") as f:
    json.dump({
        "total_sets": len(sets_data),
        "sets": sets_data
    }, f, indent=2)
print(f"Saved: {sets_summary_file}")

target_set_nums = [s["set_num"] for s in sets_data]
set_nums_sql = "'" + "','".join(target_set_nums) + "'"

print("2. Fetching distinct colors used in Animal sets...")
colors_query = f"""
WITH fauna_parts AS (
    SELECT ip.part_num, ip.color_id, ip.quantity
    FROM sets s
    JOIN inventories inv ON inv.set_num = s.set_num
    JOIN inventory_parts ip ON ip.inventory_id = inv.id
    WHERE s.set_num IN ({set_nums_sql})
      AND ip.is_spare = false
)
SELECT json_agg(c_data ORDER BY total_quantity DESC) FROM (
    SELECT 
        c.id as rebrickable_id,
        c.name as color_name,
        c.rgb as hex,
        c.is_trans,
        count(DISTINCT fp.part_num) as distinct_parts,
        sum(fp.quantity) as total_quantity
    FROM fauna_parts fp
    JOIN colors c ON fp.color_id = c.id
    GROUP BY c.id, c.name, c.rgb, c.is_trans
) c_data;
"""
colors_json = run_psql(colors_query)
colors_data = json.loads(colors_json) if colors_json else []
print(f"Total distinct colors: {len(colors_data)}")

# Color mapping to LDraw codes
REBRICKABLE_TO_LDRAW = {
    0: 0,       # Black
    1: 4,       # Blue
    2: 2,       # Green
    3: 3,       # Dark Turquoise
    4: 14,      # Red
    5: 13,      # Dark Pink
    14: 14,     # Yellow -> LDraw 14
    15: 15,     # White
    19: 19,     # Tan (LDraw 19)
    25: 25,     # Orange
    27: 27,     # Lime
    28: 28,     # Dark Tan (LDraw 28)
    69: 69,     # Dark Purple (LDraw 89)
    70: 70,     # Reddish Brown (LDraw 70)
    71: 71,     # Light Bluish Gray (LDraw 71)
    72: 72,     # Dark Bluish Gray (LDraw 72)
    84: 84,     # Medium Nougat (LDraw 84)
    85: 85,     # Dark Orange (LDraw 484)
    86: 86,     # Light Nougat (LDraw 78)
    89: 89,     # Dark Blue (LDraw 272)
    92: 92,     # Nougat (LDraw 92)
    106: 106,   # Fabuland Brown
    110: 110,   # Bright Light Orange (LDraw 191)
    115: 115,   # Medium Lime
    128: 128,   # Dark Brown (LDraw 308)
    150: 150,   # Medium Azure (LDraw 212)
    151: 151,   # Dark Azure (LDraw 321)
    153: 153,   # Aqua / Light Aqua (LDraw 226)
    154: 154,   # Lavender (LDraw 31)
    157: 157,   # Yellowish Green (LDraw 326)
    212: 212,   # Bright Light Yellow
    320: 320,   # Dark Red (LDraw 320)
    322: 322,   # Medium Dark Pink
    323: 323,   # Light Pink
    326: 326,   # Olive Green (LDraw 330)
    330: 330,   # Olive Green
    36: 36,     # Trans-Red
    40: 40,     # Trans-Black / Trans-Brown
    41: 41,     # Trans-Light Blue
    42: 42,     # Trans-Neon Green
    46: 46,     # Trans-Yellow
    47: 47,     # Trans-Clear
    111: 111,   # Trans-Dark Pink
}

palette_entries = []
for c in colors_data:
    rb_id = c["rebrickable_id"]
    ldraw_code = REBRICKABLE_TO_LDRAW.get(rb_id, rb_id)
    palette_entries.append({
        "rebrickable_id": rb_id,
        "ldraw_color_code": ldraw_code,
        "name": c["color_name"],
        "hex": c["hex"],
        "is_trans": c["is_trans"],
        "distinct_parts": c["distinct_parts"],
        "total_quantity": c["total_quantity"]
    })

palette_file = CATALOG_DIR / "fauna_palette.json"
with open(palette_file, "w") as f:
    json.dump({
        "metrics": {
            "total_colors": len(palette_entries),
            "dominant_organic_colors": [
                {"name": "Black", "code": 0, "role": "Eyes, claws, noses, striping, pupils"},
                {"name": "White", "code": 15, "role": "Sclera, bellies, plumage, fur highlights"},
                {"name": "Reddish Brown", "code": 70, "role": "Mammal fur, wood branches, raptor feathers"},
                {"name": "Dark Brown", "code": 308, "role": "Deep fur shadows, hooves, raptor beaks"},
                {"name": "Tan", "code": 19, "role": "Savanna animals, desert coats, skin, underbellies"},
                {"name": "Dark Tan", "code": 28, "role": "Accents, lions, deer, antlers"},
                {"name": "Orange", "code": 25, "role": "Tigers, beaks, foxes, clownfish"},
                {"name": "Dark Orange", "code": 484, "role": "Tigers, foxes, plumage, butterflies"},
                {"name": "Bright Light Orange", "code": 191, "role": "Lions, parrots, tropical fish"},
                {"name": "Yellow", "code": 14, "role": "Beaks, eyes, tropical markings, insects"},
                {"name": "Lime / Olive Green", "code": 27, "role": "Frogs, reptiles, praying mantis, foliage"},
                {"name": "Dark Green", "code": 288, "role": "Reptile scales, deep forest leaves, bases"},
                {"name": "Dark Blue / Medium Azure", "code": 272, "role": "Kingfisher, parrots, tropical sea creatures"},
                {"name": "Trans-Clear / Trans-Light Blue", "code": 47, "role": "Water bases, insect wings, splash effects"}
            ]
        },
        "colors": palette_entries
    }, f, indent=2)
print(f"Saved: {palette_file}")

print("3. Fetching distinct parts and usage frequency...")
parts_query = f"""
WITH fauna_parts AS (
    SELECT ip.part_num, ip.color_id, ip.quantity
    FROM sets s
    JOIN inventories inv ON inv.set_num = s.set_num
    JOIN inventory_parts ip ON ip.inventory_id = inv.id
    WHERE s.set_num IN ({set_nums_sql})
      AND ip.is_spare = false
)
SELECT json_agg(p_data ORDER BY total_qty DESC) FROM (
    SELECT 
        p.part_num,
        p.name,
        COALESCE(pc.name, 'Other') as category_name,
        pc.id as category_id,
        count(DISTINCT fp.color_id) as available_in_colors_count,
        sum(fp.quantity) as total_qty
    FROM fauna_parts fp
    JOIN parts p ON fp.part_num = p.part_num
    LEFT JOIN part_categories pc ON p.part_cat_id = pc.id
    GROUP BY p.part_num, p.name, pc.name, pc.id
) p_data;
"""
parts_json = run_psql(parts_query)
parts_data = json.loads(parts_json) if parts_json else []
print(f"Total distinct parts: {len(parts_data)}")

# Classify parts into semantic groups
semantic_classification = {
    "articulation_ball_joints": [
        "14704", "14417", "14418", "14419", "22484", "14707", "47455", "47452",
        "27336", "3614", "92013", "57360", "53923", "48336", "60478", "60470b"
    ],
    "snot_brackets_and_adapters": [
        "11211", "87087", "44728", "99780", "99781", "99207", "22885", "4070",
        "30414", "15573", "87081", "2436", "41682"
    ],
    "organic_curved_slopes": [
        "11477", "15068", "50950", "11153", "29119", "29120", "24201", "54200",
        "85984", "6091", "18653", "37352", "4286", "3040", "3298", "13547"
    ],
    "creature_features_teeth_claws_eyes": [
        "53451", "15208", "49668", "88072", "3069b", "98138", "25269", "35480",
        "2654", "4032a", "2420", "32828", "11090", "87994", "65578", "23443"
    ]
}

whitelist_file = CATALOG_DIR / "fauna_whitelist.json"
with open(whitelist_file, "w") as f:
    json.dump({
        "metrics": {
            "total_fauna_sets": len(sets_data),
            "total_distinct_parts": len(parts_data),
            "total_distinct_colors": len(colors_data),
            "semantic_subsystems": {
                "articulation": len(semantic_classification["articulation_ball_joints"]),
                "snot_core": len(semantic_classification["snot_brackets_and_adapters"]),
                "curved_skin": len(semantic_classification["organic_curved_slopes"]),
                "micro_details": len(semantic_classification["creature_features_teeth_claws_eyes"])
            }
        },
        "semantic_groups": semantic_classification,
        "parts": parts_data
    }, f, indent=2)
print(f"Saved: {whitelist_file}")

print("4. Fetching verified (part_num, color_id) combinations...")
combos_query = f"""
WITH fauna_parts AS (
    SELECT DISTINCT ip.part_num, ip.color_id, sum(ip.quantity) as total_qty
    FROM sets s
    JOIN inventories inv ON inv.set_num = s.set_num
    JOIN inventory_parts ip ON ip.inventory_id = inv.id
    WHERE s.set_num IN ({set_nums_sql})
      AND ip.is_spare = false
    GROUP BY ip.part_num, ip.color_id
)
SELECT json_agg(c ORDER BY total_qty DESC) FROM fauna_parts c;
"""
combos_json = run_psql(combos_query)
combos_data = json.loads(combos_json) if combos_json else []
print(f"Total verified part-color combos: {len(combos_data)}")

combos_file = CATALOG_DIR / "fauna_part_color_combos.json"
with open(combos_file, "w") as f:
    json.dump({
        "total_combos": len(combos_data),
        "combos": combos_data
    }, f, indent=2)
print(f"Saved: {combos_file}")

print("\n[SUCCESS] Extraction completed successfully!")
