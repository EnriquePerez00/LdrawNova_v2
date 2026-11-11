"""Improvement Loop V2 - Full pipeline with rendering, validators, persistence."""
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from datetime import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from ldraw_tools.loop_state_manager import LoopStateManager, create_feedback_for_next_iteration
from ldraw_tools.renderer import LeoCADRenderer, ColorExtractor, OverlapDetector
from ldraw_tools.validators import GeometryValidator, BOMValidator, ColorValidator

logger = logging.getLogger(__name__)


@dataclass
class IterationResult:
    iteration: int
    score: float
    axes: Dict[str, float]
    diffs_count: int
    severity: int
    converged: bool
    reason: str
    top_diffs: List
    timestamp: str


class ImprovementLoopV2:
    """Full improvement loop with rendering, validation, and persistence."""
    
    def __init__(
        self,
        spec: Dict[str, Any],
        adapter: Any,
        output_dir: Path,
        max_iter: int = 4,
        threshold: float = 85.0,
        ldraw_dir: str = "/Users/I764690/LDraw",
    ):
        self.spec = spec
        self.adapter = adapter
        self.output_dir = Path(output_dir)
        self.max_iter = max_iter
        self.threshold = threshold
        self.iterations = []
        self.best = None
        
        # Initialize managers
        self.state_mgr = LoopStateManager(self.output_dir)
        self.renderer = LeoCADRenderer(ldraw_dir=ldraw_dir)
        self.color_extractor = ColorExtractor()
        self.overlap_detector = OverlapDetector()
        
        # Validators
        self.geometry_validator = GeometryValidator()
        self.bom_validator = BOMValidator()
        self.color_validator = ColorValidator()
        
        # Initialize state
        self.state = self.state_mgr.initialize_state(
            profile=adapter.profile_name,
            slug=str(self.output_dir.name),
            max_iterations=max_iter,
            threshold=threshold,
        )
    
    def run(
        self,
        agent_roles: Any,
        feedback: Optional[Dict[str, Any]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run improvement loop with full pipeline."""
        start = time.time()
        logger.info(f"[Loop] Starting: max_iter={self.max_iter}, threshold={self.threshold}")
        
        for i in range(self.max_iter):
            iter_dir = self.output_dir / f"iter_{i}"
            iter_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"\n[Iter {i}] ===== Starting iteration =====")
            
            # -------- A2: Design --------
            try:
                logger.info(f"[Iter {i}] A2: Designing...")
                fb = feedback if i == 0 else (self.iterations[-1].top_diffs if self.iterations else None)
                plan, mpd = agent_roles.design_3d(self.spec, {"diffs": fb} if fb else None, self.adapter, iter_dir, llm_config)
                logger.info(f"[Iter {i}] A2: Generated {mpd.name}")
            except Exception as e:
                logger.error(f"[Iter {i}] A2 failed: {e}")
                continue
            
            # -------- Validators: Geometry + BOM --------
            renders_dir = iter_dir / "renders"
            try:
                logger.info(f"[Iter {i}] Validating geometry...")
                valid_geom, geom_errors = self.geometry_validator.validate_mpd(mpd, self.adapter.get_whitelist())
                if geom_errors:
                    logger.warning(f"[Iter {i}] Geometry issues: {geom_errors[:2]}")
                
                logger.info(f"[Iter {i}] Extracting BOM...")
                bom = self.bom_validator.extract_bom(mpd)
                valid_bom, bom_errors = self.bom_validator.validate_bom_constraints(bom, self.adapter.get_bom_constraints())
                if bom_errors:
                    logger.warning(f"[Iter {i}] BOM issues: {bom_errors[:2]}")
            except Exception as e:
                logger.warning(f"[Iter {i}] Validation error: {e}")
            
            # -------- Rendering: LeoCAD 4 views --------
            try:
                logger.info(f"[Iter {i}] Rendering 4 views...")
                rendered = self.renderer.render_views(mpd, renders_dir)
                logger.info(f"[Iter {i}] Rendered: {list(rendered.keys())}")
            except Exception as e:
                logger.warning(f"[Iter {i}] Rendering failed: {e}")
                rendered = {}
            
            # -------- Color Extraction --------
            try:
                if rendered.get("home"):
                    colors = self.color_extractor.extract_dominant_colors(rendered["home"], num_colors=3)
                    logger.info(f"[Iter {i}] Dominant colors: {colors}")
                    valid_color, color_errors = self.color_validator.validate_colors(colors, tolerance=30.0)
            except Exception as e:
                logger.warning(f"[Iter {i}] Color extraction failed: {e}")
            
            # -------- Overlap Detection --------
            try:
                if rendered.get("home"):
                    overlaps = self.overlap_detector.detect_overlaps(rendered["home"])
                    if overlaps:
                        logger.info(f"[Iter {i}] Potential overlaps detected: {len(overlaps)}")
            except Exception as e:
                logger.warning(f"[Iter {i}] Overlap detection failed: {e}")
            
            # -------- A3: Describe Render Blind --------
            spec_r = {}
            try:
                logger.info(f"[Iter {i}] A3: Describing renders (blind)...")
                spec_r = agent_roles.describe_render_blind(renders_dir, self.adapter, llm_config)
                logger.info(f"[Iter {i}] A3: {len(spec_r.get('segments', []))} segments observed")
            except Exception as e:
                logger.warning(f"[Iter {i}] A3 failed: {e}")
            
            # -------- A4: Judge/Differ --------
            report = {"global_score": 50, "diffs": [], "per_axis_scores": {}}
            try:
                logger.info(f"[Iter {i}] A4: Judging...")
                report, _ = agent_roles.judge_differ(self.spec, spec_r, renders_dir, self.adapter, i, llm_config)
                logger.info(f"[Iter {i}] A4: Score {report.get('global_score', 50):.1f}")
            except Exception as e:
                logger.warning(f"[Iter {i}] A4 failed: {e}")
            
            # -------- Scoring & Convergence --------
            score = report.get("global_score", 50)
            diffs = report.get("diffs", [])
            sev = max([d.get("severity", 0) for d in diffs], default=0)
            
            converged = score >= self.threshold or sev < 4 or i >= self.max_iter - 1
            reason = ""
            if score >= self.threshold:
                reason = "score_threshold_met"
            elif sev < 4:
                reason = "no_high_severity_diffs"
            elif i >= self.max_iter - 1:
                reason = "max_iterations_reached"
            else:
                reason = ""
            
            top_diffs = sorted(diffs, key=lambda d: -d.get("severity", 0))[:3]
            result = IterationResult(i, score, report.get("per_axis_scores", {}), len(diffs), sev, converged, reason, top_diffs, datetime.now().isoformat())
            self.iterations.append(result)
            
            # -------- State Persistence --------
            self.state_mgr.update_iteration(
                iteration_number=i,
                global_score=score,
                per_axis_scores=report.get("per_axis_scores", {}),
                num_diffs=len(diffs),
                max_severity=sev,
                top_diffs=top_diffs,
                model_a2="claude-haiku-5",
                model_a4="gemini-2.5-flash" if i < 2 else "gemini-2.5-pro",
            )
            
            # -------- Save Results --------
            results_file = iter_dir / f"results.json"
            results_file.write_text(json.dumps({
                "iteration": i,
                "score": score,
                "per_axis_scores": report.get("per_axis_scores", {}),
                "diffs": diffs[:5],
                "converged": converged,
                "reason": reason,
                "rendered": {k: str(v) for k, v in rendered.items()},
            }, indent=2))
            
            # Track best
            if not self.best or score > self.best.score:
                self.best = result
                best_dir = self.output_dir / "best"
                best_dir.mkdir(exist_ok=True)
                (best_dir / "design.mpd").write_text(mpd.read_text())
                (best_dir / "results.json").write_text(results_file.read_text())
            
            logger.info(f"[Iter {i}] Score: {score:.1f}/100, Diffs: {len(diffs)}, Severity: {sev}, Converged: {converged}")
            
            if converged:
                self.state_mgr.mark_converged(reason)
                logger.info(f"[Loop] Converged after {i+1} iterations: {reason}")
                break
        
        elapsed = time.time() - start
        logger.info(f"[Loop] Finished: {len(self.iterations)} iterations, best score {self.best.score:.1f}/100, time {elapsed:.1f}s")
        
        return {
            "iterations": [asdict(r) for r in self.iterations],
            "best": asdict(self.best) if self.best else None,
            "converged": self.best and self.best.converged,
            "reason": self.best.reason if self.best else "unknown",
            "elapsed_seconds": elapsed,
        }
