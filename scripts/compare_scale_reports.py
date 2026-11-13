#!/usr/bin/env python3
"""
Compare scale reports: before-fix vs after-fix.

Compara dos reportes de scale para medir el impacto de las correcciones.
"""

import json
import sys
from pathlib import Path
from collections import Counter

def compare_reports(baseline_path: str, current_path: str):
    """Compara dos scale reports."""
    
    baseline = json.load(open(baseline_path))
    current = json.load(open(current_path))
    
    print("\n" + "="*80)
    print(f"📊 SCALE REPORTS COMPARISON")
    print("="*80)
    
    print(f"\nBaseline: {Path(baseline_path).name}")
    print(f"Current:  {Path(current_path).name}")
    
    # Extraer summaries
    base_sum = baseline.get("summary", {})
    curr_sum = current.get("summary", {})
    
    # Métricas globales
    print("\n" + "-"*80)
    print("GLOBAL METRICS")
    print("-"*80)
    
    metrics = [
        ("Total Sets", "total"),
        ("Pass Rate (%)", "pass_rate_percent"),
        ("Mean Survival Ratio", "mean_survival_ratio", lambda x: x*100),
        ("Median Survival Ratio", "median_survival_ratio", lambda x: x*100),
        ("Clean Set Rate (%)", "clean_set_rate_percent"),
        ("Mean Recall@1", "mean_recall_at_1", lambda x: x*100),
        ("Total Incidents", "total_incidents"),
        ("Mean Time/Set (s)", "mean_elapsed_sec"),
    ]
    
    print(f"{'Metric':<30} | {'Baseline':>12} | {'Current':>12} | {'Change':>12}")
    print("-"*80)
    
    for metric_tuple in metrics:
        metric_name = metric_tuple[0]
        key = metric_tuple[1]
        transform = metric_tuple[2] if len(metric_tuple) > 2 else lambda x: x
        
        base_val = base_sum.get(key, 0)
        curr_val = curr_sum.get(key, 0)
        base_disp = transform(base_val)
        curr_disp = transform(curr_val)
        
        if isinstance(base_disp, float):
            delta = curr_disp - base_disp
            delta_str = f"{delta:+.1f}"
            base_str = f"{base_disp:.1f}"
            curr_str = f"{curr_disp:.1f}"
        else:
            delta = int(curr_disp - base_disp)
            delta_str = f"{delta:+d}"
            base_str = f"{int(base_disp)}"
            curr_str = f"{int(curr_disp)}"
        
        print(f"{metric_name:<30} | {base_str:>12} | {curr_str:>12} | {delta_str:>12}")
    
    # Root causes comparison
    print("\n" + "-"*80)
    print("ROOT CAUSES (Top 8)")
    print("-"*80)
    
    base_causes = baseline.get("root_causes", {}).get("causes", {})
    curr_causes = current.get("root_causes", {}).get("causes", {})
    
    # Combinar todas las causas
    all_causes = set(base_causes.keys()) | set(curr_causes.keys())
    
    print(f"{'Cause':<40} | {'Baseline':>8} | {'Current':>8} | {'Change':>8}")
    print("-"*80)
    
    # Top causes en baseline
    for cause, base_count in sorted(base_causes.items(), key=lambda x: -x[1])[:8]:
        curr_count = curr_causes.get(cause, 0)
        delta = curr_count - base_count
        print(f"{cause:<40} | {base_count:>8} | {curr_count:>8} | {delta:>+8}")
    
    # Resumen de impacto
    print("\n" + "="*80)
    print("📈 IMPACT SUMMARY")
    print("="*80)
    
    total_delta = curr_sum.get("total_incidents", 0) - base_sum.get("total_incidents", 0)
    total_pct = (total_delta / base_sum.get("total_incidents", 1) * 100) if base_sum.get("total_incidents") else 0
    
    print(f"\nIncidents: {base_sum.get('total_incidents', 0)} → {curr_sum.get('total_incidents', 0)} ({total_delta:+d}, {total_pct:+.1f}%)")
    
    # MISSING reduction
    base_missing = base_causes.get("MISSING_CONNECTIVITY_PORT", 0)
    curr_missing = curr_causes.get("MISSING_CONNECTIVITY_PORT", 0)
    missing_delta = curr_missing - base_missing
    missing_pct = (missing_delta / base_missing * 100) if base_missing > 0 else 0
    
    print(f"MISSING_CONNECTIVITY: {base_missing} → {curr_missing} ({missing_delta:+d}, {missing_pct:+.1f}%) {'✅' if missing_delta < 0 else '❌'}")
    
    # Survival improvement
    base_survival = base_sum.get("mean_survival_ratio", 0)
    curr_survival = curr_sum.get("mean_survival_ratio", 0)
    survival_delta = (curr_survival - base_survival) * 100  # in percentage points
    
    print(f"Mean Survival: {base_survival*100:.1f}% → {curr_survival*100:.1f}% ({survival_delta:+.1f}pp) {'✅' if survival_delta > 0 else '❌'}")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    # Find reports
    report_dir = Path("outputs/tier_validation")
    scale_reports = sorted(report_dir.glob("scale_report_*.json"))
    
    if len(scale_reports) < 2:
        print("❌ Need at least 2 scale reports to compare")
        print(f"Found: {len(scale_reports)}")
        sys.exit(1)
    
    # Use last two
    baseline = scale_reports[-2]
    current = scale_reports[-1]
    
    print(f"Baseline (older): {baseline}")
    print(f"Current (newer): {current}")
    
    compare_reports(str(baseline), str(current))
