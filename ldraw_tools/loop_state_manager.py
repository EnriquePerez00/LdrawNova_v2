"""Loop state persistence and resume capability."""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LoopStateManager:
    """Manages loop_state.json for persistence and resumable loops."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.state_file = self.output_dir / "loop_state.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def initialize_state(
        self,
        profile: str,
        slug: str,
        max_iterations: int = 4,
        threshold: float = 85.0,
    ) -> Dict[str, Any]:
        """Initialize new loop state."""
        state = {
            "version": 1,
            "profile": profile,
            "slug": slug,
            "current_iteration": 0,
            "best_iteration": -1,
            "best_score": 0.0,
            "converged": False,
            "stop_reason": "running",
            "config": {
                "max_iterations": max_iterations,
                "score_threshold": threshold,
                "timestamp_created": datetime.now().isoformat(),
            },
            "iterations": [],
            "anti_regression": {
                "reverted_at_iterations": [],
                "recent_fixes": [],
            },
        }
        self.save_state(state)
        logger.info(f"[LoopState] Initialized: {self.state_file}")
        return state
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load state from file."""
        if not self.state_file.exists():
            return None
        
        try:
            state = json.loads(self.state_file.read_text())
            logger.info(f"[LoopState] Loaded state: iter {state.get('current_iteration')}, score {state.get('best_score'):.1f}")
            return state
        except Exception as e:
            logger.error(f"[LoopState] Failed to load state: {e}")
            return None
    
    def save_state(self, state: Dict[str, Any]) -> None:
        """Save state to file."""
        try:
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.error(f"[LoopState] Failed to save state: {e}")
    
    def update_iteration(
        self,
        iteration_number: int,
        global_score: float,
        per_axis_scores: Dict[str, float],
        num_diffs: int,
        max_severity: int,
        top_diffs: List[Dict],
        model_a2: str = "",
        model_a4: str = "",
    ) -> None:
        """Update state with new iteration result."""
        state = self.load_state() or {"iterations": [], "best_score": 0.0}
        
        iter_data = {
            "iteration_number": iteration_number,
            "global_score": global_score,
            "per_axis_scores": per_axis_scores,
            "num_diffs": num_diffs,
            "max_severity": max_severity,
            "model_a2": model_a2,
            "model_a4": model_a4,
            "timestamp": datetime.now().isoformat(),
            "top_diffs": top_diffs[:3],
            "status": "success",
        }
        
        state["iterations"].append(iter_data)
        state["current_iteration"] = iteration_number
        
        # Track best
        if global_score > state.get("best_score", 0):
            state["best_score"] = global_score
            state["best_iteration"] = iteration_number
        
        self.save_state(state)
        logger.info(f"[LoopState] Updated iter {iteration_number}: score {global_score:.1f}")
    
    def mark_converged(self, reason: str) -> None:
        """Mark loop as converged with reason."""
        state = self.load_state()
        if state:
            state["converged"] = True
            state["stop_reason"] = reason
            self.save_state(state)
            logger.info(f"[LoopState] Converged: {reason}")
    
    def get_best_iteration(self) -> Optional[int]:
        """Get best iteration number."""
        state = self.load_state()
        if state and state.get("best_iteration", -1) >= 0:
            return state["best_iteration"]
        return None


def create_feedback_for_next_iteration(
    iteration_number: int,
    global_score: float,
    diffs: List[Dict[str, Any]],
    output_dir: Path,
) -> Path:
    """
    Create feedback.json for next iteration.
    Contains top diffs and score history.
    """
    feedback = {
        "iteration": iteration_number,
        "score": global_score,
        "diffs": sorted(diffs, key=lambda d: -d.get("severity", 0))[:5],  # Top 5 diffs
        "timestamp": datetime.now().isoformat(),
    }
    
    feedback_path = output_dir / f"iteration_{iteration_number}" / "feedback.json"
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    feedback_path.write_text(json.dumps(feedback, indent=2))
    
    logger.info(f"[Feedback] Created for iter {iteration_number}: {len(feedback['diffs'])} diffs")
    return feedback_path
