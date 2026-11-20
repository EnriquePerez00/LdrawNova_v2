"""Scale test: Intermediate (10 MICRO sets, baseline vs learning, SEQUENTIAL).

Compares convergence with/without learning. Runs SEQUENTIALLY to avoid race conditions.
"""
import json, os, subprocess, sys
from pathlib import Path
from datetime import datetime
from select_micro_sets import select_micro_sets, get_io_path


def run_harness(io_path, sample_id, output_dir, learning_enabled, max_iter=2, permissive_gate=True):
    """Run harness, return result dict."""
    env = os.environ.copy()
    env["LDRAW_ENABLE_LEARNING"] = "1" if learning_enabled else "0"
    
    harness = Path(__file__).parent / "harness_e2e_real.py"
    cmd = [sys.executable, str(harness), "--io-file", str(io_path), "--sample-id", sample_id,
           "--output", str(output_dir), "--max-iter", str(max_iter)]
    if permissive_gate:
        cmd.append("--permissive-gate")
    
    print(f"  [{sample_id}] Learning={'ON' if learning_enabled else 'OFF'}...")
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600,
                              cwd=Path(__file__).parent.parent.parent)
        result_file = output_dir / sample_id / "e2e_result.json"
        if result_file.exists():
            with open(result_file) as f:
                res = json.load(f)
            print(f"    ✅ score={res.get('best_score',0):.1f}, iter={res.get('iterations',0)}")
            return res
    except Exception as e:
        print(f"    ❌ {str(e)[:100]}")
    return {"status": "error"}


def run_scale_test(splits_file, io_dir, n_sets=10, max_iter=2, output_base=Path("/tmp/scale_test_intermediate")):
    """Run baseline + learning on N MICRO sets sequentially."""
    output_base.mkdir(parents=True, exist_ok=True)
    print("\n" + "="*70)
    print("SCALE TEST: Intermediate (10 MICRO, Baseline vs Learning)")
    print("="*70)
    
    selected = select_micro_sets(splits_file, n=n_sets)
    if not selected:
        print("❌ No MICRO sets found!")
        return
    
    print(f"\n[2] BASELINE (learning OFF)...")
    baseline_dir = output_base / "baseline"
    baseline_results = []
    for sample_id, parts, steps in selected:
        try:
            io_path = get_io_path(sample_id, Path(io_dir))
            res = run_harness(io_path, sample_id, baseline_dir, False, max_iter)
            res["sample_id"] = sample_id
            baseline_results.append(res)
        except Exception as e:
            baseline_results.append({"sample_id": sample_id, "error": str(e)})
    
    print(f"\n[3] LEARNING (learning ON, shared --output)...")
    learning_dir = output_base / "learning"
    learning_results = []
    for sample_id, parts, steps in selected:
        try:
            io_path = get_io_path(sample_id, Path(io_dir))
            res = run_harness(io_path, sample_id, learning_dir, True, max_iter)
            res["sample_id"] = sample_id
            learning_results.append(res)
        except Exception as e:
            learning_results.append({"sample_id": sample_id, "error": str(e)})
    
    print(f"\n[4] Results Comparison:")
    def agg(results):
        valid = [r for r in results if "best_score" in r]
        return {"count": len(valid), "avg_score": sum(r["best_score"] for r in valid)/len(valid) if valid else 0,
                "avg_iter": sum(r.get("iterations",0) for r in valid)/len(valid) if valid else 0} if valid else {}
    
    baseline_agg = agg(baseline_results)
    learning_agg = agg(learning_results)
    
    print(f"\n  BASELINE: avg_score={baseline_agg.get('avg_score',0):.1f}, avg_iter={baseline_agg.get('avg_iter',0):.1f}")
    print(f"  LEARNING: avg_score={learning_agg.get('avg_score',0):.1f}, avg_iter={learning_agg.get('avg_iter',0):.1f}")
    print(f"  DELTA: score {learning_agg.get('avg_score',0)-baseline_agg.get('avg_score',0):+.1f}, iter {learning_agg.get('avg_iter',0)-baseline_agg.get('avg_iter',0):+.1f}")
    
    report = {"timestamp": datetime.now().isoformat(), "baseline": baseline_agg, "learning": learning_agg,
              "results": {"baseline": baseline_results, "learning": learning_results}}
    report_file = output_base / "SCALE_TEST_REPORT.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n✅ Report saved: {report_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits", required=True)
    parser.add_argument("--io-dir", required=True)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--max-iter", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("/tmp/scale_test_intermediate"))
    args = parser.parse_args()
    run_scale_test(Path(args.splits), args.io_dir, args.n, args.max_iter, args.output)
