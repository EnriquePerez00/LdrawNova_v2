#!/usr/bin/env python3
"""Phase 2: Run A1/A3/A4 judge loop with LiteLLM."""

import json
import logging
import os
from pathlib import Path
from ldraw_tools.agent_roles import describe_gt, describe_render_blind, judge_differ
from ldraw_tools.profile_adapter import ProfileAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LiteLLM config from .env
llm_config = {
    "base_url": os.getenv("LLM_BASE_URL", "http://localhost:6655/litellm"),
    "secret": os.getenv("LLM_SECRET", ""),
}

output_dir = Path("/Users/I764690/Code_personal/LdrawNova/output/sap_logo")
renders_dir = output_dir / "renders"

# Load profile adapter
whitelist_path = Path("/Users/I764690/Code_personal/LdrawNova/profiles/brand_logo/catalog/brand_logo_whitelist.json")
palette_path = Path("/Users/I764690/Code_personal/LdrawNova/profiles/brand_logo/catalog/brand_logo_palette.json")
adapter = ProfileAdapter("brand_logo", whitelist_path, palette_path)

logger.info(f"\n[Phase 2] LiteLLM: {llm_config['base_url']}")

# A1/A3/A4 calls
gt_images = [renders_dir / "home.png"]
spec_gt = describe_gt(gt_images, adapter, llm_config)
logger.info(f"[A1] Segments: {len(spec_gt.get('segments', []))}")

spec_render = describe_render_blind(renders_dir, adapter, llm_config)
logger.info(f"[A3] Segments: {len(spec_render.get('segments', []))}")

diff_report, _ = judge_differ(spec_gt, spec_render, renders_dir, adapter, 1, llm_config)
logger.info(f"[A4] Score: {diff_report.get('global_score')}/100")

# Save
(output_dir / "diff_report.json").write_text(json.dumps(diff_report, indent=2))
logger.info(f"\n✓ Phase 2 complete")

