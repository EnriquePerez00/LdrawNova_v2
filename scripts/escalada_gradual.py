#!/usr/bin/env python3
"""Escalada Gradual: Aumenta corpus incrementalmente"""

import json
import os
import subprocess
from pathlib import Path

BASE = Path("/Users/I764690/Code_personal/LegoGPT")

LEVELS = [("SMALL", 20), ("MEDIUM", 50), ("LARGE", 100), ("XLARGE", 250)]

def load_corpus():
    with open(BASE / "data/dataset_splits/corpus_all_pairs.json") as f:
        return json.load(f)

def split_corpus(corpus, train_ratio=0.7):
    split_idx = int(len(corpus) * train_ratio)
    return corpus[:split_idx], corpus[split_idx:]

def create_level(name, size):
    """Crea nivel N del corpus"""
    print(f"\n📊 NIVEL: {name} ({size} MOCs)")
    print("="*60)
    
    corpus = load_corpus()[:size]
    train, val = split_corpus(corpus, 0.7)
    
    outdir = BASE / "outputs" / name
    os.makedirs(outdir, exist_ok=True)
    
    # Save splits
    with open(outdir / "train.json", "w") as f:
        json.dump(train, f)
    with open(outdir / "val.json", "w") as f:
        json.dump(val, f)
    
    print(f"✅ Train: {len(train)} | Val: {len(val)}")
    
    # Run Iter 1
    print(f"\n1️⃣  Iter 1 (Baseline)...")
    cmd = [
        ".venv/bin/python3", "scripts/run_moc_continuous_improvement_loop.py",
        "--limit", str(len(train)), "--iterations", "1",
        "--output-dir", f"outputs/{name}_iter1",
    ]
    result = subprocess.run(cmd, cwd=BASE)
    
    if result.returncode != 0:
        print(f"❌ Error en Iter 1")
        return False
    
    # Run Iter 2
    print(f"\n2️⃣  Iter 2 (Con Fixes)...")
    fixes = f"outputs/{name}_iter1/generalized_fixes_iter_1.json"
    cmd = [
        ".venv/bin/python3", "scripts/run_moc_continuous_improvement_loop.py",
        "--limit", str(len(train)), "--iterations", "1",
        "--input-fixes", fixes,
        "--output-dir", f"outputs/{name}_iter2",
    ]
    result = subprocess.run(cmd, cwd=BASE)
    
    if result.returncode != 0:
        print(f"❌ Error en Iter 2")
        return False
    
    # Show results
    for i, iter_num in enumerate([1, 2], 1):
        report = BASE / f"outputs/{name}_iter{iter_num}/iter_{iter_num}_report.json"
        if report.exists():
            with open(report) as f:
                data = json.load(f)["summary"]
                survival = data["mean_survival_ratio"] * 100
                incidents = data["total_first_error_aborts"]
                print(f"   Iter {iter_num}: Survival {survival:.2f}%, Incidents {incidents}")
    
    print(f"\n✅ Nivel {name} completado")
    return True

def main():
    print("\n🎓 ESCALADA GRADUAL DEL LOOP\n")
    
    for name, size in LEVELS:
        if not create_level(name, size):
            break
        
        resp = input(f"\n❓ ¿Siguiente nivel? (s/n): ").strip().lower()
        if resp != "s":
            break
    
    print(f"\n✅ Escalada completada")

if __name__ == "__main__":
    main()
