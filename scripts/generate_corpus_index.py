import os
import json
import sqlite3
import re

DB_PATH = "data/catalog/models_catalog.db"
OUT_PATH = "data/dataset_splits/corpus_all_pairs.json"

COMPLEXITY_TIERS = [
    ("MICRO", 0, 50),
    ("SMALL", 51, 150),
    ("MEDIUM", 151, 400),
    ("COMPLEX", 401, 1000),
    ("EXPERT", 1001, 3000),
    ("MONUMENTAL", 3001, 999999),
]

def assign_tier(parts):
    for code, low, high in COMPLEXITY_TIERS:
        if low <= parts <= high:
            return code
    return "UNKNOWN"

def count_parts_from_mpd(mpd_path: str) -> int:
    """Count actual parts by counting '^1 ' lines in the MPD file."""
    if not os.path.exists(mpd_path):
        return 0
    try:
        count = 0
        with open(mpd_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # MPD/LDraw part reference starts with "1 " (command type 1)
                if line.startswith('1 '):
                    count += 1
        return count
    except Exception as e:
        print(f"Warning: Could not parse {mpd_path}: {e}")
        return 0

def main():
    if not os.path.exists("data/omr_raw/"):
        print("ERROR: data/omr_raw/ not found")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    rows = cursor.execute("SELECT pair_id, model_file_path, parts_count, source FROM ground_truth_pairs WHERE model_file_path LIKE '%omr_raw%' ORDER BY parts_count").fetchall()

    corpus = []
    found = 0
    skipped_zero = 0
    
    for pair_id, model_file_path, parts_count_db, source in rows:
        if model_file_path is None:
            continue
        # Check file exists
        if not os.path.exists(model_file_path):
            continue
        
        # Count parts from actual file (overrides DB value)
        actual_parts_count = count_parts_from_mpd(model_file_path)
        if actual_parts_count == 0:
            skipped_zero += 1
            continue
        
        category = "OFFICIAL_OMR" if source == "ldraw_omr" else source
        entry = {
            "moc_id": pair_id,
            "io_path": model_file_path,
            "parts_count": actual_parts_count,  # Use actual count from file
            "complexity_tier": assign_tier(actual_parts_count),
            "category": category,
        }
        corpus.append(entry)
        found += 1
    conn.close()

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(corpus, f, indent=2)

    print(f"Corpus index generated with {found} entries to {OUT_PATH}")
    print(f"Skipped {skipped_zero} entries with 0 parts (empty or unparseable)")
    
    # Print tier distribution
    tier_counts = {}
    for entry in corpus:
        tier = entry["complexity_tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    print("\nTier distribution:")
    for tier_name, low, high in COMPLEXITY_TIERS:
        count = tier_counts.get(tier_name, 0)
        print(f"  {tier_name:12} ({low:5}-{high:5}): {count:4} sets")

if __name__ == "__main__":
    main()
