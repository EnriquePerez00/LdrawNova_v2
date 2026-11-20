"""E2E Harness - FASE D: A2 Hardened with Geometric Constraints

Uses the hardened A2 prompt which explicitly instructs segment Z-separation.
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load .env
env_file = Path("/Users/I764690/Code_personal/LdrawNova/.env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ[key.strip()] = val.strip().strip('"')

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import what we need
from ldraw_tools import design_generator
from ldraw_tools.a2_prompt_v2 import build_geometric_constraints_block

# Monkey-patch to use hardened constraints
_original_submodel_instructions = design_generator._submodel_instructions

def _submodel_instructions_v2(segments: list) -> str:
    """Enhanced submodel instructions with geometric constraints (FASE D)."""
    original = _original_submodel_instructions(segments)
    geo_constraints = build_geometric_constraints_block(segments)
    
    if geo_constraints:
        # Insert constraints before MPD STRUCTURE
        idx = original.find("MPD STRUCTURE")
        if idx >= 0:
            return geo_constraints + "\n\n" + original
    
    return original

# Apply patch
design_generator._submodel_instructions = _submodel_instructions_v2

# Now import harness (which uses patched function)
from scripts.bench.harness_e2e_real import run_e2e_real_agents

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--io-file", required=True, help="Path to .io file")
    parser.add_argument("--sample-id", required=True, help="Sample identifier")
    parser.add_argument("--output", default="/tmp/e2e_a2v2", help="Output directory")
    parser.add_argument("--max-iter", type=int, default=2, help="Max iterations")
    parser.add_argument("--permissive-gate", action="store_true", help="(FASE B.2)")
    parser.add_argument("--few-shot", action="store_true", help="(FASE C)")
    
    args = parser.parse_args()
    
    io_file = Path(args.io_file)
    if not io_file.exists():
        print(f"❌ Not found: {io_file}")
        sys.exit(1)
    
    logger.info("[A2-V2] Monkey-patched _submodel_instructions with geometric constraints")
    
    result = run_e2e_real_agents(
        io_file, args.sample_id, args.output, args.max_iter,
        use_real_spec=True,
        use_permissive_gate=args.permissive_gate,
        use_few_shot=args.few_shot
    )
    
    if result:
        print(f"\n✅ SUCCESS: {args.sample_id}")
    else:
        print(f"\n❌ FAILED: {args.sample_id}")
        sys.exit(1)

