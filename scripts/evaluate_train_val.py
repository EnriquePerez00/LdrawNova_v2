#!/usr/bin/env python3
"""
Train/Val Evaluation for Loop Overfitting Detection
====================================================

Runs bundle synthesis on train split, evaluates on val split,
and reports generalization gap.

Usage:
    python3 scripts/evaluate_train_val.py --train outputs/corpus_splits/train_split.json \
        --val outputs/corpus_splits/val_split.json --bundle outputs/moc_loop/generalized_fixes_iter_1.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.oracle_step_debugger import GeneralizedFixBundle


def compute_metrics_on_split(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes KPI metrics on a list of evaluation results."""
    if not results:
        return {}
    
    passed = sum(1 for r in results if r.get("completed_all_steps"))
    survived = [r.get("survival_ratio", 0.0) for r in results]
    mean_survival = sum(survived) / len(survived) if survived else 0.0
    
    return {
        "n_evaluated": len(results),
        "n_passed": passed,
        "pass_rate_percent": round(100.0 * passed / len(results), 2),
        "mean_survival_ratio": round(mean_survival, 4),
        "total_incidents": sum(len(r.get("incidents", [])) for r in results),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate train vs val generalization")
    parser.add_argument(
        "--train-report",
        type=str,
        help="Path to train iteration report JSON (from moc_loop)",
    )
    parser.add_argument(
        "--val-report",
        type=str,
        help="Path to val iteration report JSON (from moc_loop)",
    )
    args = parser.parse_args()
    
    if not args.train_report or not args.val_report:
        print("Usage: --train-report <path> --val-report <path>")
        return
    
    if not os.path.exists(args.train_report):
        print(f"❌ Train report not found: {args.train_report}")
        return
    if not os.path.exists(args.val_report):
        print(f"❌ Val report not found: {args.val_report}")
        return
    
    with open(args.train_report) as f:
        train_report = json.load(f)
    with open(args.val_report) as f:
        val_report = json.load(f)
    
    train_summary = train_report.get("summary", {})
    val_summary = val_report.get("summary", {})
    
    train_survival = train_summary.get("mean_survival_ratio", 0.0)
    val_survival = val_summary.get("mean_survival_ratio", 0.0)
    generalization_gap = train_survival - val_survival
    
    print("\n📊 Train vs. Validation Generalization Report")
    print("=" * 60)
    print(f"\nTrain:")
    print(f"  Pass Rate: {train_summary.get('pass_rate_percent', 0):.2f}%")
    print(f"  Mean Survival: {train_survival * 100:.2f}%")
    print(f"  Total Incidents: {train_summary.get('total_first_error_aborts', 0)}")
    print(f"\nValidation:")
    print(f"  Pass Rate: {val_summary.get('pass_rate_percent', 0):.2f}%")
    print(f"  Mean Survival: {val_survival * 100:.2f}%")
    print(f"  Total Incidents: {val_summary.get('total_first_error_aborts', 0)}")
    print(f"\nGeneralization Gap:")
    print(f"  Δ Survival: {generalization_gap * 100:+.2f}%")
    
    if generalization_gap > 0.05:
        print(f"  ⚠️  WARNING: Large gap detected! Bundle may be overfitting to training data.")
    elif generalization_gap < -0.05:
        print(f"  ✓ Val better than train (unexpected but valid).")
    else:
        print(f"  ✓ Minimal gap — good generalization.")


if __name__ == "__main__":
    main()
