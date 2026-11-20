"""Improvement Loop V2 with Structural Diff Integration (Etapa 3)

Extends ImprovementLoopV2 to inject assembly graph comparison after A2+gate.
Blends A4 visual score with structural quantitative score.

Usage:
    from ldraw_tools.improvement_loop_v2_with_structural import ImprovementLoopV2WithStructural
    
    loop = ImprovementLoopV2WithStructural(
        spec, adapter, output_dir,
        io_path=Path("data.io"),
        sample_id="OMR-30103-1",
        weight_structural=0.3,  # 0.7*A4 + 0.3*structural
    )
    result = loop.run(agent_roles, feedback, llm_config)
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from ldraw_tools.improvement_loop_v2 import ImprovementLoopV2

logger = logging.getLogger(__name__)

__all__ = ["ImprovementLoopV2WithStructural"]


class ImprovementLoopV2WithStructural(ImprovementLoopV2):
    """ImprovementLoopV2 with optional structural_diff integration.
    
    Injects assembly graph comparison (BOM, edges, studs) after A2+gate.
    Blends A4 visual score with structural quantitative score.
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
        tier: str = "MICRO",
    ):
        """Initialize loop with structural diff support.
        
        Args:
            io_path: Original LegoGPT .io file (for GT graph extraction)
            sample_id: e.g., "OMR-30103-1"
            enable_structural_diff: Whether to compute structural diffs
            weight_structural: Weight for structural score (0.3 = 70% A4, 30% struct)
            tier: MICRO/SMALL/MEDIUM (affects weight defaults)
        """
        super().__init__(spec, adapter, output_dir, max_iter, threshold, ldraw_dir, router)
        
        self.io_path = Path(io_path) if io_path else None
        self.sample_id = sample_id or "design"
        self.enable_structural_diff = enable_structural_diff
        self.weight_structural = weight_structural
        self.tier = tier
        
        if tier == "SMALL" and weight_structural == 0.3:
            self.weight_structural = 0.4
        elif tier == "MEDIUM" and weight_structural == 0.3:
            self.weight_structural = 0.5
        
        self._graph_gt = None
        self._graph_gt_path = None
        
        logger.info(
            f"[ImprovementLoopV2WithStructural] Init: "
            f"tier={tier}, enable_structural={enable_structural_diff}, "
            f"weight_structural={self.weight_structural}"
        )
    
    def _ensure_gt_graph(self) -> tuple[Optional[Dict[str, Any]], Optional[Path]]:
        """Build and cache GT graph from .io file."""
        if self._graph_gt is not None:
            return self._graph_gt, self._graph_gt_path
        
        if not self.io_path or not self.io_path.exists():
            logger.warning(f"[StructuralDiff] No .io file ({self.io_path}), skipping GT")
            return None, None
        
        try:
            from scripts.bench.assembly_graph_gt import build_assembly_graph_gt
            
            self._graph_gt = build_assembly_graph_gt(self.io_path, self.sample_id)
            self._graph_gt_path = self.output_dir / f"{self.sample_id}_assembly_graph_GT.json"
            
            with open(self._graph_gt_path, "w") as f:
                json.dump(self._graph_gt, f, indent=2)
            
            logger.info(
                f"[StructuralDiff] Cached GT: {self._graph_gt_path.name} "
                f"({self._graph_gt.get('parts_count', 0)} parts, "
                f"{len(self._graph_gt.get('edges_part', []))} edges)"
            )
            return self._graph_gt, self._graph_gt_path
        except Exception as e:
            logger.warning(f"[StructuralDiff] Failed to build GT graph: {e}")
            return None, None
    
    def _compute_structural_diffs(
        self,
        mpd_gen_path: Path,
        iter_idx: int,
    ) -> Optional[Dict[str, Any]]:
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
            
            graph_gen = build_assembly_graph_gt(
                mpd_gen_path,
                f"{self.sample_id}_iter{iter_idx}"
            )
            
            result = structural_diff.compute_structural_diffs(graph_gt, graph_gen)
            
            graphs_dir = self.output_dir / f"iter_{iter_idx}" / "graphs"
            graphs_dir.mkdir(parents=True, exist_ok=True)
            
            gen_path = graphs_dir / f"assembly_graph_GEN.json"
            with open(gen_path, "w") as f:
                json.dump(graph_gen, f, indent=2)
            
            result["graph_gen_path"] = str(gen_path)
            
            logger.info(
                f"[Iter {iter_idx}] Structural diffs: "
                f"overall={result['scores']['overall_score']:.1f}, "
                f"bom={result['scores']['bom_score']:.1f}, "
                f"edge_score={result['scores']['edge_score']:.1f}, "
                f"diffs={result['summary']['total_diffs']}"
            )
            
            return result
        except Exception as e:
            logger.warning(f"[Iter {iter_idx}] Structural diff failed: {e}")
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
            Enhanced A4 report with blended score.
        """
        from scripts.bench.loop_structural_diff_integration import inject_structural_feedback
        
        enhanced = inject_structural_feedback(
            a4_report,
            structural_result,
            weight_structural=self.weight_structural,
            weight_a4=1.0 - self.weight_structural,
        )
        
        a4_score = a4_report.get("global_score", 50)
        struct_score = structural_result["scores"]["overall_score"]
        blended_score = enhanced["global_score"]
        
        logger.info(
            f"[StructuralDiff] Blend: A4={a4_score:.1f} + struct={struct_score:.1f} "
            f"({self.weight_structural:.0%}) = {blended_score:.1f}"
        )
        
        return enhanced
    
    def _post_judge_hook(
        self,
        report: Dict[str, Any],
        mpd_path: Path,
        iteration: int,
    ) -> Dict[str, Any]:
        """Override: blend A4 report with structural diffs after judge.
        
        Called from parent ImprovementLoopV2.run() hook.
        """
        if not self.enable_structural_diff or self.io_path is None:
            logger.info(f"[Iter {iteration}] Structural diff disabled or no .io; skipping blend")
            return report
        
        structural_result = self._compute_structural_diffs(mpd_path, iteration)
        if structural_result is None:
            logger.warning(f"[Iter {iteration}] Structural diff computation failed; using A4 score as-is")
            return report
        
        return self._blend_a4_with_structural(report, structural_result)
    
    def run(
        self,
        agent_roles: Any,
        feedback: Optional[Dict[str, Any]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run improvement loop with structural diff integration.
        
        Calls parent run() (which invokes _post_judge_hook on each iter for blending),
        then enriches final result with structural diff metadata.
        """
        result = super().run(agent_roles, feedback, llm_config)
        
        if not self.enable_structural_diff or self.io_path is None:
            logger.info("[StructuralDiff] Disabled or no .io; returning parent result")
            return result
        
        try:
            result["structural_diff"] = {
                "enabled": True,
                "tier": self.tier,
                "weight_structural": self.weight_structural,
                "io_path": str(self.io_path),
                "sample_id": self.sample_id,
                "gt_graph_path": str(self._graph_gt_path) if self._graph_gt_path else None,
            }
        except Exception as e:
            logger.warning(f"[StructuralDiff] Failed to enrich result metadata: {e}")
        
        return result
