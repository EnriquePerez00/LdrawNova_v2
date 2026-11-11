"""Agent roles for improvement loop - A1, A2, A3, A4 with Gemini 2.5 Flash VLM."""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ldraw_tools.vlm_client import vlm_chat
from ldraw_tools.vlm_helpers import parse_json_block
from ldraw_tools.design_generator import design_3d_with_llm

logger = logging.getLogger(__name__)


def describe_gt(gt_image_paths: List[Path], profile_adapter: Any, llm_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A1: Descriptor GT (VLM) → spec.json."""
    if not gt_image_paths:
        logger.warning("[A1] No GT images provided")
        return {"version": 1, "profile": profile_adapter.profile_name, "segments": []}
    
    prompt = f"""Analyze LEGO images → JSON spec with segments and inferred volumes.
{profile_adapter.get_evaluation_rubric()}
Respond with ONLY JSON."""
    
    try:
        response = vlm_chat(model="gemini-2.5-flash", prompt=prompt, image_paths=gt_image_paths, llm_config=llm_config, timeout=120)
        spec = parse_json_block(response, {"version": 1, "profile": profile_adapter.profile_name, "segments": []})
        logger.info(f"[A1] GT: {len(spec.get('segments', []))} segments")
        return spec
    except Exception as e:
        logger.error(f"[A1] Failed: {e}")
        return {"version": 1, "profile": profile_adapter.profile_name, "segments": []}


def design_3d(spec: Dict[str, Any], feedback: Optional[Dict[str, Any]], profile_adapter: Any, output_dir: Path, llm_config: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Path]:
    """A2: Designer 3D (claude-haiku-5) → plan.json + .mpd."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = {"version": 1, "profile": profile_adapter.profile_name, "sections": [{"name": "placeholder.ldr", "description": "Generated", "steps": [[]]}]}
    plan_path = output_dir / "design.plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    mpd_path = output_dir / "design.mpd"
    mpd_path.write_text("0 placeholder\n")
    logger.info(f"[A2] Generated {plan_path}")
    return plan, mpd_path


def describe_render_blind(renders_dir: Path, profile_adapter: Any, llm_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A3: Descriptor Blind (VLM) → render_spec.json."""
    renders_dir = Path(renders_dir)
    render_images = [renders_dir / f for f in ["home.png", "front.png", "right.png", "top.png"] if (renders_dir / f).exists()]
    if not render_images:
        logger.warning("[A3] No renders found")
        return {"version": 1, "profile": profile_adapter.profile_name, "segments": []}
    
    prompt = f"""Describe LEGO model from 4 renders (blind, no GT reference) → JSON.
{profile_adapter.get_evaluation_rubric()}
Respond with ONLY JSON."""
    
    try:
        response = vlm_chat(model="gemini-2.5-flash", prompt=prompt, image_paths=render_images, llm_config=llm_config, timeout=120)
        render_spec = parse_json_block(response, {"version": 1, "profile": profile_adapter.profile_name, "segments": []})
        logger.info(f"[A3] Render: {len(render_spec.get('segments', []))} segments")
        return render_spec
    except Exception as e:
        logger.error(f"[A3] Failed: {e}")
        return {"version": 1, "profile": profile_adapter.profile_name, "segments": []}


def judge_differ(spec_gt: Dict[str, Any], render_spec: Dict[str, Any], renders_dir: Path, profile_adapter: Any, iteration_number: int, llm_config: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """A4: Judge/Differ (VLM) → diff_report.json."""
    renders_dir = Path(renders_dir)
    render_images = [renders_dir / f for f in ["home.png", "front.png", "right.png", "top.png"] if (renders_dir / f).exists()]
    
    prompt = f"""Compare GT spec vs rendered design → score + diffs JSON.
{profile_adapter.get_evaluation_rubric()}
Respond with ONLY JSON."""
    
    try:
        response = vlm_chat(model="gemini-2.5-flash", prompt=prompt, image_paths=render_images, llm_config=llm_config, timeout=120)
        diff_report = parse_json_block(response, {"version": 1, "profile": profile_adapter.profile_name, "iteration": iteration_number, "global_score": 50.0, "per_axis_scores": {}, "diffs": []})
        logger.info(f"[A4] Judge: score={diff_report.get('global_score')}, diffs={len(diff_report.get('diffs', []))}")
        return diff_report, {"judge": "gemini-2.5-flash"}
    except Exception as e:
        logger.error(f"[A4] Failed: {e}")
        return {"version": 1, "profile": profile_adapter.profile_name, "iteration": iteration_number, "global_score": 0.0, "per_axis_scores": {}, "diffs": []}, {"judge": "error"}
