"""Token Tracker - Collect and estimate costs for LLM calls in improvement loop."""
import logging
from threading import Lock
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AgentMetrics:
    """Metrics for a single agent + model combination."""
    agent: str  # "A1", "A2", "A3", "A4"
    model: str
    num_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_latency_sec: float = 0.0
    fallback_count: int = 0
    
    def avg_latency_sec(self) -> float:
        if self.num_calls == 0:
            return 0.0
        return self.total_latency_sec / self.num_calls
    
    def cost_usd(self, pricing: Dict[str, Dict[str, float]]) -> float:
        """Estimate cost in USD based on tokens and pricing table."""
        if self.model not in pricing:
            return 0.0
        rates = pricing[self.model]
        input_cost = (self.prompt_tokens / 1_000_000) * rates.get("input_per_1m", 0)
        output_cost = (self.completion_tokens / 1_000_000) * rates.get("output_per_1m", 0)
        return input_cost + output_cost


class TokenTracker:
    """Accumulates tokens, latency, and estimates costs per agent/model."""
    
    # Public pricing (estimated, as of 2026-11)
    PRICING = {
        "gemini-2.5-flash": {"input_per_1m": 0.075, "output_per_1m": 0.3},
        "gemini-2.5-pro": {"input_per_1m": 0.6, "output_per_1m": 2.4},
        "claude-haiku-4-5": {"input_per_1m": 0.8, "output_per_1m": 4.0},
        "llama3.2-vision:11b": {"input_per_1m": 0.0, "output_per_1m": 0.0}
    }
    
    def __init__(self):
        self.metrics: Dict[Tuple[str, str], AgentMetrics] = {}
        self._lock = Lock()
    
    def record_call(
        self, agent: str, model: str, prompt_tokens: int, 
        completion_tokens: int, latency_sec: float, fallback: bool = False
    ) -> None:
        """Record a single LLM call."""
        key = (agent, model)
        with self._lock:
            if key not in self.metrics:
                self.metrics[key] = AgentMetrics(agent=agent, model=model)
            
            m = self.metrics[key]
            m.num_calls += 1
            m.prompt_tokens += prompt_tokens
            m.completion_tokens += completion_tokens
            m.total_tokens += prompt_tokens + completion_tokens
            m.total_latency_sec += latency_sec
            if fallback:
                m.fallback_count += 1
    
    def cost_summary_usd(self) -> float:
        """Total estimated cost in USD."""
        return sum(m.cost_usd(self.PRICING) for m in self.metrics.values())
    
    def to_dict(self) -> Dict:
        """Serialize for JSON persistence."""
        with self._lock:
            metrics_list = []
            for (agent, model), m in sorted(self.metrics.items()):
                cost = m.cost_usd(self.PRICING)
                metrics_list.append({
                    "agent": agent,
                    "model": model,
                    "num_calls": m.num_calls,
                    "prompt_tokens": m.prompt_tokens,
                    "completion_tokens": m.completion_tokens,
                    "total_tokens": m.total_tokens,
                    "avg_latency_sec": round(m.avg_latency_sec(), 3),
                    "total_latency_sec": round(m.total_latency_sec, 1),
                    "fallback_count": m.fallback_count,
                    "cost_usd": round(cost, 4),
                })
            
            cost_by_model = {}
            for m in self.metrics.values():
                if m.model not in cost_by_model:
                    cost_by_model[m.model] = 0.0
                cost_by_model[m.model] += m.cost_usd(self.PRICING)
            
            total_cost = sum(cost_by_model.values())
            
            return {
                "by_agent_model": metrics_list,
                "cost_by_model": {k: round(v, 4) for k, v in cost_by_model.items()},
                "cost_total_usd": round(total_cost, 4),
                "pricing_note": "Rates are estimated. Local models (Ollama) are free.",
            }


# Global tracker registry
_trackers: Dict[str, TokenTracker] = {}
_trackers_lock = Lock()

def get_tracker(output_dir_slug: str) -> TokenTracker:
    """Get or create tracker for output directory."""
    with _trackers_lock:
        if output_dir_slug not in _trackers:
            _trackers[output_dir_slug] = TokenTracker()
        return _trackers[output_dir_slug]

def reset_tracker(output_dir_slug: str) -> None:
    """Reset tracker."""
    with _trackers_lock:
        if output_dir_slug in _trackers:
            del _trackers[output_dir_slug]
