#!/usr/bin/env python3
"""
Consolidate Loop State into Single Markdown Report
===================================================

Generates a unified LOOP_STATE.md with:
- Current iteration and bundle version
- KPI by tier (train vs val if split exists)
- Key decisions and pending actions
- Timeline

This replaces the scattered ~40 status files with ONE source of truth.

Usage:
    python3 scripts/consolidate_loop_state.py --loop-dir outputs/moc_loop \
        --agentic-dir outputs/agentic_eval --train-dir outputs/corpus_splits
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


def load_json_safe(path: str) -> Optional[Dict[str, Any]]:
    """Safely load JSON, return None if file not found."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def generate_loop_state(
    loop_dir: str,
    agentic_dir: Optional[str] = None,
    train_dir: Optional[str] = None,
) -> str:
    """Generates consolidated loop state markdown."""
    
    # Load latest iteration from loop
    latest_iter = 0
    latest_report = None
    for fname in os.listdir(loop_dir) if os.path.exists(loop_dir) else []:
        if fname.startswith("iter_") and fname.endswith("_report.json"):
            try:
                it_num = int(fname.split("_")[1])
                if it_num > latest_iter:
                    latest_iter = it_num
                    latest_report = load_json_safe(os.path.join(loop_dir, fname))
            except (ValueError, IndexError):
                pass
    
    # Load agentic eval
    agentic_report = None
    if agentic_dir:
        agentic_report = load_json_safe(os.path.join(agentic_dir, "agentic_eval_report.json"))
    
    # Build markdown
    lines = [
        "# 🔄 LegoGPT Improvement Loop State",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "---",
        "",
        "## 📊 Current Status",
        "",
    ]
    
    if latest_report:
        summary = latest_report.get("summary", {})
        lines.extend([
            f"### Oracle Loop (Bucle B — Bundle Synthesis)",
            "",
            f"- **Iteration:** {latest_iter}",
            f"- **MOCs Evaluated:** {summary.get('total_mocs_evaluated', '?')}",
            f"- **Pass Rate:** {summary.get('pass_rate_percent', 0):.2f}%",
            f"- **Mean Survival:** {summary.get('mean_survival_ratio', 0) * 100:.2f}%",
            f"- **Total Incidents:** {summary.get('total_first_error_aborts', 0)}",
            "",
        ])
    else:
        lines.extend([
            "### Oracle Loop (Bucle B — Bundle Synthesis)",
            "",
            "**Status:** No iteration reports found.",
            "",
        ])
    
    if agentic_report:
        by_status = agentic_report.get("by_status", {})
        total = agentic_report.get("total_evaluated", 0)
        lines.extend([
            "### Agentic Pipeline (Bucle A — 6-Agent Inference)",
            "",
            f"- **Validation Set:** {total} MOCs evaluated",
            f"- **Results:**",
        ])
        for status, count in sorted(by_status.items()):
            lines.append(f"  - {status}: {count}")
        lines.append("")
    else:
        lines.extend([
            "### Agentic Pipeline (Bucle A — 6-Agent Inference)",
            "",
            "**Status:** Not yet evaluated.",
            "",
        ])
    
    lines.extend([
        "---",
        "",
        "## 📁 Key Outputs",
        "",
        f"- **Loop Reports:** `{loop_dir}`",
    ])
    if agentic_dir:
        lines.append(f"- **Agentic Eval:** `{agentic_dir}`")
    lines.extend([
        "",
        "## 🚀 Next Steps",
        "",
        "1. Evaluate Bucle A (agentic pipeline) end-to-end if not yet done:",
        f"   ```bash",
        f"   python3 scripts/eval_agentic_end_to_end.py --val-split outputs/corpus_splits/val_split.json --workers 2 --limit 5",
        f"   ```",
        "",
        "2. Compare train vs. validation generalization:",
        f"   ```bash",
        f"   python3 scripts/evaluate_train_val.py --train-report outputs/moc_loop/iter_1_report.json --val-report outputs/moc_loop/iter_2_report.json",
        f"   ```",
        "",
        "3. If regression detected, rollback bundle and re-iterate.",
        "",
        "---",
        "",
        "**For detailed iteration history, see the full reports in the loop/agentic directories.**",
    ])
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Consolidate loop state into single report")
    parser.add_argument("--loop-dir", type=str, default="outputs/moc_loop")
    parser.add_argument("--agentic-dir", type=str, default=None)
    parser.add_argument("--train-dir", type=str, default=None)
    parser.add_argument("--output", type=str, default="LOOP_STATE.md")
    args = parser.parse_args()
    
    markdown = generate_loop_state(args.loop_dir, args.agentic_dir, args.train_dir)
    
    with open(args.output, "w") as f:
        f.write(markdown)
    
    print(f"✅ Loop state consolidated: {args.output}")
