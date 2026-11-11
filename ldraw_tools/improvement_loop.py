"""Improvement Loop - Minimal MVP."""
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from datetime import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

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

class ImprovementLoop:
    def __init__(self, spec, adapter, output, max_iter=4, threshold=85.0):
        self.spec = spec
        self.adapter = adapter
        self.output = output
        self.max_iter = max_iter
        self.threshold = threshold
        self.iterations = []
        self.best = None

    def run(self, agent_roles, feedback=None):
        start = time.time()
        for i in range(self.max_iter):
            logger.info(f"\n[Iter {i}]")
            fb = feedback if i == 0 else ({"score": self.iterations[-1].score, "diffs": self.iterations[-1].top_diffs} if self.iterations else None)
            try:
                plan, mpd = agent_roles.design_3d(self.spec, fb, self.adapter, Path(self.output) / f"iter_{i}")
            except:
                logger.error("A2 failed")
                continue
            try:
                spec_r = agent_roles.describe_render_blind(Path(self.output) / f"iter_{i}/renders", self.adapter)
            except:
                spec_r = {}
            try:
                report = agent_roles.judge_differ(self.spec, spec_r, Path(self.output) / f"iter_{i}/renders", self.adapter, i)
            except:
                report = {"global_score": 50, "diffs": [], "per_axis_scores": {}}
            score = report.get("global_score", 50)
            diffs = report.get("diffs", [])
            sev = max([d.get("severity", 0) for d in diffs], default=0)
            converged = score >= self.threshold or sev < 4 or i >= self.max_iter - 1
            top_diffs = sorted(diffs, key=lambda d: -d.get("severity", 0))[:3]
            result = IterationResult(i, score, report.get("per_axis_scores", {}), len(diffs), sev, converged, "", top_diffs, datetime.now().isoformat())
            self.iterations.append(result)
            logger.info(f"Score {score:.1f}/100")
            if not self.best or score > self.best.score:
                self.best = result
            if converged:
                break
        logger.info(f"Done in {time.time()-start:.1f}s")
        return self.best
