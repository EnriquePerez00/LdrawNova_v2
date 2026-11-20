"""Pure decision policy for the improvement loop (no I/O, unit-testable).

Fixes: A4 emits severity as 'high|medium|low' strings while the loop compared
numerically; normalizes both to an int 0-5 scale.
"""
from typing import Any, Dict, Iterable, List, Optional, Tuple

SEVERITY_MAP = {"critical": 5, "high": 4, "medium": 2, "low": 1, "info": 0, "none": 0}
SEVERITY_STOP_THRESHOLD = 4  # converge when max severity < this
REVERT_MARGIN = 5.0  # points below best that trigger a revert


def normalize_severity(value: Any) -> int:
    """Map str/number severity to int 0-5. Unknown -> 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, min(5, int(value)))
    if isinstance(value, str):
        v = value.strip().lower()
        if v in SEVERITY_MAP:
            return SEVERITY_MAP[v]
        try:
            return max(0, min(5, int(float(v))))
        except ValueError:
            return 0
    return 0


def normalize_diffs(diffs: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    out = []
    for d in diffs or []:
        if isinstance(d, dict):
            out.append({**d, "severity": normalize_severity(d.get("severity", 0))})
    return out


def max_severity(diffs: List[Dict[str, Any]]) -> int:
    return max((d["severity"] for d in diffs), default=0)


def top_diffs(diffs: List[Dict[str, Any]], n: int = 3) -> List[Dict[str, Any]]:
    return sorted(diffs, key=lambda d: -d["severity"])[:n]


def check_convergence(score: float, max_sev: int, iteration: int, max_iter: int,
                      threshold: float = 85.0, judged: bool = True) -> Tuple[bool, str]:
    """3-way OR. `judged=False` (A4 failed/no diffs info) never counts as 'no high severity'."""
    if score >= threshold:
        return True, "score_threshold_met"
    if judged and max_sev < SEVERITY_STOP_THRESHOLD:
        return True, "no_high_severity_diffs"
    if iteration >= max_iter - 1:
        return True, "max_iterations_reached"
    return False, ""


def should_revert(new_score: float, best_score: Optional[float], margin: float = REVERT_MARGIN) -> bool:
    """Hill-climbing guard: revert if the new design is clearly worse than best."""
    return best_score is not None and new_score < best_score - margin
