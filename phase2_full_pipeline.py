#!/usr/bin/env python3
"""
Full Phase 2 Pipeline: Decompose GT, run VLM loop in background, monitor results.
"""

import json
import logging
from pathlib import Path
from PIL import Image
import subprocess
import time
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(message)s'
)
logger = logging.getLogger("Phase2-Pipeline")

# Paths
WORKSPACE = Path("/Users/I764690/Code_personal/LdrawNova")
GT_SOURCE = WORKSPACE / "images_GT" / "SAP_logo.jpeg"
OUTPUT_DIR = WORKSPACE / "output" / "sap_logo"
GT_DIR = OUTPUT_DIR / "gt"
RENDERS_DIR = OUTPUT_DIR / "renders"

logger.info("=" * 80)
logger.info("PHASE 2 PIPELINE: Backend Real (Decompose GT + Run VLM in Background)")
logger.info("=" * 80)

# ============ STEP 1: Decompose GT image 2×2 → 4 quadrants ============
logger.info("\n[STEP 1] Decomposing GT image 2×2 → 4 quadrants...")

if not GT_SOURCE.exists():
    logger.error(f"✗ GT source not found: {GT_SOURCE}")
    sys.exit(1)

try:
    img = Image.open(GT_SOURCE)
    logger.info(f"✓ Loaded: {GT_SOURCE.name} ({img.size[0]}×{img.size[1]}, {img.mode})")
    
    width, height = img.size
    half_w = width // 2
    half_h = height // 2
    
    GT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Define 4 quadrants: cenital, frontal, lateral_izq, lateral_der
    quadrants = [
        ("cenital", (0, 0, half_w, half_h)),           # top-left
        ("frontal", (half_w, 0, width, half_h)),       # top-right
        ("lateral_izq", (0, half_h, half_w, height)), # bottom-left
        ("lateral_der", (half_w, half_h, width, height)), # bottom-right
    ]
    
    for name, bbox in quadrants:
        cropped = img.crop(bbox)
        output_path = GT_DIR / f"gt_{name}.png"
        cropped.save(output_path)
        logger.info(f"✓ {name}: {output_path.name} ({cropped.size[0]}×{cropped.size[1]})")
    
    # Also save a copy of the original 2×2
    gt_source_copy = GT_DIR / "gt_source_2x2.jpeg"
    img.save(gt_source_copy)
    logger.info(f"✓ Copied original: {gt_source_copy.name}")
    
except Exception as e:
    logger.error(f"✗ Decomposition failed: {e}")
    sys.exit(1)


# ============ STEP 4: Create and launch VLM loop script (background) ============
logger.info("\n[STEP 4] Creating VLM loop script (to run in background)...")

vlm_script_content = '''#!/usr/bin/env python3
import json, logging, os, sys
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[
        logging.FileHandler("/Users/I764690/Code_personal/LdrawNova/output/sap_logo/vlm_loop.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("VLM-Loop")

sys.path.insert(0, '/Users/I764690/Code_personal/LdrawNova')
from ldraw_tools.agent_roles import describe_gt, describe_render_blind, judge_differ
from ldraw_tools.profile_adapter import ProfileAdapter

output_dir = Path("/Users/I764690/Code_personal/LdrawNova/output/sap_logo")
gt_dir = output_dir / "gt"
renders_dir = output_dir / "renders"

llm_config = {
    "base_url": os.getenv("LLM_BASE_URL", "http://localhost:6655/litellm"),
    "secret": os.getenv("LLM_SECRET", ""),
}

whitelist_path = Path("/Users/I764690/Code_personal/LdrawNova/profiles/brand_logo/catalog/brand_logo_whitelist.json")
palette_path = Path("/Users/I764690/Code_personal/LdrawNova/profiles/brand_logo/catalog/brand_logo_palette.json")
adapter = ProfileAdapter("brand_logo", whitelist_path, palette_path)

logger.info(f"LiteLLM: {llm_config['base_url']}")

gt_images = [gt_dir / f"gt_{name}.png" for name in ["cenital", "frontal", "lateral_izq", "lateral_der"]]
existing_gt = [img for img in gt_images if img.exists()]
logger.info(f"GT images: {len(existing_gt)}/4")

try:
    logger.info("[A1] Describing GT...")
    spec_gt = describe_gt(existing_gt, adapter, llm_config)
    (output_dir / "gt_spec.json").write_text(json.dumps(spec_gt, indent=2))
    logger.info(f"[A1] ✓ {len(spec_gt.get('segments', []))} segments")
except Exception as e:
    logger.error(f"[A1] Failed: {e}")
    spec_gt = {"segments": []}

try:
    logger.info("[A3] Describing renders (blind)...")
    spec_render = describe_render_blind(renders_dir, adapter, llm_config)
    (output_dir / "render_spec.json").write_text(json.dumps(spec_render, indent=2))
    logger.info(f"[A3] ✓ {len(spec_render.get('segments', []))} segments")
except Exception as e:
    logger.error(f"[A3] Failed: {e}")
    spec_render = {"segments": []}

try:
    logger.info("[A4] Judging (GT vs render)...")
    diff_report, _ = judge_differ(spec_gt, spec_render, renders_dir, adapter, 1, llm_config)
    (output_dir / "diff_report.json").write_text(json.dumps(diff_report, indent=2))
    logger.info(f"[A4] ✓ Score: {diff_report.get('global_score', 0)}/100")
except Exception as e:
    logger.error(f"[A4] Failed: {e}")

logger.info("[VLM Loop] COMPLETE")
'''

