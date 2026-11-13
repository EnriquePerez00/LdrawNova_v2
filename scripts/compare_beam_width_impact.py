#!/usr/bin/env python3
"""
Compare Recall@1 before/after beam_width expansion (8 → 16).
"""

import json
import sys

def load_report(path: str) -> dict:
    """Load scale report."""
    with open(path) as f:
        return json.load(f)

def analyze_recall(report: dict, label: str) -> dict:
    """Extract recall metrics from report."""
    summary = report.get("summary", {})
    results = report.get("results", [])
    
    recall_by_tier = {}
    for r in results:
        tier = r.get("complexity_tier", "UNKNOWN")
        recall = r.get("recall_at_n", {}).get("1", 0.0)
        if tier not in recall_by_tier:
            recall_by_tier[tier] = []
        recall_by_tier[tier].append(recall)
    
    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"{'='*80}")
    print(f"\n  Global Recall@1:  {summary.get('mean_recall_at_1', 0)*100:.1f}%")
    print(f"  Survival Ratio:   {summary.get('mean_survival_ratio', 0)*100:.1f}%")
    print(f"  Clean Sets:       {summary.get('clean_set_rate_percent', 0):.1f}%")
    print(f"  Total Incidents:  {summary.get('total_incidents', 0)}")
    print(f"  Sets Evaluated:   {len(results)}")
    
    print(f"\n  By Tier:")
    for tier in sorted(recall_by_tier.keys()):
        recalls = recall_by_tier[tier]
        mean = sum(recalls) / len(recalls) * 100 if recalls else 0
        print(f"    {tier:15s}: {mean:5.1f}%  (n={len(recalls)})")
    
    return {
        "global_recall": summary.get('mean_recall_at_1', 0),
        "survival": summary.get('mean_survival_ratio', 0),
        "clean": summary.get('clean_set_rate_percent', 0),
        "incidents": summary.get('total_incidents', 0),
        "by_tier": recall_by_tier
    }

def main():
    baseline_path = "outputs/tier_validation/scale_report_5.json"
    new_path = "outputs/tier_validation/scale_report_6.json"
    
    print("\n🔄 COMPARING RECALL@1 AFTER BEAM_WIDTH EXPANSION\n")
    
    try:
        baseline_report = load_report(baseline_path)
        baseline = analyze_recall(baseline_report, "BASELINE (beam_width=8)")
    except FileNotFoundError:
        print(f"❌ Baseline not found: {baseline_path}")
        return 1
    
    try:
        new_report = load_report(new_path)
        new = analyze_recall(new_report, "NEW (beam_width=16)")
    except FileNotFoundError:
        print(f"⏳ New report not ready yet: {new_path}")
        return 1
    
    # Calculate deltas
    print(f"\n{'='*80}")
    print("  IMPACT ANALYSIS")
    print(f"{'='*80}")
    
    recall_delta = (new["global_recall"] - baseline["global_recall"]) * 100
    survival_delta = (new["survival"] - baseline["survival"]) * 100
    incidents_delta = new["incidents"] - baseline["incidents"]
    
    print(f"\n  Recall@1 Δ:      {recall_delta:+.1f}pp  ({baseline['global_recall']*100:.1f}% → {new['global_recall']*100:.1f}%)")
    print(f"  Survival Δ:      {survival_delta:+.1f}pp")
    print(f"  Incidents Δ:     {incidents_delta:+d}  ({baseline['incidents']} → {new['incidents']})")
    
    print(f"\n  By Tier (Recall@1):")
    for tier in sorted(baseline["by_tier"].keys()):
        base_recalls = baseline["by_tier"].get(tier, [])
        new_recalls = new["by_tier"].get(tier, [])
        base_mean = sum(base_recalls) / len(base_recalls) * 100 if base_recalls else 0
        new_mean = sum(new_recalls) / len(new_recalls) * 100 if new_recalls else 0
        delta = new_mean - base_mean
        print(f"    {tier:15s}: {delta:+5.1f}pp  ({base_mean:5.1f}% → {new_mean:5.1f}%)")
    
    # Verdict
    print(f"\n{'='*80}")
    if recall_delta >= 10:
        print(f"  ✅ SUCCESSFUL — Recall@1 improved by {recall_delta:.1f}pp")
        print(f"     Action: Keep beam_width=16, project to full corpus")
    elif recall_delta >= 5:
        print(f"  🟡 PARTIAL — Recall@1 improved by {recall_delta:.1f}pp")
        print(f"     Action: Investigate Visual Scorer (Chamfer weighting)")
    else:
        print(f"  🔴 INSUFFICIENT — Recall@1 improved by {recall_delta:.1f}pp only")
        print(f"     Action: Revert beam_width, attack collision pruning")
    print(f"{'='*80}\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
