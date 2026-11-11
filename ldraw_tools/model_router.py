"""Model Router - Intelligent model assignment for LLM agents in improvement loop."""
from typing import Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)


class ModelRouter:
    """Routes LLM calls to appropriate Claude models based on agent and context."""

    def __init__(self, config: Optional[Dict[str, str]] = None):
        """
        Initialize router with optional config dict.
        Falls back to environment variables.
        
        Config keys (optional): a1_model, a2_model, a3_model, a4_model
        Env vars: LLM_A1_MODEL, LLM_A2_MODEL, LLM_A3_MODEL, LLM_A4_MODEL
        """
        self.config = config or {}
        self.stagnation_iterations = {}  # Track stagnation per job
        self.escalation_enabled = os.getenv("LLM_A4_STAGNATION_ESCALATION", "true").lower() == "true"

    def get_model_for_agent(self, agent_name: str, job_id: Optional[str] = None, score_history: Optional[list] = None) -> str:
        """
        Get the appropriate model for an agent.
        
        Args:
            agent_name: "A1", "A2", "A3", or "A4"
            job_id: Identifier for tracking A4 escalation
            score_history: List of scores from previous iterations (for A4 escalation logic)
        
        Returns:
            Model name string (e.g., "gemini-2.5-flash" for VLM, "claude-haiku-5" for A2)
        """
        # Check config first, then env vars, then defaults
        # A1/A3/A4 are VLM (Gemini); A2 is code generation (Claude Haiku)
        defaults = {
            "A1": os.getenv("LLM_A1_MODEL", "gemini-2.5-flash"),      # VLM: describe GT
            "A2": os.getenv("LLM_A2_MODEL", "claude-haiku-5"),        # Code: design 3D
            "A3": os.getenv("LLM_A3_MODEL", "gemini-2.5-flash"),      # VLM: describe render
            "A4": os.getenv("LLM_A4_MODEL", "gemini-2.5-flash"),      # VLM: judge/differ
        }
        
        base_model = self.config.get(f"{agent_name}_model") or defaults.get(agent_name)
        
        # A4 escalation logic: if stagnant, escalate to gemini-2.5-pro (stronger VLM)
        if agent_name == "A4" and self.escalation_enabled and job_id:
            if self._is_stagnant(job_id, score_history):
                logger.info(f"[ModelRouter] A4 escalation triggered (stagnation detected)")
                # Escalate from gemini-2.5-flash to gemini-2.5-pro
                if "gemini-2.5-flash" in base_model:
                    return base_model.replace("gemini-2.5-flash", "gemini-2.5-pro")
        
        return base_model

    def _is_stagnant(self, job_id: str, score_history: Optional[list]) -> bool:
        """
        Detect if score has stagnated (no improvement for 2 iterations).
        """
        if not score_history or len(score_history) < 3:
            return False
        
        # Check last 2 scores
        last_scores = score_history[-2:]
        if len(set(last_scores)) == 1 or (last_scores[-1] <= last_scores[-2]):
            # Same score or decreased
            if job_id not in self.stagnation_iterations:
                self.stagnation_iterations[job_id] = 1
            else:
                self.stagnation_iterations[job_id] += 1
            
            return self.stagnation_iterations[job_id] >= 2
        else:
            # Score improved, reset counter
            self.stagnation_iterations[job_id] = 0
            return False

    def reset_job(self, job_id: str) -> None:
        """Reset tracking for a job (cleanup)."""
        if job_id in self.stagnation_iterations:
            del self.stagnation_iterations[job_id]


# Global router instance
_router = None

def get_router() -> ModelRouter:
    """Get or create global router instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router

def get_model(agent_name: str, job_id: Optional[str] = None, score_history: Optional[list] = None) -> str:
    """Convenience function for getting a model without explicit router."""
    return get_router().get_model_for_agent(agent_name, job_id, score_history)
