#!/usr/bin/env python3
"""Progressive scale testing: MICRO → SMALL → MEDIUM with automatic gates.

Runs each escalón (tier) with baseline vs learning comparison.
Gates determine promotion to next tier based on convergence, delta learning, and quality metrics.

Escalones:
  1. MICRO/trivial:  6-20 piezas,   N=5,  max_iter=2
  2. MICRO/simple:   20-50 piezas,  N=10, max_iter=3
  3. SMALL:          50-200 piezas, N=10, max_iter=3, weight_struct=0.4
  4. MEDIUM:         200+ piezas,   N=5,  max_iter=4, weight_struct=0.5

Each escalón produces GATE_REPORT.json with pass/fail criteria + recommendation.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.bench.select_micro_sets import select_micro_sets, get_io_path
from ldraw_tools.structural_diff_config import infer_tier, get_config_for_tier


ESCALONES = [
    {
        "name": "Escalón 1: MICRO/trivial",
        "min_parts": 6,
        "max_parts": 20,
        "n": 5,
        "max_iter": 2,
        "permissive_gate": False,
        "few_shot": False,
    },
    {
        "name": "Escalón 2: MICRO/simple",
        "min_parts": 20,
        "max_parts": 50,
        "n": 10,
        "max_iter": 3,
        "permissive_gate": False,
        "few_shot": False,
    },
    {
        "name": "Escalón 3: SMALL",
        "min_parts": 50,
        "max_parts": 200,
        "n": 10,
        "max_iter": 3,
        "permissive_gate": True,
        "few_shot": False,
    },
    {
        "name": "Escalón 4: MEDIUM",
        "min_parts": 200,
        "max_parts": 2000,
        "n": 5,
        "max_iter": 4,
        "permissive_gate": True,
        "few_shot": True,
    },
]


def run_harness(io_path: Path, sample_id: str, output_dir: Path, learning_enabled: bool, max_iter: int, 
                permissive_gate: bool = False, few_shot: bool = False, tier: str = "MICRO") -> Optional[Dict[str, Any]]:
    """Run harness, return result dict or None on error."""
    env = os.environ.copy()
    env["LDRAW_ENABLE_LEARNING"] = "1" if learning_enabled else "0"
    
    harness = Path(__file__).parent / "harness_e2e_real.py"
    cmd = [
        sys.executable, str(harness),
        "--io-file", str(io_path),
        "--sample-id", sample_id,
        "--output", str(output_dir),
        "--max-iter", str(max_iter),
    ]
    
    if permissive_gate:
        cmd.append("--permissive-gate")
    if few_shot:
        cmd.append("--few-shot")
    
    mode_label = "LEARNING" if learning_enabled else "BASELINE"
    print(f"    [{sample_id}] {mode_label:8s}... ", end="", flush=True)
    
    try:
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=900,
            cwd=Path(__file__).parent.parent.parent
        )
        
        result_file = output_dir / sample_id / "e2e_result.json"
        if result_file.exists():
            with open(result_file) as f:
                res = json.load(f)
            score = res.get("best_score", 0.0)
            iterations = res.get("iterations", 0)
            print(f"✅ score={score:.1f}, iter={iterations}")
            return res
        else:
            # Print error details
            if result.returncode != 0:
                print(f"❌ Harness error (rc={result.returncode})")
                if result.stderr:
                    err_preview = result.stderr[:200]
                    print(f"      {err_preview}")
                    # Save full error to file for debugging
                    err_file = output_dir / f"{sample_id}_error.txt"
                    err_file.write_text(result.stderr)
            else:
                print(f"❌ No result file (harness succeeded but no output)")
            return None
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout (15min)")
        return None
    except Exception as e:
        print(f"❌ {str(e)[:80]}")
        return None


def run_escalon(
    escalon_config: Dict[str, Any],
    splits_file: Path,
    io_dir: Path,
    output_base: Path,
    escalon_num: int,
) -> Tuple[bool, Dict[str, Any]]:
    """Run one escalón (baseline + learning). Return (passed, report_dict)."""
    
    name = escalon_config["name"]
    min_p = escalon_config["min_parts"]
    max_p = escalon_config["max_parts"]
    n = escalon_config["n"]
    max_iter = escalon_config["max_iter"]
    permissive = escalon_config["permissive_gate"]
    few_shot = escalon_config["few_shot"]
    
    escalon_dir = output_base / f"escalon_{escalon_num}"
    escalon_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"{name}")
    print(f"{'='*80}")
    print(f"Config: {min_p}-{max_p} piezas, N={n}, max_iter={max_iter}")
    print(f"  Flags: permissive_gate={permissive}, few_shot={few_shot}")
    
    # Select sets
    print(f"\n[1] Selecting {n} sets from splits.json...")
    try:
        selected = select_micro_sets(splits_file, n=n, min_parts=min_p, max_parts=max_p, seed=42)
        if not selected:
            print(f"  ❌ No sets found in range [{min_p}, {max_p}]")
            return False, {"error": "No sets in range"}
        print(f"  ✅ Selected {len(selected)} sets")
    except Exception as e:
        print(f"  ❌ Selection failed: {e}")
        return False, {"error": str(e)}
    
    # Baseline
    print(f"\n[2] Running BASELINE (learning OFF)...")
    baseline_dir = escalon_dir / "baseline"
    baseline_results = []
    
    for sample_id, parts, steps in selected:
        try:
            io_path = get_io_path(sample_id, Path(io_dir))
            tier = infer_tier(parts)
            res = run_harness(io_path, sample_id, baseline_dir, False, max_iter, permissive, few_shot, tier)
            if res:
                res["sample_id"] = sample_id
                res["parts"] = parts
                baseline_results.append(res)
            else:
                baseline_results.append({"sample_id": sample_id, "parts": parts, "error": "No result"})
        except Exception as e:
            baseline_results.append({"sample_id": sample_id, "parts": parts, "error": str(e)})
    
    # Learning
    print(f"\n[3] Running LEARNING (learning ON)...")
    learning_dir = escalon_dir / "learning"
    learning_results = []
    
    for sample_id, parts, steps in selected:
        try:
            io_path = get_io_path(sample_id, Path(io_dir))
            tier = infer_tier(parts)
            res = run_harness(io_path, sample_id, learning_dir, True, max_iter, permissive, few_shot, tier)
            if res:
                res["sample_id"] = sample_id
                res["parts"] = parts
                learning_results.append(res)
            else:
                learning_results.append({"sample_id": sample_id, "parts": parts, "error": "No result"})
        except Exception as e:
            learning_results.append({"sample_id": sample_id, "parts": parts, "error": str(e)})
    
    # Aggregate & gates
    print(f"\n[4] Analyzing results...")
    
    def agg(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        valid = [r for r in results if "best_score" in r]
        errors = [r for r in results if "error" in r]
        if not valid:
            return {"count": 0, "errors": len(errors)}
        return {
            "count": len(valid),
            "errors": len(errors),
            "avg_score": sum(r["best_score"] for r in valid) / len(valid),
            "avg_iter": sum(r.get("iterations", 0) for r in valid) / len(valid),
            "min_score": min(r["best_score"] for r in valid),
            "max_score": max(r["best_score"] for r in valid),
            "results": valid,
        }
    
    baseline_agg = agg(baseline_results)
    learning_agg = agg(learning_results)
    
    print(f"\n  BASELINE: count={baseline_agg.get('count', 0)}, avg_score={baseline_agg.get('avg_score', 0):.1f}, avg_iter={baseline_agg.get('avg_iter', 0):.1f}")
    print(f"  LEARNING: count={learning_agg.get('count', 0)}, avg_score={learning_agg.get('avg_score', 0):.1f}, avg_iter={learning_agg.get('avg_iter', 0):.1f}")
    
    baseline_score = baseline_agg.get("avg_score", 0)
    learning_score = learning_agg.get("avg_score", 0)
    delta_score = learning_score - baseline_score
    
    print(f"  DELTA: score {delta_score:+.1f}, iter {learning_agg.get('avg_iter', 0) - baseline_agg.get('avg_iter', 0):+.1f}")
    
    # Gate criteria
    print(f"\n[5] Gate criteria:")
    
    gate_pass = True
    gate_details = {}
    
    # Criterion 1: At least N-1 successful runs
    success_rate = baseline_agg.get("count", 0) / n if n > 0 else 0
    criterion_1 = success_rate >= 0.8
    gate_details["success_rate_baseline"] = (success_rate, criterion_1)
    print(f"  ✓ Baseline success rate ≥ 80%: {success_rate*100:.0f}% {'✅' if criterion_1 else '❌'}")
    gate_pass = gate_pass and criterion_1
    
    # Criterion 2: Baseline score < 100 (not completely broken, allows 10.0 fallback for no-render case)
    criterion_2 = baseline_score < 100
    gate_details["baseline_not_fake"] = (baseline_score, criterion_2)
    print(f"  ✓ Baseline avg_score < 100: {baseline_score:.1f} {'✅' if criterion_2 else '❌'}")
    gate_pass = gate_pass and criterion_2
    
    # Criterion 3: Learning delta >= 0 (learning helps or doesn't hurt)
    criterion_3 = delta_score >= -1.0  # Allow -1 tolerance for noise
    gate_details["delta_learning"] = (delta_score, criterion_3)
    print(f"  ✓ Delta learning ≥ -1.0: {delta_score:+.1f} {'✅' if criterion_3 else '⚠️'}")
    if not criterion_3:
        gate_pass = False
    
    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "escalon": escalon_num,
        "name": name,
        "config": escalon_config,
        "selected_sets": len(selected),
        "gate_pass": gate_pass,
        "gate_details": gate_details,
        "baseline": baseline_agg,
        "learning": learning_agg,
    }
    
    # Save gate report
    gate_report_file = escalon_dir / "GATE_REPORT.json"
    with open(gate_report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n{'='*80}")
    if gate_pass:
        print(f"✅ GATE PASSED: Ready for next escalón")
    else:
        print(f"❌ GATE FAILED: Review results above")
    print(f"{'='*80}")
    print(f"Report: {gate_report_file}\n")
    
    return gate_pass, report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Progressive scale testing")
    parser.add_argument("--splits", required=True, help="Path to splits.json")
    parser.add_argument("--io-dir", required=True, help="Path to IO corpus")
    parser.add_argument("--start-escalon", type=int, default=1, help="Start at escalón (1-4)")
    parser.add_argument("--output", type=Path, default=Path("/tmp/scale_test_progressive"))
    
    args = parser.parse_args()
    
    splits_file = Path(args.splits)
    io_dir = Path(args.io_dir)
    output_base = Path(args.output)
    start_escalon = args.start_escalon
    
    if not splits_file.exists():
        print(f"❌ splits.json not found: {splits_file}")
        sys.exit(1)
    
    if not io_dir.exists():
        print(f"❌ IO dir not found: {io_dir}")
        sys.exit(1)
    
    output_base.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*80)
    print("🚀 PROGRESSIVE SCALE TESTING: MICRO → SMALL → MEDIUM")
    print("="*80)
    print(f"Output: {output_base}")
    
    all_reports = []
    
    for idx, escalon_cfg in enumerate(ESCALONES, start=1):
        if idx < start_escalon:
            print(f"\n⋘ Escalón {idx}: Skipped (start={start_escalon})")
            continue
        
        passed, report = run_escalon(escalon_cfg, splits_file, io_dir, output_base, idx)
        all_reports.append(report)
        
        if not passed:
            print(f"\n❌ Gate failed at Escalón {idx}. Stopping.")
            print(f"\n📊 SUMMARY (stopped at Escalón {idx}):")
            for r in all_reports:
                s = "✅" if r["gate_pass"] else "❌"
                print(f"  {s} {r['name']}")
            
            # Save master report
            master = {
                "timestamp": datetime.now().isoformat(),
                "status": "STOPPED",
                "stopped_at_escalon": idx,
                "escalones": all_reports,
            }
            master_file = output_base / "MASTER_REPORT.json"
            with open(master_file, "w") as f:
                json.dump(master, f, indent=2)
            print(f"\nMaster report: {master_file}")
            print(f"\n👉 FIX the gate failures and re-run with --start-escalon {idx}")
            break
        else:
            if idx < len(ESCALONES):
                response = input(f"\n👉 Escalón {idx} PASSED. Proceed to Escalón {idx+1}? (y/n) ").strip().lower()
                if response != "y":
                    print(f"✋ Stopping. You can resume with --start-escalon {idx+1}")
                    break
    else:
        print(f"\n🎉 ALL ESCALONES PASSED!")
        master = {
            "timestamp": datetime.now().isoformat(),
            "status": "COMPLETE",
            "escalones": all_reports,
        }
        master_file = output_base / "MASTER_REPORT.json"
        with open(master_file, "w") as f:
            json.dump(master, f, indent=2)
        print(f"\nMaster report: {master_file}")


if __name__ == "__main__":
    main()
