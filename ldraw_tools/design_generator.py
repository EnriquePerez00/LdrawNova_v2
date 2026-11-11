"""A2 Designer: Claude Haiku-5 code generation for LDraw designs."""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def design_3d_with_llm(
    spec: Dict[str, Any],
    feedback: Optional[Dict[str, Any]],
    profile_adapter: Any,
    output_dir: Path,
    llm_config: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Path]:
    """
    A2: Designer 3D with Claude Haiku-5 (code LLM, not VLM).
    Generates LDraw MPD from spec + feedback.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    import requests
    llm_config = llm_config or {}
    base_url = (llm_config.get("base_url") or "http://localhost:6655/litellm").rstrip("/")
    secret = llm_config.get("secret", "")
    
    # Build prompt for Claude Haiku-5
    feedback_str = ""
    if feedback:
        diffs = feedback.get("diffs", [])
        if diffs:
            feedback_str = "\n\nFeedback from judge (fixes needed):\n"
            for d in diffs[:3]:
                feedback_str += f"- {d.get('type', 'unknown')}: {d.get('suggested_fix', 'improve')}\n"
    
    prompt = f"""Generate valid LDraw/MPD code for a LEGO design based on this spec:

Profile: {profile_adapter.profile_name}
Description: {spec.get('canonical_description', 'LEGO model')}
Segments: {len(spec.get('segments', []))}

Segment details:
"""
    
    for seg in spec.get('segments', [])[:5]:  # First 5 segments
        prompt += f"- {seg.get('name', 'segment')}: {seg.get('description', '')} (color: {seg.get('color_dominant', '#000000')})\n"
    
    prompt += f"""
{feedback_str}

Generate valid LDraw MPD syntax. Return ONLY the MPD code, no explanation.
Format:
0 FILE design.ldr
0 Name: design.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
(more parts as needed)
0 NOFILE
"""
    
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    
    payload = {
        "model": "claude-haiku-5",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1000,
    }
    
    url = f"{base_url}/v1/chat/completions"
    
    try:
        logger.debug(f"[A2] Calling {url} with claude-haiku-5")
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("No response from LLM")
        
        mpd_code = (choices[0].get("message", {}).get("content") or "").strip()
        logger.info(f"[A2] LLM generated {len(mpd_code)} chars of LDraw code")
    
    except Exception as e:
        logger.error(f"[A2] LLM call failed: {e}")
        # Fallback: simple placeholder
        mpd_code = """0 FILE design.ldr
0 Name: design.ldr
0 Placeholder generated after LLM failure
1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE
"""
    
    # Write MPD file
    mpd_path = output_dir / "design.mpd"
    mpd_path.write_text(mpd_code)
    
    # Create plan.json metadata
    plan = {
        "version": 1,
        "profile": profile_adapter.profile_name,
        "spec_segments": len(spec.get('segments', [])),
        "feedback_applied": feedback is not None,
        "llm_model": "claude-haiku-5",
        "sections": [{"name": "design.ldr", "description": "Generated LDraw model", "lines": len(mpd_code.split('\n'))}]
    }
    
    plan_path = output_dir / "design.plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    
    logger.info(f"[A2] Generated {mpd_path.name} and {plan_path.name}")
    return plan, mpd_path
