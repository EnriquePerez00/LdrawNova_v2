"""Configuration for Structural Diff weights by LEGO tier.

Phase D validation showed:
- MICRO (12-32 parts): convergence 60%, scores 85.5 avg
- SMALL (50-200 parts): TBD (recommend probe before production)
- MEDIUM (200+ parts): TBD (phased rollout)

Weights:
  weight_structural = proportion of structural score in blend
  weight_a4 = 1.0 - weight_structural
  
  blended_score = weight_a4 * a4_score + weight_structural * struct_score

Default: 0.7*A4 + 0.3*structural (A4 visual is primary signal)
"""

from typing import Dict, Any

# Tier-specific configurations
TIER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "MICRO": {
        "parts_range": (1, 50),
        "weight_structural": 0.3,  # 70% A4 + 30% structural
        "convergence_threshold": 85.0,
        "status": "VALIDATED",  # Phase D tested
        "description": "Small sets, simple connectivity",
    },
    "SMALL": {
        "parts_range": (50, 200),
        "weight_structural": 0.4,  # 60% A4 + 40% structural
        "convergence_threshold": 82.0,  # Lower threshold due to complexity
        "status": "RECOMMENDED_PROBE",  # Not yet tested
        "description": "Medium sets, moderate connectivity",
    },
    "MEDIUM": {
        "parts_range": (200, 2000),
        "weight_structural": 0.5,  # 50% A4 + 50% structural
        "convergence_threshold": 80.0,  # Lower threshold due to high complexity
        "status": "PHASED_ROLLOUT",  # Rollout pending
        "description": "Large sets, complex connectivity",
    },
}


def get_config_for_tier(tier: str) -> Dict[str, Any]:
    """Get structural diff config for a tier.
    
    Args:
        tier: "MICRO", "SMALL", or "MEDIUM"
    
    Returns:
        Config dict with weights, threshold, status, description.
    
    Raises:
        ValueError: If tier not recognized.
    """
    if tier not in TIER_CONFIGS:
        raise ValueError(
            f"Unknown tier '{tier}'. "
            f"Must be one of: {list(TIER_CONFIGS.keys())}"
        )
    return TIER_CONFIGS[tier].copy()


def infer_tier(parts_count: int) -> str:
    """Infer tier from parts count.
    
    Args:
        parts_count: Number of parts in assembly
    
    Returns:
        Tier name ("MICRO", "SMALL", or "MEDIUM")
    """
    for tier, config in TIER_CONFIGS.items():
        parts_min, parts_max = config["parts_range"]
        if parts_min <= parts_count <= parts_max:
            return tier
    
    # Default to largest if exceeds
    if parts_count > 2000:
        return "MEDIUM"
    return "MICRO"
