"""Root cause analyzer: LLM-assisted analysis of unknown incident types.

When incident_taxonomy fails to classify an incident (new, unknown pattern),
this module invokes an LLM to analyze the root cause and propose a generalized fix.

This is ONLY called for novel incidents (not in the deterministic taxonomy),
so LLM cost is amortized across many future sets once the rule is learned.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def analyze_root_cause_and_propose_fix(
    diff: Dict[str, Any],
    llm_client: Any,
    model: str = "claude-haiku-4-5",
) -> Optional[Dict[str, Any]]:
    """Invoke LLM to analyze an unknown incident and propose generalized fix.
    
    Args:
        diff: The unclassified diff from physical_gate
        llm_client: LiteLLM-compatible client (or mock)
        model: LLM model to use
    
    Returns:
        Dict with keys:
          - category: proposed category name (e.g. "WEIRD_BRICK_PATTERN")
          - fix_pattern: generalized fix (no specific coordinates)
          - prompt_injection: text to inject into future prompts
          - trigger_signature: description of when to use this fix
        Or None if LLM call fails.
    """
    
    # Build diff summary for LLM
    diff_type = diff.get("type", "unknown")
    issue = diff.get("issue", "")
    evidence = diff.get("evidence", {})
    segment_a = evidence.get("segment_a", "")
    segment_b = evidence.get("segment_b", "")
    depth_ldu = evidence.get("depth_ldu", 0)
    
    prompt = f"""Analyze this LEGO building issue and propose a generalized fix.

Diff Type: {diff_type}
Issue: {issue}
Depth (LDU): {depth_ldu}
Segment A: {segment_a}
Segment B: {segment_b}

Your task:
1. Identify the ROOT CAUSE (what went wrong architecturally?)
2. Propose a GENERALIZED FIX that could prevent this across any set/MOC
3. Create a category name (UPPERCASE_SNAKE_CASE)
4. Provide a prompt injection that A2 can use

Return valid JSON with:
{{
  "category": "CATEGORY_NAME",
  "root_cause": "explanation",
  "fix_pattern": "generalized fix (no specific coords or IDs)",
  "prompt_injection": "CONSTRAINT: ... (no segment names, no exact values)",
  "trigger_signature": "description of when to apply this rule"
}}"""
    
    try:
        # Call LLM
        response = llm_client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        
        text = response.content[0].text if response.content else ""
        
        # Extract JSON from response
        try:
            # Try direct parse
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in text:
                json_part = text.split("```json")[1].split("```")[0]
                result = json.loads(json_part)
            elif "```" in text:
                json_part = text.split("```")[1].split("```")[0]
                result = json.loads(json_part)
            else:
                logger.warning(f"[RootCauseAnalyzer] Could not extract JSON from LLM response")
                return None
        
        # Validate required fields
        required = {"category", "fix_pattern", "prompt_injection"}
        if not required.issubset(result.keys()):
            logger.warning(f"[RootCauseAnalyzer] LLM response missing required fields: {required - set(result.keys())}")
            return None
        
        logger.info(f"[RootCauseAnalyzer] Analyzed unknown incident → category: {result['category']}")
        return result
    
    except Exception as e:
        logger.error(f"[RootCauseAnalyzer] LLM call failed: {e}")
        return None
