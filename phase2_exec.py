#!/usr/bin/env python3
"""Phase 2: Full VLM judge loop with GT images."""

import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger('Phase2')

# Config from env
llm_config = {
    "base_url": "http://localhost:6655/litellm",
    "secret": os.getenv("LLM_SECRET", ""),
}

from ldraw_tools.agent_roles import describe_gt, describe_render_blind, judge_differ
from ldraw_tools.profile_adapter import ProfileAdapter

output_dir = Path("/Users/I764690/Code_personal/LdrawNova/output/sap_logo")
renders_dir = output_dir / "renders"
gt_dir = output_dir / "gt"

# Ensure GT dir exists
gt_dir.mkdir(exist_ok=True)

# Load adapter
whitelist_path = Path("/Users/I764690/Code_personal/LdrawNova/profiles/brand_logo/catalog/brand_logo_whitelist.json")
palette_path = Path("/Users/I764690/Code_personal/LdrawNova/profiles/brand_logo/catalog/brand_logo_palette.json")
adapter = ProfileAdapter("brand_logo", whitelist_path, palette_path)

logger.info(f"LiteLLM: {llm_config['base_url']}")

# Check if GT images exist
gt_images = [gt_dir / f"gt_{name}.png" for name in ["cenital", "frontal", "lateral_izq", "lateral_der"]]
existing_gt = [img for img in gt_images if img.exists()]

logger.info(f"GT images found: {len(existing_gt)}/4")

if len(existing_gt) == 0:
    logger.warning("No GT images in gt_dir; using renders as proxy for now")
    gt_images = [renders_dir / "home.png"]
else:
    gt_images = existing_gt
    for img in existing_gt:
        logger.info(f"  ✓ {img.name}")

# A1: Describe GT
logger.info(f"[A1] Describing {len(gt_images)} GT image(s)...")
try:
    spec_gt = describe_gt(gt_images, adapter, llm_config)
    logger.info(f"[A1] ✓ Segments: {len(spec_gt.get('segments', []))}")
except Exception as e:
    logger.error(f"[A1] ✗ Failed: {e}")
    spec_gt = {"segments": []}

# A3: Describe Renders (Blind)
logger.info("[A3] Describing renders (blind)...")
try:
    spec_render = describe_render_blind(renders_dir, adapter, llm_config)
    logger.info(f"[A3] ✓ Segments: {len(spec_render.get('segments', []))}")
except Exception as e:
    logger.error(f"[A3] ✗ Failed: {e}")
    spec_render = {"segments": []}

# A4: Judge/Differ
logger.info("[A4] Judging...")
try:
    diff_report, _ = judge_differ(spec_gt, spec_render, renders_dir, adapter, 1, llm_config)
    score = diff_report.get("global_score", 0)
    diffs_count = len(diff_report.get("diffs", []))
    logger.info(f"[A4] ✓ Score: {score}/100, Diffs: {diffs_count}")
except Exception as e:
    logger.error(f"[A4] ✗ Failed: {e}")
    diff_report = {"global_score": 0, "diffs": []}

# Save
(output_dir / "diff_report_phase2.json").write_text(json.dumps(diff_report, indent=2))
logger.info("✓ Saved: diff_report_phase2.json")

# Summary
print("\n" + "="*60)
print("PHASE 2 RESULTS")
print("="*60)
print(f"GT Score: {diff_report.get('global_score', 0)}/100")
print(f"Diffs: {len(diff_report.get('diffs', []))}")
print(f"Per-axis: {diff_report.get('per_axis_scores', {})}")
print("="*60)
