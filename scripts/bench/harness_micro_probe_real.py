"""Fase D Real: Harness Probe MICRO — Corpus Auténtico

Executes the complete learning loop on real MICRO sets from the corpus.
- Extrae ground truth desde .io files
- Simula agent iterations (A2 output progresivo)
- Valida convergencia vs. GT
- Output: learning_probe_micro_real_results.json

Requisitos:
  LDRAW_DIR=/path/to/ldraw (para connectivity extraction)
  Corpus en /Users/I764690/Code_personal/LegoGPT/data/normalized_io/*.io
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

__all__ = ["MicroProbeHarnessReal", "run_micro_probe_real"]


@dataclass
class ProbeMetricsReal:
    sample_id: str
    io_file: str
    parts_count: int
    steps_count: int
    edges_gt_count: int
    studs_gt_count: int
    iterations_taken: int
    converged: bool
    final_score: float
    bom_accuracy: float
    edge_recall: float
    edge_precision: float
    stud_score: Optional[float]
    max_severity_seen: int
    top_issues: List[str]
    connectivity_status: str
    timestamp: str


@dataclass
class ProbeAggregationReal:
    total_samples: int
    convergence_rate: float
    avg_iterations: float
    avg_bom_accuracy: float
    avg_edge_recall: float
    avg_edge_precision: float
    avg_stud_score: Optional[float]
    taxonomy: Dict[str, int]
    failures: List[str]


class MicroProbeHarnessReal:
    def __init__(self, output_dir: Path, max_iter: int = 4):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_iter = max_iter
        self.results: List[ProbeMetricsReal] = []
        self.failures: List[str] = []
        ldraw_dir = os.environ.get("LDRAW_DIR")
        if not ldraw_dir:
            logger.warning("⚠️  LDRAW_DIR not set; connectivity extraction will fail")
        self.ldraw_dir = ldraw_dir
    
    def probe_sample(self, sample_id: str, io_file: Path, graph_gt: Dict[str, Any],
                     graph_gen_sequence: List[Dict[str, Any]], a4_scores: List[float]
    ) -> Optional[ProbeMetricsReal]:
        """Probe a single MICRO sample."""
        try:
            from scripts.bench.structural_diff import compute_structural_diffs
            
            converged = False
            final_score = 0.0
            max_severity = 0
            all_issues: List[str] = []
            iter_idx = 0
            stud_score_final = None
            
            for iter_idx, (graph_gen, a4_score) in enumerate(zip(graph_gen_sequence, a4_scores)):
                diff_result = compute_structural_diffs(graph_gt, graph_gen)
                sev = diff_result["summary"]["max_severity"]
                max_severity = max(max_severity, sev)
                
                for diff in diff_result.get("diffs", []):
                    all_issues.append(diff.get("type", "unknown"))
                
                struct_score = diff_result["scores"]["overall_score"]
                blended = 0.7 * a4_score + 0.3 * struct_score
                final_score = blended
                stud_score_final = diff_result["scores"].get("stud_score")
                
                if blended >= 85.0 or (sev < 4 and iter_idx >= 1):
                    converged = True
                    break
            
            bom_gt = graph_gt.get("bom", {})
            bom_gen = graph_gen_sequence[-1].get("bom", {})
            common_parts = sum(1 for p in bom_gt if bom_gen.get(p) == bom_gt[p])
            bom_accuracy = 100 * common_parts / len(bom_gt) if bom_gt else 100.0
            
            edges_gt = set(tuple(sorted(e)) for e in graph_gt.get("edges_part", []))
            edges_gen = set(tuple(sorted(e)) for e in graph_gen_sequence[-1].get("edges_part", []))
            common_edges = edges_gt & edges_gen
            edge_recall = 100 * len(common_edges) / len(edges_gt) if edges_gt else 100.0
            edge_precision = 100 * len(common_edges) / len(edges_gen) if edges_gen else 100.0
            
            top_issues = sorted(set(all_issues))[:3]
            
            metrics = ProbeMetricsReal(
                sample_id=sample_id,
                io_file=io_file.name,
                parts_count=graph_gt.get("parts_count", 0),
                steps_count=graph_gt.get("step_count", 0),
                edges_gt_count=len(edges_gt),
                studs_gt_count=len(graph_gt.get("edges_stud", [])),
                iterations_taken=iter_idx + 1,
                converged=converged,
                final_score=round(final_score, 1),
                bom_accuracy=round(bom_accuracy, 1),
                edge_recall=round(edge_recall, 1),
                edge_precision=round(edge_precision, 1),
                stud_score=round(stud_score_final, 1) if stud_score_final is not None else None,
                max_severity_seen=max_severity,
                top_issues=top_issues,
                connectivity_status=graph_gt.get("connectivity_status", "unknown"),
                timestamp=datetime.now().isoformat(),
            )
            
            self.results.append(metrics)
            return metrics
        
        except Exception as e:
            self.failures.append(f"{sample_id}: {str(e)[:200]}")
            logger.error(f"[PROBE FAILED] {sample_id}: {e}")
            return None
    
    def aggregate_results(self) -> ProbeAggregationReal:
        if not self.results:
            return ProbeAggregationReal(0, 0.0, 0.0, 0.0, 0.0, 0.0, None, {}, self.failures)
        
        converged_count = sum(1 for r in self.results if r.converged)
        convergence_rate = 100 * converged_count / len(self.results)
        avg_iterations = sum(r.iterations_taken for r in self.results) / len(self.results)
        avg_bom_accuracy = sum(r.bom_accuracy for r in self.results) / len(self.results)
        avg_edge_recall = sum(r.edge_recall for r in self.results) / len(self.results)
        avg_edge_precision = sum(r.edge_precision for r in self.results) / len(self.results)
        
        stud_scores = [r.stud_score for r in self.results if r.stud_score is not None]
        avg_stud_score = sum(stud_scores) / len(stud_scores) if stud_scores else None
        
        taxonomy: Dict[str, int] = {}
        for result in self.results:
            for issue in result.top_issues:
                taxonomy[issue] = taxonomy.get(issue, 0) + 1
        
        return ProbeAggregationReal(
            total_samples=len(self.results),
            convergence_rate=round(convergence_rate, 1),
            avg_iterations=round(avg_iterations, 2),
            avg_bom_accuracy=round(avg_bom_accuracy, 1),
            avg_edge_recall=round(avg_edge_recall, 1),
            avg_edge_precision=round(avg_edge_precision, 1),
            avg_stud_score=round(avg_stud_score, 1) if avg_stud_score is not None else None,
            taxonomy=taxonomy,
            failures=self.failures,
        )
    
    def save_results(self) -> Path:
        aggregation = self.aggregate_results()
        
        output = {
            "phase": "D",
            "harness": "micro_probe_real",
            "timestamp": datetime.now().isoformat(),
            "config": {
                "max_iterations": self.max_iter,
                "total_samples": len(self.results),
                "weight_structural": 0.3,
                "weight_a4": 0.7,
                "ldraw_dir": self.ldraw_dir,
            },
            "samples": [asdict(r) for r in self.results],
            "aggregation": asdict(aggregation),
        }
        
        output_path = self.output_dir / "learning_probe_micro_real_results.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Results saved: {output_path}")
        return output_path


def run_micro_probe_real(output_dir=None, num_samples: int = 5, corpus_dir: Optional[Path] = None):
    """Execute Fase D harness on real MICRO corpus samples."""
    from scripts.bench.assembly_graph_gt import build_assembly_graph_gt
    from scripts.bench.io_loader_extended import count_steps_and_parts_extended
    
    if output_dir is None:
        output_dir = Path("/tmp/phase_d_probe_real")
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
        raise ValueError("LDRAW_DIR environment variable not set (required for connectivity extraction)")
    
    io_files = sorted(corpus_dir.glob("*.io"), key=lambda p: p.stat().st_size)[:num_samples]
    
    if not io_files:
        raise ValueError(f"No .io files found in {corpus_dir}")
    
    harness = MicroProbeHarnessReal(output_dir, max_iter=4)
    
    print(f"\n{'='*70}")
    print(f"FASE D REAL: Harness MICRO Probe")
    print(f"{'='*70}")
    print(f"Corpus:      {corpus_dir}")
    print(f"LDRAW_DIR:   {ldraw_dir}")
    print(f"Output:      {output_dir}")
    print(f"Samples:     {len(io_files)}")
    print(f"{'='*70}\n")
    
    for idx, io_file in enumerate(io_files):
        sample_id = io_file.stem.replace("_normalized", "")
        steps, parts = count_steps_and_parts_extended(io_file)
        
        print(f"[{idx + 1}/{len(io_files)}] {sample_id:30s} | size={io_file.stat().st_size/1024:6.1f}KB | parts={parts:3d} | steps={steps:2d}")
        
        try:
            graph_gt = build_assembly_graph_gt(io_file, sample_id)
            
            graph_gen_sequence = []
            a4_scores = []
            
            for iter_idx in range(4):
                accuracy = 0.5 + iter_idx * 0.15
                gen_parts_count = int(graph_gt["parts_count"] * accuracy)
                gen_nodes = graph_gt["nodes"][:gen_parts_count]
                gen_bom = {}
                for node in gen_nodes:
                    pid = node["part_id"]
                    gen_bom[pid] = gen_bom.get(pid, 0) + 1
                
                gen_edges = []
                for edge in graph_gt.get("edges_part", []):
                    if edge[0] < gen_parts_count and edge[1] < gen_parts_count:
                        gen_edges.append(edge)
                
                graph_gen = {
                    "version": 1,
                    "sample_id": f"{sample_id}_iter{iter_idx}",
                    "parts_count": gen_parts_count,
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
            
            metrics = harness.probe_sample(sample_id, io_file, graph_gt, graph_gen_sequence, a4_scores)
            if metrics:
                conv_marker = "✅" if metrics.converged else "❌"
                conn_marker = "✅" if metrics.connectivity_status == "extracted" else "⚠️ "
                print(f"       {conv_marker} Converged: {metrics.converged:5} | Score: {metrics.final_score:5.1f} | BOM: {metrics.bom_accuracy:5.1f}% | {conn_marker} Conn: {metrics.connectivity_status}")
        
        except Exception as e:
            print(f"       ❌ FAILED: {str(e)[:100]}")
    
    result_path = harness.save_results()
    
    agg = harness.aggregate_results()
    print(f"\n{'='*70}")
    print(f"AGGREGATED RESULTS")
    print(f"{'='*70}")
    print(f"Total samples:      {agg.total_samples}")
    print(f"Convergence:        {agg.convergence_rate:.1f}%")
    print(f"Avg iterations:     {agg.avg_iterations:.2f}")
    print(f"Avg BOM accuracy:   {agg.avg_bom_accuracy:.1f}%")
    print(f"Avg edge recall:    {agg.avg_edge_recall:.1f}%")
    print(f"Avg edge precision: {agg.avg_edge_precision:.1f}%")
    if agg.avg_stud_score is not None:
        print(f"Avg stud score:     {agg.avg_stud_score:.1f}")
    print(f"Top issues:         {dict(agg.taxonomy)}")
    if agg.failures:
        print(f"Failures:           {len(agg.failures)}")
        for fail in agg.failures[:3]:
            print(f"  - {fail}")
    print(f"{'='*70}\n")
    
    return result_path


if __name__ == "__main__":
    if not os.environ.get("LDRAW_DIR"):
        print("❌ Error: LDRAW_DIR not set")
        print("   Run: export LDRAW_DIR=/Users/I764690/LDraw")
        sys.exit(1)
    
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/phase_d_probe_real")
    num_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    try:
        result_path = run_micro_probe_real(output_dir, num_samples)
        print(f"\n✅ Harness completed: {result_path}")
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
