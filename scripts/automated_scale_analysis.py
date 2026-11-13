#!/usr/bin/env python3
import json
import os
import sys
import time
from datetime import datetime

def wait_for_file(path: str, timeout_sec: int = 36000) -> bool:
    """Wait for file to exist and be complete."""
    start = time.time()
    while time.time() - start < timeout_sec:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size > 100:
                return True
        time.sleep(30)
    return False

def load_report(path: str) -> dict:
    """Load JSON report."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f'Error loading {path}: {e}')
        return {}

def analyze_scale(report: dict, label: str) -> dict:
    """Extract key metrics."""
    summary = report.get('summary', {})
    results = report.get('results', [])
    recall_by_tier = {}
    for r in results:
        tier = r.get('complexity_tier', 'UNKNOWN')
        recall = r.get('recall_at_n', {}).get('1', 0.0)
        if tier not in recall_by_tier:
            recall_by_tier[tier] = []
        recall_by_tier[tier].append(recall)
    return {
        'label': label,
        'sets': len(results),
        'recall_at_1': summary.get('mean_recall_at_1', 0),
        'survival': summary.get('mean_survival_ratio', 0),
        'incidents': summary.get('total_incidents', 0),
        'by_tier': recall_by_tier,
    }

def main():
    print('\n===== AUTOMATED SCALE ANALYSIS =====')
    baseline_path = 'outputs/tier_validation/scale_report_5.json'
    beam_path = 'outputs/tier_validation/scale_report_6.json'
    print(f'Loading baseline: {baseline_path}')
    baseline_report = load_report(baseline_path)
    if not baseline_report:
        print('Baseline missing'); return 1
    baseline = analyze_scale(baseline_report, 'BASELINE')
    print(f'Baseline: {baseline["sets"]} sets, Recall@1={baseline["recall_at_1"]*100:.1f}%')
    print(f'Waiting for beam width scale: {beam_path}')
    if wait_for_file(beam_path, timeout_sec=3600):
        print('Beam scale complete')
        beam_report = load_report(beam_path)
        beam = analyze_scale(beam_report, 'BEAM_WIDTH')
        delta = (beam['recall_at_1'] - baseline['recall_at_1']) * 100
        print(f'\nRESULTS:\n  Baseline: {baseline["recall_at_1"]*100:.1f}%\n  New: {beam["recall_at_1"]*100:.1f}%\n  Delta: {delta:+.1f}pp')
        if delta >= 10:
            print('\nVERDICT: SUCCESS - beam_width=16 VALIDATED')
        elif delta >= 5:
            print('\nVERDICT: PARTIAL - investigate further')
        else:
            print('\nVERDICT: INSUFFICIENT - may need revert')
        return 0
    else:
        print('Timeout waiting for beam scale')
        return 1

if __name__ == '__main__':
    sys.exit(main())
