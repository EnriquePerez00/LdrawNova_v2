"""Structural differ: compare 2 assembly graphs (GT vs generated).

Level 1 (Convergence): BOM + part-to-part connectivity
Level 2 (Quality): Stud-exact fidelity

Emits diffs[] compatible with loop_policy.normalize_severity (0-5 scale).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

__all__ = ["compute_structural_diffs", "score_structural_match"]


def _bom_diff(bom_gt: Dict[str, int], bom_gen: Dict[str, int]) -> Tuple[List[Dict[str, Any]], float]:
    """Level 1: BOM comparison.
    
    Returns:
        (diffs[], bom_score: 0-100)
        where bom_score = mean(recall, precision)
    """
    diffs = []
    gt_parts = set(bom_gt.keys())
    gen_parts = set(bom_gen.keys())
    
    missing_parts = gt_parts - gen_parts
    extra_parts = gen_parts - gt_parts
    common_parts = gt_parts & gen_parts
    
    # Missing parts (severity: high)
    for part_id in sorted(missing_parts):
        qty = bom_gt[part_id]
        diffs.append({
            "type": "missing_part",
            "severity": 4,  # high
            "part_id": part_id,
            "expected_qty": qty,
            "actual_qty": 0,
            "description": f"Missing {qty}× {part_id} (required by GT)",
        })
    
    # Extra parts (severity: medium)
    for part_id in sorted(extra_parts):
        qty = bom_gen[part_id]
        diffs.append({
            "type": "extra_part",
            "severity": 2,  # medium
            "part_id": part_id,
            "expected_qty": 0,
            "actual_qty": qty,
            "description": f"Extra {qty}× {part_id} (not in GT)",
        })
    
    # Quantity mismatch (severity: medium)
    for part_id in sorted(common_parts):
        if bom_gt[part_id] != bom_gen[part_id]:
            diffs.append({
                "type": "qty_mismatch",
                "severity": 2,  # medium
                "part_id": part_id,
                "expected_qty": bom_gt[part_id],
                "actual_qty": bom_gen[part_id],
                "description": f"Quantity mismatch: {part_id} (GT={bom_gt[part_id]}, gen={bom_gen[part_id]})",
            })
    
    # Compute BOM score (recall + precision)
    total_gt = sum(bom_gt.values())
    total_gen = sum(bom_gen.values())
    
    # Recall: of GT parts, how many were generated
    recall = sum(bom_gen.get(p, 0) for p in gt_parts if bom_gen.get(p) == bom_gt[p]) / total_gt if total_gt > 0 else 0
    
    # Precision: of generated parts, how many are in GT
    precision = sum(bom_gt.get(p, 0) for p in gen_parts if bom_gt.get(p) == bom_gen[p]) / total_gen if total_gen > 0 else 0
    
    bom_score = 100 * (recall + precision) / 2 if (recall + precision) > 0 else 0
    
    return diffs, bom_score


def _edges_diff(
    edges_gt: List[Tuple[int, int]],
    edges_gen: List[Tuple[int, int]],
    nodes_gt: int,
    nodes_gen: int,
) -> Tuple[List[Dict[str, Any]], float]:
    """Level 1: part-to-part connectivity (pieza-a-pieza).
    
    Returns:
        (diffs[], edge_score: 0-100)
    """
    diffs = []
    
    # Normalize node indices (edges_gen may have different indexing)
    edges_gt_set = set(tuple(sorted(e)) for e in edges_gt)
    edges_gen_set = set(tuple(sorted(e)) for e in edges_gen)
    
    missing_edges = edges_gt_set - edges_gen_set
    extra_edges = edges_gen_set - edges_gt_set
    
    # Missing edges (severity: high)
    for a, b in sorted(missing_edges):
        diffs.append({
            "type": "missing_edge",
            "severity": 4,  # high
            "node_a": a,
            "node_b": b,
            "description": f"Missing connection between part[{a}] and part[{b}]",
        })
    
    # Extra edges (severity: low)
    for a, b in sorted(extra_edges):
        diffs.append({
            "type": "extra_edge",
            "severity": 1,  # low
            "node_a": a,
            "node_b": b,
            "description": f"Spurious connection between part[{a}] and part[{b}]",
        })
    
    # Compute edge score (recall + precision)
    total_gt = len(edges_gt_set)
    total_gen = len(edges_gen_set)
    
    common_edges = edges_gt_set & edges_gen_set
    recall = len(common_edges) / total_gt if total_gt > 0 else 1.0
    precision = len(common_edges) / total_gen if total_gen > 0 else 1.0
    
    edge_score = 100 * (recall + precision) / 2 if (recall + precision) > 0 else 0
    
    return diffs, edge_score


def _stud_fidelity(
    edges_stud_gt: List[Dict[str, Any]],
    edges_stud_gen: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], float]:
    """Level 2: stud-exact connectivity (feature_id + status).
    
    Returns:
        (diffs[], stud_score: 0-100)
    """
    diffs = []
    
    if not edges_stud_gt:
        # No stud data in GT (fallback mode)
        return [], 100.0
    
    if not edges_stud_gen:
        # Generated has no stud data but GT does
        diffs.append({
            "type": "stud_connectivity_missing",
            "severity": 1,  # low (doesn't block convergence)
            "description": f"Stud-level connectivity not available (GT has {len(edges_stud_gt)} contacts)",
        })
        return diffs, 0.0
    
    # Map studs by (occurrence_a, occurrence_b) pair
    gt_studs = {(e["occurrence_a"], e["occurrence_b"]): e for e in edges_stud_gt}
    gen_studs = {(e["occurrence_a"], e["occurrence_b"]): e for e in edges_stud_gen}
    
    matching = 0
    total = max(len(gt_studs), len(gen_studs))
    
    for key in gt_studs:
        if key in gen_studs:
            gt_e = gt_studs[key]
            gen_e = gen_studs[key]
            # Check feature_id match
            if (gt_e.get("feature_a") == gen_e.get("feature_a") and
                gt_e.get("feature_b") == gen_e.get("feature_b")):
                matching += 1
            else:
                diffs.append({
                    "type": "stud_feature_mismatch",
                    "severity": 1,  # low
                    "occurrence_a": key[0],
                    "occurrence_b": key[1],
                    "gt_features": f"{gt_e.get('feature_a')} ↔ {gt_e.get('feature_b')}",
                    "gen_features": f"{gen_e.get('feature_a')} ↔ {gen_e.get('feature_b')}",
                    "description": f"Stud feature mismatch at ({key[0]}, {key[1]})",
                })
    
    stud_score = 100 * matching / total if total > 0 else 100.0
    return diffs, stud_score


def compute_structural_diffs(
    graph_gt: Dict[str, Any],
    graph_gen: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare 2 assembly graphs and emit structured diffs.
    
    Args:
        graph_gt: ground truth graph from assembly_graph_gt.py
        graph_gen: generated graph (assumed same structure)
    
    Returns:
        {
            "diffs": [...],  # list of diffs with severity 0-5
            "scores": {
                "bom_score": 0-100,
                "edge_score": 0-100,
                "stud_score": 0-100,
                "level1_score": mean(bom, edge),  # convergence metric
                "level2_score": stud,  # quality metric
                "overall_score": weighted mean
            },
            "summary": {...}
        }
    """
    # Extract data
    bom_gt = graph_gt.get("bom", {})
    bom_gen = graph_gen.get("bom", {})
    
    edges_part_gt = [tuple(e) for e in graph_gt.get("edges_part", [])]
    edges_part_gen = [tuple(e) for e in graph_gen.get("edges_part", [])]
    
    edges_stud_gt = graph_gt.get("edges_stud", [])
    edges_stud_gen = graph_gen.get("edges_stud", [])
    
    nodes_gt = len(graph_gt.get("nodes", []))
    nodes_gen = len(graph_gen.get("nodes", []))
    
    # Compute diffs at each level
    diffs_bom, bom_score = _bom_diff(bom_gt, bom_gen)
    diffs_edges, edge_score = _edges_diff(edges_part_gt, edges_part_gen, nodes_gt, nodes_gen)
    diffs_stud, stud_score = _stud_fidelity(edges_stud_gt, edges_stud_gen)
    
    all_diffs = diffs_bom + diffs_edges + diffs_stud
    
    # Compute scores
    level1_score = (bom_score + edge_score) / 2  # Convergence metric
    level2_score = stud_score  # Quality metric
    
    # Weighted overall: 80% level1, 20% level2
    overall_score = 0.8 * level1_score + 0.2 * level2_score
    
    return {
        "diffs": all_diffs,
        "scores": {
            "bom_score": round(bom_score, 1),
            "edge_score": round(edge_score, 1),
            "stud_score": round(stud_score, 1),
            "level1_score": round(level1_score, 1),  # Convergence
            "level2_score": round(level2_score, 1),  # Quality
            "overall_score": round(overall_score, 1),
        },
        "summary": {
            "total_diffs": len(all_diffs),
            "missing_parts": len([d for d in all_diffs if d["type"] == "missing_part"]),
            "missing_edges": len([d for d in all_diffs if d["type"] == "missing_edge"]),
            "max_severity": max((d["severity"] for d in all_diffs), default=0),
        },
    }


def score_structural_match(graph_gt: Dict[str, Any], graph_gen: Dict[str, Any]) -> float:
    """Quick: return overall_score (0-100) for a generated design."""
    result = compute_structural_diffs(graph_gt, graph_gen)
    return result["scores"]["overall_score"]


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.bench.structural_diff <graph_gt.json> <graph_gen.json>")
        sys.exit(1)
    
    with open(sys.argv[1]) as f:
        gt = json.load(f)
    with open(sys.argv[2]) as f:
        gen = json.load(f)
    
    result = compute_structural_diffs(gt, gen)
    print(json.dumps(result, indent=2))
