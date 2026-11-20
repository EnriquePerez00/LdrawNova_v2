"""Recipe bank: store, select, and format few-shot examples for A2 prompts.

A recipe is a triple (description, mpd_code, score) that A2 learns from.
Examples are selected based on spec similarity and injected into the prompt.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["load_recipes", "select_recipes", "format_recipes_for_prompt"]


def load_recipes(bank_path: Path) -> List[Dict[str, Any]]:
    """Load recipes from a JSON bank file.
    
    Args:
        bank_path: Path to recipes_seed.json or similar
    
    Returns:
        List of recipe dicts: {description, mpd, score, tier, num_segments, ...}
    """
    if not bank_path.exists():
        logger.warning(f"[RecipeBank] Bank not found: {bank_path}")
        return []
    
    try:
        data = json.loads(bank_path.read_text())
        recipes = data.get("recipes", []) if isinstance(data, dict) else data
        logger.info(f"[RecipeBank] Loaded {len(recipes)} recipes from {bank_path.name}")
        return recipes
    except Exception as e:
        logger.error(f"[RecipeBank] Failed to load: {e}")
        return []


def select_recipes(spec: Dict[str, Any], bank: List[Dict[str, Any]], k: int = 3) -> List[Dict[str, Any]]:
    """Select k most relevant recipes for the given spec.
    
    Heuristics:
    - Match by tier (MICRO/SMALL/MEDIUM if present in spec)
    - Match by num_segments (prefer recipes with similar segment count)
    - Sort by score (descending)
    
    Args:
        spec: Design spec (has segments, canonical_description, etc.)
        bank: List of recipes to select from
        k: Number of recipes to return
    
    Returns:
        Top k recipes, sorted by relevance score
    """
    if not bank:
        return []
    
    spec_tier = spec.get("tier", "MICRO")
    spec_segments = len(spec.get("segments", []))
    
    # Score each recipe
    scored = []
    for recipe in bank:
        score = 0.0
        
        # Match tier (if available)
        if recipe.get("tier") == spec_tier:
            score += 3.0
        
        # Match segment count (prefer within ±2 segments)
        recipe_segments = recipe.get("num_segments", 1)
        seg_diff = abs(recipe_segments - spec_segments)
        if seg_diff <= 2:
            score += 2.0 / (seg_diff + 1)
        
        # Prefer higher scores (learned from convergence)
        recipe_score = recipe.get("score", 0)
        score += recipe_score / 100.0
        
        scored.append((score, recipe))
    
    # Sort by relevance score (desc) and return top k
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [r for _, r in scored[:k]]
    logger.info(f"[RecipeBank] Selected {len(selected)}/{len(bank)} recipes for {spec_tier} tier, {spec_segments} segs")
    
    return selected


def format_recipes_for_prompt(recipes: List[Dict[str, Any]]) -> str:
    """Format recipes as a text block for the A2 prompt.
    
    NOTE: NO markdown code fences - raw MPD only to avoid confusing LLM.
    
    Args:
        recipes: List of recipes from select_recipes()
    
    Returns:
        Text block with examples, ready to embed in prompt
    """
    if not recipes:
        return ""
    
    block = "Few-shot examples (well-formed designs with good structure):\n\n"
    for i, recipe in enumerate(recipes, 1):
        desc = recipe.get("description", "Example")
        score = recipe.get("score", "?")
        num_seg = recipe.get("num_segments", "?")
        block += f"Example {i}: {desc} (score={score}/100, segments={num_seg})\n"
        # Raw MPD code WITHOUT markdown fences - Claude handles this better
        block += recipe.get("mpd", "0 FILE example.ldr\n0 NOFILE\n")
        block += "\n"
    
    return block


if __name__ == "__main__":
    # Quick test
    test_recipes = [
        {"description": "2x4 brick", "mpd": "0 FILE example.ldr\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 NOFILE\n", "score": 80, "tier": "MICRO", "num_segments": 1},
        {"description": "2 bricks stacked", "mpd": "0 FILE example.ldr\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 16 0 10 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 NOFILE\n", "score": 85, "tier": "MICRO", "num_segments": 1},
    ]
    
    spec = {"segments": [{}, {}, {}], "tier": "MICRO"}
    selected = select_recipes(spec, test_recipes, k=2)
    block = format_recipes_for_prompt(selected)
    print(block)
