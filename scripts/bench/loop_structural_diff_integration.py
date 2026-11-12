"""Integration harness for structural_diff in improvement_loop_v2.

Injects ground-truth assembly graph comparison after A2+gate, before A4.
Enriches A4 feedback with structural diffs.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = ["compute_structural_diffs_for_loop", "inject_structural_feedback"]


def compute_structural_diffs_for_loop(
    io_path: Path,
    mpd_gen_path: Path,
    sample_id: str,
    output_dir: Path,
    structural_diff_module: Any = None,
) -> Dict[str, Any]:
    """Build GT graph from .io, gen graph from .mpd, compute diffs.
    
    Args:
        io_path: Original LegoGPT .io file
        mpd_gen_path: Generated .mpd from A2
        sample_id: e.g., "OMR-30103-1"
        output_dir: Where to save intermediate graphs
        structural_diff_module: Optional pre-imported module (else dynamically import)
    
    Returns:
        {
            "diffs": [...],  # From structural_diff
            "scores": {...},
            "summary": {...},
            "graph_gt_path": Path,
            "graph_gen_path": Path,
        }
    """
    # Lazy import to avoid circular deps
    if structural_diff_module is None:
        from scripts.bench import structural_diff as structural_diff_module
    from scripts.bench.assembly_graph_gt import build_assembly_graph_gt
    
    # Build GT graph
    graph_gt = build_assembly_graph_gt(io_path, sample_id)
    graph_gt_path = output_dir / f"{sample_id}_assembly_graph_GT.json"
    graph_gt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(graph_gt_path, "w") as f:
        json.dump(graph_gt, f, indent=2)
    
    # Build gen graph from .mpd
    # (For now, use same builder; in future could have mpd-specific extractor)
    graph_gen = build_assembly_graph_gt(mpd_gen_path, f"{sample_id}_generated")
    graph_gen_path = output_dir / f"{sample_id}_assembly_graph_GEN.json"
    with open(graph_gen_path, "w") as f:
        json.dump(graph_gen, f, indent=2)
    
    # Compute diffs
    result = structural_diff_module.compute_structural_diffs(graph_gt, graph_gen)
    
    # Add paths
    result["graph_gt_path"] = str(graph_gt_path)
    result["graph_gen_path"] = str(graph_gen_path)
    
    return result


def inject_structural_feedback(
    a4_report: Dict[str, Any],
    structural_result: Dict[str, Any],
    weight_structural: float = 0.3,
    weight_a4: float = 0.7,
) -> Dict[str, Any]:
    """Blend structural diffs into A4 report.
    
    Args:
        a4_report: Original A4 judge output {"global_score": X, "diffs": [...]}
        structural_result: Output from compute_structural_diffs_for_loop
        weight_structural: How much to weight structural score (0-1)
        weight_a4: How much to weight A4 score (0-1)
    
    Returns:
        Enhanced A4 report with structural diffs injected.
    """
    a4_score = a4_report.get("global_score", 50.0)
    struct_score = structural_result["scores"]["overall_score"]
    
    # Blend scores (normalized to 0-100)
    blended_score = (weight_a4 * a4_score + weight_structural * struct_score) / (
        weight_a4 + weight_structural
    )
    
    # Collect top structural diffs
    struct_diffs = structural_result.get("diffs", [])
    struct_diffs_sorted = sorted(struct_diffs, key=lambda d: -d["severity"])[:3]
    
    # Enrich with source tag
    for diff in struct_diffs_sorted:
        diff["source"] = "structural_diff"
    
    # Merge diffs: structural first (highest severity), then A4
    a4_diffs = a4_report.get("diffs", [])
    merged_diffs = struct_diffs_sorted + a4_diffs
    
    # Return enhanced report
    enhanced = {
        **a4_report,
        "global_score": blended_score,
        "diffs": merged_diffs,
        "_meta": {
            "a4_score": a4_score,
            "structural_score": struct_score,
            "blended_score": blended_score,
            "structural_diffs_count": len(struct_diffs),
            "weight_structural": weight_structural,
            "weight_a4": weight_a4,
        },
    }
    
    return enhanced


if __name__ == "__main__":
    import sys
    
    # Quick CLI test
    if len(sys.argv) < 4:
        print("Usage: python -m scripts.bench.loop_structural_diff_integration <io_path> <mpd_gen_path> <sample_id>")
        sys.exit(1)
    
    io = Path(sys.argv[1])
    mpd = Path(sys.argv[2])
    sid = sys.argv[3]
    outdir = Path("/tmp/structural_diff_integration")
    outdir.mkdir(exist_ok=True)
    
    result = compute_structural_diffs_for_loop(io, mpd, sid, outdir)
    print(json.dumps(result, indent=2, default=str))