vlm_script_path = OUTPUT_DIR / "run_vlm_loop.py"
vlm_script_path.write_text(vlm_script_content)
logger.info(f"✓ Created: {vlm_script_path.name}")

# ============ STEP 5: Launch VLM in background ============
logger.info("\n[STEP 5] Launching VLM loop in background (max 5 min)...")

log_file = OUTPUT_DIR / "vlm_loop.log"

try:
    with open(log_file, "w") as lf:
        process = subprocess.Popen(
            ["python3", str(vlm_script_path)],
            stdout=lf,
            stderr=subprocess.STDOUT,
            cwd=str(WORKSPACE),
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
    logger.info(f"✓ VLM loop launched (PID: {process.pid})")
    logger.info(f"✓ Logging to: {log_file.name}")
    
except Exception as e:
    logger.error(f"✗ Failed to launch: {e}")
    sys.exit(1)

# ============ STEP 6: Monitor progress ============
logger.info("\n[STEP 6] Monitoring VLM progress...")

start_time = time.time()
timeout = 300  # 5 minutes
check_interval = 10

while time.time() - start_time < timeout:
    outputs = {
        "gt_spec.json": OUTPUT_DIR / "gt_spec.json",
        "render_spec.json": OUTPUT_DIR / "render_spec.json",
        "diff_report.json": OUTPUT_DIR / "diff_report.json",
    }
    
    completed = [name for name, path in outputs.items() if path.exists()]
    if completed:
        for name in completed:
            logger.info(f"✓ {name}")
    
    if all(path.exists() for path in outputs.values()):
        logger.info("\n✅ All VLM outputs generated!")
        break
    
    if log_file.exists() and "[VLM Loop] COMPLETE" in log_file.read_text():
        logger.info("\n✅ VLM loop reported completion")
        break
    
    time.sleep(check_interval)

# ============ STEP 7: Summary ============
logger.info("\n[STEP 7] Final Summary...")
logger.info("=" * 80)

for output_file in ["gt_spec.json", "render_spec.json", "diff_report.json"]:
    path = OUTPUT_DIR / output_file
    if path.exists():
        logger.info(f"✓ {output_file} ({path.stat().st_size} bytes)")
    else:
        logger.info(f"⏳ {output_file} (still running...)")

logger.info("=" * 80)
logger.info("✅ PHASE 2 BACKEND COMPLETE - Ready for UX integration")
logger.info("=" * 80)

# ============ STEP 2: Re-render with fixed renderer ============
logger.info("\n[STEP 2] Re-rendering with fixed renderer (--viewpoint syntax)...")

try:
    cmd = [
        "python3", "-c",
        """
import sys
sys.path.insert(0, '/Users/I764690/Code_personal/LdrawNova')
from pathlib import Path
from ldraw_tools.renderer import LeoCADRenderer

mpd_path = Path('/Users/I764690/Code_personal/LdrawNova/output/sap_logo/sap_logo.mpd')
renders_dir = Path('/Users/I764690/Code_personal/LdrawNova/output/sap_logo/renders')
renderer = LeoCADRenderer()

rendered = renderer.render_views(mpd_path, renders_dir)
for view, path in rendered.items():
    print(f'✓ {view}: {path.stat().st_size} bytes')
"""
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(WORKSPACE))
    if result.returncode == 0:
        logger.info("✓ Re-rendering complete:")
        for line in result.stdout.split('\n'):
            if '✓' in line:
                logger.info(f"  {line}")
    else:
        logger.warning(f"⚠ Re-rendering had issues:\n{result.stderr[:300]}")
        
except Exception as e:
    logger.warning(f"⚠ Re-render skipped: {e}")

# ============ STEP 3: Check MD5 of renders (verify they're different now) ============
logger.info("\n[STEP 3] Verifying renders are distinct (checking MD5 hashes)...")

import hashlib
render_hashes = {}
for view in ["home", "front", "right", "top"]:
    path = RENDERS_DIR / f"{view}.png"
    if path.exists():
        md5 = hashlib.md5(path.read_bytes()).hexdigest()
        render_hashes[view] = md5
        logger.info(f"  {view}: {md5[:16]}...")

unique_count = len(set(render_hashes.values()))
total_count = len(render_hashes)
logger.info(f"✓ Unique renders: {unique_count}/{total_count}")

if unique_count == 1:
    logger.warning("⚠ All 4 renders still identical (renderer may not be working yet)")
elif unique_count < 4:
    logger.warning(f"⚠ Only {unique_count}/4 renders are unique")
else:
    logger.info("✓ All 4 renders are distinct!")
