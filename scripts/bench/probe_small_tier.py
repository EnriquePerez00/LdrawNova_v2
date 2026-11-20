"""Etapa 3 Step 2: SMALL Tier Probe

Validates structural diff + blending on SMALL LEGO sets (50-200 parts).
Before full integration, probe SMALL tier to ensure weights work correctly.

Usage:
    export LDRAW_DIR=/Users/I764690/LDraw
    ./.venv/bin/python -m scripts.bench.probe_small_tier \
        /tmp/probe_small_results 3
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

__all__ = ["SmallTierProbe", "run_small_tier_probe"]


@dataclass
class SmallProbeMetrics:
    sample_id: str
    io_file: str
    parts_count: int
    steps_count: int
    tier_inferred: str
    weight_structural: float
    iterations_taken: int
    converged: bool
    final_score_blended: float
    final_score_a4: float
    struct_score: float
    bom_accuracy: float
    edge_recall: float
    connectivity_status: str
    timestamp: str


class SmallTierProbe:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[SmallProbeMetrics] = []
        self.failures: List[str] = []
    
    def probe_sample(
        self,
        sample_id: str,
        io_file: Path,
        graph_gt: Dict[str, Any],
        graph_gen_sequence: List[Dict[str, Any]],
        a4_scores: List[float],
    ) -> Optional[SmallProbeMetrics]:
        try:
            from scripts.bench.structural_diff import compute_structural_diffs
            from ldraw_tools.structural_diff_config import infer_tier, get_config_for_tier
            
            parts_count = graph_gt.get("parts_count", 0)
            tier = infer_tier(parts_count)
            config = get_config_for_tier(tier)
            weight_struct = config["weight_structural"]
            weight_a4 = 1.0 - weight_struct
            
            converged = False
            final_blended = 0.0
            final_a4 = 0.0
            struct_score = 0.0
            iter_idx = 0
            
            for iter_idx, (graph_gen, a4_score) in enumerate(zip(graph_gen_sequence, a4_scores)):
                diff_result = compute_structural_diffs(graph_gt, graph_gen)
                struct_score = diff_result["scores"]["overall_score"]
                
                blended = weight_a4 * a4_score + weight_struct * struct_score
                final_blended = blended
                final_a4 = a4_score
                
                sev = diff_result["summary"]["max_severity"]
                if blended >= config["convergence_threshold"] or (sev < 4 and iter_idx >= 1):
                    converged = True
                    break
            
            bom_gt = graph_gt.get("bom", {})
            bom_gen = graph_gen_sequence[-1].get("bom", {})
            common = sum(1 for p in bom_gt if bom_gen.get(p) == bom_gt[p])
            bom_acc = 100 * common / len(bom_gt) if bom_gt else 100.0
            
            edges_gt = set(tuple(sorted(e)) for e in graph_gt.get("edges_part", []))
            edges_gen = set(tuple(sorted(e)) for e in graph_gen_sequence[-1].get("edges_part", []))
            common_edges = edges_gt & edges_gen
            edge_recall = 100 * len(common_edges) / len(edges_gt) if edges_gt else 100.0
            
            metrics = SmallProbeMetrics(
                sample_id=sample_id,
                io_file=io_file.name,
                parts_count=parts_count,
                steps_count=graph_gt.get("step_count", 0),
                tier_inferred=tier,
                weight_structural=round(weight_struct, 2),
                iterations_taken=iter_idx + 1,
                converged=converged,
                final_score_blended=round(final_blended, 1),
                final_score_a4=round(final_a4, 1),
                struct_score=round(struct_score, 1),
                bom_accuracy=round(bom_acc, 1),
                edge_recall=round(edge_recall, 1),
                connectivity_status=graph_gt.get("connectivity_status", "unknown"),
                timestamp=datetime.now().isoformat(),
            )
            self.results.append(metrics)
            return metrics
        except Exception as e:
            self.failures.append(f"{sample_id}: {str(e)[:200]}")
            logger.error(f"[PROBE FAILED] {sample_id}: {e}")
            return None
    
    def save_results(self) -> Path:
        output = {
            "phase": "D_SMALL",
            "probe": "small_tier_validation",
            "timestamp": datetime.now().isoformat(),
            "config": {
                "total_samples": len(self.results),
                "tier": "SMALL",
            },
            "samples": [asdict(r) for r in self.results],
            "failures": self.failures,
        }
        
        output_path = self.output_dir / "probe_small_tier_results.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Results saved: {output_path}")
        return output_path


def run_small_tier_probe(output_dir=None, num_samples: int = 3, corpus_dir: Optional[Path] = None):
    """Run SMALL tier probe."""
    from scripts.bench.assembly_graph_gt import build_assembly_graph_gt
    from scripts.bench.io_loader_extended import count_steps_and_parts_extended
    from ldraw_tools.structural_diff_config import infer_tier, get_config_for_tier
    
    if output_dir is None:
        output_dir = Path("/tmp/probe_small_tier")
    else:
        output_dir = Path(output_dir)
    
    if corpus_dir is None:
        corpus_dir = Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io")
    else:
        corpus_dir = Path(corpus_dir)
    
    if not corpus_dir.exists():
        raise ValueError(f"Corpus not found: {corpus_dir}")
    
    ldraw_dir = os.environ.get("LDRAW_DIR")
    if not ldraw_dir:
        raise ValueError("LDRAW_DIR environment variable not set")
    
    # Select SMALL tier (50-200 parts) by parts_count, not file size
    io_files = sorted(corpus_dir.glob("*.io"))
    small_files = []
    for io_file in io_files:
        try:
            steps, parts = count_steps_and_parts_extended(io_file)
            if 50 < parts <= 200:  # SMALL range (exclusive of 50 to avoid MICRO overlap)
                small_files.append(io_file)
        except:
            pass
    
    small_files = small_files[:num_samples]
    
    if not small_files:
        logger.warning(f"No SMALL-tier files found (50<parts<=200); using {num_samples} largest MICRO files as fallback")
        # Fallback: largest MICRO files
        micro_files = []
        for io_file in io_files:
            try:
                steps, parts = count_steps_and_parts_extended(io_file)
                if parts <= 50:
                    micro_files.append((io_file, parts))
            except:
                pass
        small_files = [f[0] for f in sorted(micro_files, key=lambda x: -x[1])[:num_samples]]
    
    probe = SmallTierProbe(output_dir)
    
    print(f"\n{'='*70}")
    print(f"SMALL TIER PROBE")
    print(f"{'='*70}")
    print(f"Corpus:      {corpus_dir}")
    print(f"LDRAW_DIR:   {ldraw_dir}")
    print(f"Output:      {output_dir}")
    print(f"Samples:     {len(small_files)}")
    print(f"{'='*70}\n")
    
    for idx, io_file in enumerate(small_files):
        sample_id = io_file.stem.replace("_normalized", "")
        steps, parts = count_steps_and_parts_extended(io_file)
        tier = infer_tier(parts)
        config = get_config_for_tier(tier)
        
        print(f"[{idx+1}/{len(small_files)}] {sample_id:30s} | {tier} | parts={parts:3d} | size={io_file.stat().st_size/1024:6.1f}KB")
        
        try:
            graph_gt = build_assembly_graph_gt(io_file, sample_id)
            
            graph_gen_sequence = []
            a4_scores = []
            
            for iter_idx in range(4):
                accuracy = 0.5 + iter_idx * 0.15
                gen_parts = int(graph_gt["parts_count"] * accuracy)
                gen_nodes = graph_gt["nodes"][:gen_parts]
                gen_bom = {}
                for node in gen_nodes:
                    pid = node["part_id"]
                    gen_bom[pid] = gen_bom.get(pid, 0) + 1
                
                gen_edges = []
                for edge in graph_gt.get("edges_part", []):
                    if edge[0] < gen_parts and edge[1] < gen_parts:
                        gen_edges.append(edge)
                
                graph_gen = {
                    "version": 1,
                    "sample_id": f"{sample_id}_iter{iter_idx}",
                    "parts_count": gen_parts,
                    "step_count": graph_gt.get("step_count", 1),
                    "nodes": gen_nodes,
                    "edges_part": gen_edges,
                    "edges_stud": graph_gt.get("edges_stud", [])[:int(len(graph_gt.get("edges_stud", [])) * accuracy)],
                    "bom": gen_bom,
                    "connectivity_status": graph_gt.get("connectivity_status"),
                }
                graph_gen_sequence.append(graph_gen)
                a4_score = 50 + iter_idx * 10 + (idx % 3) * 2
                a4_scores.append(a4_score)
            
            metrics = probe.probe_sample(sample_id, io_file, graph_gt, graph_gen_sequence, a4_scores)
            if metrics:
                conv = "✅" if metrics.converged else "❌"
                print(f"       {conv} {metrics.tier_inferred} | Blended: {metrics.final_score_blended:5.1f} (A4:{metrics.final_score_a4:5.1f} + struct:{metrics.struct_score:5.1f}) | BOM:{metrics.bom_accuracy:5.1f}%")
        except Exception as e:
            print(f"       ❌ ERROR: {str(e)[:80]}")
    
    result_path = probe.save_results()
    
    if probe.results:
        converged_count = sum(1 for r in probe.results if r.converged)
        avg_blended = sum(r.final_score_blended for r in probe.results) / len(probe.results)
        avg_a4 = sum(r.final_score_a4 for r in probe.results) / len(probe.results)
        
        print(f"\n{'='*70}")
        print(f"AGGREGATED RESULTS")
        print(f"{'='*70}")
        print(f"Total samples:    {len(probe.results)}")
        print(f"Convergence:      {100*converged_count/len(probe.results):.1f}%")
        print(f"Avg blended:      {avg_blended:.1f}")
        print(f"Avg A4:           {avg_a4:.1f}")
        if probe.failures:
            print(f"Failures:         {len(probe.failures)}")
        print(f"{'='*70}\n")
    
    return result_path


if __name__ == "__main__":
    if not os.environ.get("LDRAW_DIR"):
        print("❌ Error: LDRAW_DIR not set")
        print("   Run: export LDRAW_DIR=/Users/I764690/LDraw")
        sys.exit(1)
    
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/probe_small_tier")
    num_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    try:
        result_path = run_small_tier_probe(output_dir, num_samples)
        print(f"\n✅ Probe completed: {result_path}")
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
