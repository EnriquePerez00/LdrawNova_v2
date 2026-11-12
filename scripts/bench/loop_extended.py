"""Improvement Loop V2 Extended - With Structural Diff Integration.

Extends ImprovementLoopV2 to inject assembly graph comparison after A2+gate.
"""
from ldraw_tools.improvement_loop_v2 import ImprovementLoopV2
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = ["ImprovementLoopV2Extended"]


class ImprovementLoopV2Extended(ImprovementLoopV2):
    """ImprovementLoopV2 with structural_diff integration.
    
    After A2+gate, compares GT assembly graph vs generated graph,
    injects structural diffs into A4 feedback.
    """
    
    def __init__(
        self,
        spec: Dict[str, Any],
        adapter: Any,
        output_dir: Path,
        max_iter: int = 4,
        threshold: float = 85.0,
        ldraw_dir: str = "/Users/I764690/LDraw",
        router: Optional[Any] = None,
        io_path: Optional[Path] = None,
        sample_id: Optional[str] = None,
        enable_structural_diff: bool = True,
        weight_structural: float = 0.3,
    ):
        """Initialize extended loop.
        
        Args:
            io_path: Original LegoGPT .io file (for GT graph extraction)
            sample_id: e.g., "OMR-30103-1"
            enable_structural_diff: Whether to compute structural diffs
            weight_structural: Weight for blending structural score with A4 score
        """
        super().__init__(spec, adapter, output_dir, max_iter, threshold, ldraw_dir, router)
        
        self.io_path = io_path
        self.sample_id = sample_id or "design"
        self.enable_structural_diff = enable_structural_diff
        self.weight_structural = weight_structural
        
        # Cache GT graph (computed once)
        self._graph_gt = None
        self._graph_gt_path = None
    
    def _ensure_gt_graph(self):
        """Build and cache GT graph from .io file."""
        if self._graph_gt is not None:
            return self._graph_gt, self._graph_gt_path
        
        if not self.io_path or not self.io_path.exists():
            logger.warning("[StructuralDiff] No .io file provided, skipping GT graph")
            return None, None
        
        try:
            from scripts.bench.assembly_graph_gt import build_assembly_graph_gt
            
            self._graph_gt = build_assembly_graph_gt(self.io_path, self.sample_id)
            self._graph_gt_path = self.output_dir / f"{self.sample_id}_assembly_graph_GT.json"
            
            import json
            with open(self._graph_gt_path, "w") as f:
                json.dump(self._graph_gt, f, indent=2)
            
            logger.info(f"[StructuralDiff] Cached GT graph: {self._graph_gt_path}")
            return self._graph_gt, self._graph_gt_path
        except Exception as e:
            logger.warning(f"[StructuralDiff] Failed to build GT graph: {e}")
            return None, None
    
    def _compute_structural_diffs(self, mpd_gen_path: Path, iter_idx: int) -> Optional[Dict[str, Any]]:
        """Compute structural diffs for a generated MPD.
        
        Args:
            mpd_gen_path: Path to generated .mpd from A2
            iter_idx: Iteration number (for logging)
        
        Returns:
            Structural diff result or None if computation fails.
        """
        if not self.enable_structural_diff:
            return None
        
        graph_gt, _ = self._ensure_gt_graph()
        if graph_gt is None:
            return None
        
        try:
            from scripts.bench.assembly_graph_gt import build_assembly_graph_gt
            from scripts.bench import structural_diff
            
            # Build gen graph from generated MPD
            graph_gen = build_assembly_graph_gt(
                mpd_gen_path,
                f"{self.sample_id}_iter{iter_idx}"
            )
            
            # Compute diffs
            result = structural_diff.compute_structural_diffs(graph_gt, graph_gen)
            
            # Save intermediate graphs
            import json
            graphs_dir = self.output_dir / f"iter_{iter_idx}" / "graphs"
            graphs_dir.mkdir(parents=True, exist_ok=True)
            
            gen_path = graphs_dir / f"assembly_graph_GEN.json"
            with open(gen_path, "w") as f:
                json.dump(graph_gen, f, indent=2)
            
            result["graph_gen_path"] = str(gen_path)
            
            logger.info(
                f"[Iter {iter_idx}] Structural diffs: "
                f"overall={result['scores']['overall_score']:.1f}, "
                f"diffs={result['summary']['total_diffs']}"
            )
            
            return result
        except Exception as e:
            logger.warning(f"[Iter {iter_idx}] Structural diff computation failed: {e}")
            return None
    
    def _blend_a4_with_structural(
        self,
        a4_report: Dict[str, Any],
        structural_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Blend A4 report with structural diffs.
        
        Args:
            a4_report: Original A4 judge output
            structural_result: Structural diff result
        
        Returns:
            Enhanced A4 report.
        """
        from scripts.bench.loop_structural_diff_integration import inject_structural_feedback
        
        enhanced = inject_structural_feedback(
            a4_report,
            structural_result,
            weight_structural=self.weight_structural,
            weight_a4=1.0,
        )
        
        logger.info(
            f"[StructuralDiff] Blended scores: "
            f"A4={a4_report.get('global_score', 50):.1f}, "
            f"structural={structural_result['scores']['overall_score']:.1f}, "
            f"blended={enhanced['global_score']:.1f}"
        )
        
        return enhanced


if __name__ == "__main__":
    print("Use: from scripts.bench.loop_extended import ImprovementLoopV2Extended")
