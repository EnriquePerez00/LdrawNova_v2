
"""Fase D: Harness Probe MICRO - Full loop validation.

Executes the complete learning loop on 5-10 MICRO sets.
Output: learning_probe_micro_results.json with aggregated metrics.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

__all__ = ["MicroProbeHarness", "run_micro_probe"]


@dataclass
class ProbeMetrics:
    sample_id: str
    parts_count: int
    iterations_taken: int
    converged: bool
    final_score: float
    bom_accuracy: float
    edge_recall: float
    edge_precision: float
    max_severity_seen: int
    top_issues: List[str]
    timestamp: str


@dataclass
class ProbeAggregation:
    total_samples: int
    convergence_rate: float
    avg_iterations: float
    avg_bom_accuracy: float
    avg_edge_recall: float
    avg_edge_precision: float
    taxonomy: Dict[str, int]
    failures: List[str]


class MicroProbeHarness:
    def __init__(self, output_dir: Path, max_iter: int = 4):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_iter = max_iter
        self.results: List[ProbeMetrics] = []
        self.failures: List[str] = []
    
    def probe_sample(self, sample_id: str, graph_gt: Dict[str, Any],
                     graph_gen_sequence: List[Dict[str, Any]], a4_scores: List[float]) -> Optional[ProbeMetrics]:
        try:
            from scripts.bench.structural_diff import compute_structural_diffs
            
            converged = False
            final_score = 0.0
            max_severity = 0
            all_issues: List[str] = []
            iter_idx = 0
            
            for iter_idx, (graph_gen, a4_score) in enumerate(zip(graph_gen_sequence, a4_scores)):
                diff_result = compute_structural_diffs(graph_gt, graph_gen)
                sev = diff_result["summary"]["max_severity"]
                max_severity = max(max_severity, sev)
                
                for diff in diff_result.get("diffs", []):
                    all_issues.append(diff.get("type", "unknown"))
                
                struct_score = diff_result["scores"]["overall_score"]
                blended = 0.7 * a4_score + 0.3 * struct_score
                final_score = blended
                
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
            
            metrics = ProbeMetrics(
                sample_id=sample_id,
                parts_count=graph_gt.get("parts_count", 0),
                iterations_taken=iter_idx + 1,
                converged=converged,
                final_score=round(final_score, 1),
                bom_accuracy=round(bom_accuracy, 1),
                edge_recall=round(edge_recall, 1),
                edge_precision=round(edge_precision, 1),
                max_severity_seen=max_severity,
                top_issues=top_issues,
                timestamp=datetime.now().isoformat(),
            )
            
            self.results.append(metrics)
            return metrics
        
        except Exception as e:
            self.failures.append(f"{sample_id}: {e}")
            logger.error(f"[PROBE FAILED] {sample_id}: {e}")
            return None
    
    def aggregate_results(self) -> ProbeAggregation:
        if not self.results:
            return ProbeAggregation(0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, self.failures)
        
        converged_count = sum(1 for r in self.results if r.converged)
        convergence_rate = 100 * converged_count / len(self.results)
        avg_iterations = sum(r.iterations_taken for r in self.results) / len(self.results)
        avg_bom_accuracy = sum(r.bom_accuracy for r in self.results) / len(self.results)
        avg_edge_recall = sum(r.edge_recall for r in self.results) / len(self.results)
        avg_edge_precision = sum(r.edge_precision for r in self.results) / len(self.results)
        
        taxonomy: Dict[str, int] = {}
        for result in self.results:
            for issue in result.top_issues:
                taxonomy[issue] = taxonomy.get(issue, 0) + 1
        
        return ProbeAggregation(
            total_samples=len(self.results),
            convergence_rate=round(convergence_rate, 1),
            avg_iterations=round(avg_iterations, 2),
            avg_bom_accuracy=round(avg_bom_accuracy, 1),
            avg_edge_recall=round(avg_edge_recall, 1),
            avg_edge_precision=round(avg_edge_precision, 1),
            taxonomy=taxonomy,
            failures=self.failures,
        )
    
    def save_results(self) -> Path:
        aggregation = self.aggregate_results()
        
        output = {
            "phase": "D",
            "harness": "micro_probe",
            "timestamp": datetime.now().isoformat(),
            "config": {
                "max_iterations": self.max_iter,
                "total_samples": len(self.results),
                "weight_structural": 0.3,
                "weight_a4": 0.7,
            },
            "samples": [asdict(r) for r in self.results],
            "aggregation": asdict(aggregation),
        }
        
        output_path = self.output_dir / "learning_probe_micro_results.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Results saved: {output_path}")
        return output_path


def run_micro_probe(output_dir=None, num_samples: int = 5):
    """Execute Fase D harness on simulated MICRO samples.
    
    Args:
        output_dir: Where to save results
        num_samples: Number of MICRO sets to probe (5-10)
    
    Returns:
        Path to learning_probe_micro_results.json
    """
    from pathlib import Path
    
    if output_dir is None:
        output_dir = Path("/tmp/phase_d_probe")
    else:
        output_dir = Path(output_dir)
    
    harness = MicroProbeHarness(output_dir, max_iter=4)
    
    for i in range(num_samples):
        sample_id = f"MICRO-{1001 + i}"
        parts_count = 20 + i * 5
        
        graph_gt = {
            "version": 1,
            "sample_id": sample_id,
            "parts_count": parts_count,
            "step_count": 1,
            "nodes": [{"idx": j, "part_id": f"part_{j}.dat", "color": 16, "pos": [0, j*2, 0], "step_idx": 0}
                      for j in range(parts_count)],
            "edges_part": [(j, j+1) for j in range(parts_count - 1)],
            "edges_stud": [],
            "bom": {f"part_{j}.dat": 1 for j in range(parts_count)},
            "connectivity_status": "extracted",
        }
        
        graph_gen_sequence = []
        a4_scores = []
        
        for iter_idx in range(4):
            accuracy = 0.5 + iter_idx * 0.15
            
            graph_gen = {
                "version": 1,
                "sample_id": f"{sample_id}_iter{iter_idx}",
                "parts_count": int(parts_count * accuracy),
                "step_count": 1,
                "nodes": [{"idx": j, "part_id": f"part_{j}.dat", "color": 16, "pos": [0, j*2, 0], "step_idx": 0}
                          for j in range(int(parts_count * accuracy))],
                "edges_part": [(j, j+1) for j in range(max(0, int(parts_count * accuracy) - 1))],
                "edges_stud": [],
                "bom": {f"part_{j}.dat": 1 for j in range(int(parts_count * accuracy))},
                "connectivity_status": "extracted",
            }
            graph_gen_sequence.append(graph_gen)
            a4_score = 50 + iter_idx * 10 + (i % 3) * 2
            a4_scores.append(a4_score)
        
        metrics = harness.probe_sample(sample_id, graph_gt, graph_gen_sequence, a4_scores)
        if metrics:
            print(f"[{sample_id}] ✅ Converged: {metrics.converged}, Score: {metrics.final_score}")
    
    return harness.save_results()


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/phase_d_probe")
    num_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    result_path = run_micro_probe(output_dir, num_samples)
    print(f"\n✅ Harness completed: {result_path}")
