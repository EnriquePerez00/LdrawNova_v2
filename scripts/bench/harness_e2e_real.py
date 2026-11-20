"""E2E Harness with real agents (A2, A3, A4) via LiteLLM proxy.

Runs ImprovementLoopV2WithStructural on MICRO tier sets.
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any

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

from ldraw_tools.improvement_loop_v2_with_structural import ImprovementLoopV2WithStructural
from ldraw_tools.profile_adapter import ProfileAdapter
from ldraw_tools import agent_roles
from ldraw_tools.model_router import ModelRouter
from ldraw_tools.structural_diff_config import infer_tier, get_config_for_tier
from scripts.bench.assembly_graph_gt import build_assembly_graph_gt
from scripts.bench.io_loader import count_steps_and_parts
from scripts.bench.recipe_bank import load_recipes, select_recipes
from scripts.bench.render_gt import get_final_gt_renders
from typing import Optional

def generate_spec_from_gt_graph(graph_gt: Dict[str, Any], parts_count: int) -> Dict[str, Any]:
    """Generate a realistic spec from the GT assembly graph.
    
    Instead of generic segments ("Part 0", "Part 1"), infer semantic segments
    from the connectivity structure (connected components, part clusters).
    This gives A2 real structure to work with.
    
    Args:
        graph_gt: Assembly graph from build_assembly_graph_gt
        parts_count: Total parts
    
    Returns:
        A realistic spec dict with segments derived from GT structure.
    """
    segments = []
    
    # Derive segments from GT structure: connected components / clusters
    edges = graph_gt.get("edges_part", [])
    parts_by_id = graph_gt.get("parts_by_id", {})
    
    if not edges or not parts_by_id:
        # Fallback: equal distribution of parts across 3 segments
        parts_per_segment = max(1, parts_count // 3)
        for i in range(min(3, (parts_count + parts_per_segment - 1) // parts_per_segment)):
            segments.append({
                "id": f"seg_{i}",
                "name": f"segment_{i}",
                "type": "assembly",
                "description": f"Structural component (approx {parts_per_segment} parts)",
                "color": ["red", "blue", "green"][i % 3],
                "estimated_size_studs": [4, 4, 2],
                "role": "structural",
            })
    else:
        # Infer segments from connectivity: each connected cluster is a segment
        visited = set()
        cluster_id = 0
        
        for part_id in parts_by_id:
            if part_id in visited:
                continue
            
            # BFS to find connected component
            cluster = set()
            queue = [part_id]
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                cluster.add(curr)
                
                # Find neighbors
                for edge in edges:
                    if edge.get("part_from") == curr and edge.get("part_to") not in visited:
                        queue.append(edge["part_to"])
                    elif edge.get("part_to") == curr and edge.get("part_from") not in visited:
                        queue.append(edge["part_from"])
            
            if cluster:
                segments.append({
                    "id": f"seg_{cluster_id}",
                    "name": f"segment_{cluster_id}",
                    "type": "assembly",
                    "description": f"Connected structure ({len(cluster)} parts)",
                    "color": ["red", "blue", "green", "yellow"][cluster_id % 4],
                    "estimated_size_studs": [4, 4, 2],
                    "role": "structural",
                })
                cluster_id += 1
        
        # Limit to 5 segments for manageability
        segments = segments[:5]
    
    # Return realistic spec
    return {
        "version": 1,
        "profile": "generic",
        "canonical_description": f"LEGO assembly with {parts_count} parts, {len(graph_gt.get('edges_part', []))} connections",
        "segments": segments or [
            {"id": f"seg_{i}", "name": f"segment_{i}", "type": "part", "color": "red", "description": f"Part {i}"}
            for i in range(min(3, parts_count))
        ],
    }


    """Describe ground-truth renders (4 views) using A1 VLM.
    
    FASE 2: A1 analyzes GT images and returns a spec dict describing what it sees.
    
    Args:
        gt_pngs: List of 4 PNG paths [home.png, front.png, right.png, top.png]
        sample_id: Sample identifier (for logging)
        llm_config: LLM config dict
        router: ModelRouter instance
    
    Returns:
        Spec dict {version, profile, segments, ...} derived from GT images.
        None if A1 fails or images are missing.
    """
    if not gt_pngs or len(gt_pngs) < 4:
        logger.warning(f"[A1 VLM] Expected 4 GT PNGs, got {len(gt_pngs)}")
        return None
    
    try:
        logger.info(f"[A1 VLM] Describing GT renders from {sample_id}...")
        logger.debug(f"[A1 VLM] Images: {[p.name for p in gt_pngs]}")
        
        # Call A1 (describe_gt) via agent_roles
        # For now, we'll use a placeholder since agent_roles.describe_gt may not exist yet
        # In production, this would be:
        # spec = agent_roles.describe_gt(gt_pngs, sample_id, llm_config=llm_config)
        
        # Fallback: return a placeholder spec (can be improved once A1 exists)
        logger.warning(f"[A1 VLM] describe_gt not yet implemented; using fallback spec")
        return {
            "version": 1,
            "profile": "generic",
            "segments": [
                {"id": "seg_0", "type": "assembly", "color": "red", "description": "Main assembly from GT images"},
            ],
            "note": "Placeholder: awaiting A1 VLM implementation"
        }
        
    except Exception as e:
        logger.error(f"[A1 VLM] Failed to describe GT renders: {e}")
        return None

    """Generate a realistic spec from the GT assembly graph.
    
    Instead of generic segments ("Part 0", "Part 1"), infer semantic segments
    from the connectivity structure (connected components, part clusters).
    This gives A2 real structure to work with.
    
    Args:
        graph_gt: Assembly graph from build_assembly_graph_gt
        parts_count: Total parts
    
    Returns:
        A realistic spec dict with segments derived from GT structure.
    """
    segments = []
    
    # Derive segments from GT structure: connected components / clusters
    edges = graph_gt.get("edges_part", [])
    parts_by_id = graph_gt.get("parts_by_id", {})
    
    if not edges or not parts_by_id:
        # Fallback: equal distribution of parts across 3 segments
        parts_per_segment = max(1, parts_count // 3)
        for i in range(min(3, (parts_count + parts_per_segment - 1) // parts_per_segment)):
            segments.append({
                "id": f"seg_{i}",
                "name": f"segment_{i}",
                "type": "assembly",
                "description": f"Structural component (approx {parts_per_segment} parts)",
                "color": ["red", "blue", "green"][i % 3],
                "estimated_size_studs": [4, 4, 2],
                "role": "structural",
            })
    else:
        # Infer segments from connectivity: each connected cluster is a segment
        visited = set()
        cluster_id = 0
        
        for part_id in parts_by_id:
            if part_id in visited:
                continue
            
            # BFS to find connected component
            cluster = set()
            queue = [part_id]
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                cluster.add(curr)
                
                # Find neighbors
                for edge in edges:
                    if edge.get("part_from") == curr and edge.get("part_to") not in visited:
                        queue.append(edge["part_to"])
                    elif edge.get("part_to") == curr and edge.get("part_from") not in visited:
                        queue.append(edge["part_from"])
            
            if cluster:
                segments.append({
                    "id": f"seg_{cluster_id}",
                    "name": f"segment_{cluster_id}",
                    "type": "assembly",
                    "description": f"Connected structure ({len(cluster)} parts)",
                    "color": ["red", "blue", "green", "yellow"][cluster_id % 4],
                    "estimated_size_studs": [4, 4, 2],
                    "role": "structural",
                })
                cluster_id += 1
        
        # Limit to 5 segments for manageability
        segments = segments[:5]
    
    # Return realistic spec
    return {
        "version": 1,
        "profile": "generic",
        "canonical_description": f"LEGO assembly with {parts_count} parts, {len(graph_gt.get('edges_part', []))} connections",
        "segments": segments or [
            {"id": f"seg_{i}", "name": f"segment_{i}", "type": "part", "color": "red", "description": f"Part {i}"}
            for i in range(min(3, parts_count))
        ],
    }


def describe_gt_renders_with_a1(gt_pngs: List[Path], sample_id: str, llm_config: Dict[str, Any], adapter: Optional[ProfileAdapter] = None, output_dir_slug: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Describe ground-truth renders (4 views) using A1 VLM (FASE 3 REAL IMPLEMENTATION).
    
    FASE 3: A1 analyzes GT images and returns a spec dict describing what it sees.
    Now calls agent_roles.describe_gt() with real VLM (Gemini).
    
    Args:
        gt_pngs: List of 4 PNG paths [home.png, front.png, right.png, top.png]
        sample_id: Sample identifier (for logging)
        llm_config: LLM config dict with models and credentials
        adapter: ProfileAdapter (default: generic profile if None)
        output_dir_slug: Output directory slug for VLM call artifacts
    
    Returns:
        Spec dict {version, profile, segments, ...} derived from GT images.
        None if A1 fails or images are missing.
    """
    if not gt_pngs or len(gt_pngs) < 4:
        logger.warning(f"[A1 VLM] Expected 4 GT PNGs, got {len(gt_pngs)}")
        return None
    
    # Verify all PNGs exist and are files
    missing = [p for p in gt_pngs if not p.exists()]
    if missing:
        logger.warning(f"[A1 VLM] Missing image files: {missing}")
        return None
    
    try:
        logger.info(f"[A1 VLM] Describing GT renders from {sample_id}...")
        logger.info(f"[A1 VLM] Images: {[p.name for p in gt_pngs]} (total: {sum(p.stat().st_size for p in gt_pngs)/1024:.1f} KB)")
        
        # Create a minimal ProfileAdapter if not provided (generic profile)
        if adapter is None:
            adapter = ProfileAdapter("generic", Path("dummy.json"), Path("dummy.json"))
        
        # FASE 3: Call agent_roles.describe_gt() with REAL VLM
        spec = agent_roles.describe_gt(
            gt_image_paths=gt_pngs,
            profile_adapter=adapter,
            llm_config=llm_config,
            output_dir_slug=output_dir_slug
        )
        
        if spec and spec.get("segments"):
            logger.info(f"[A1 VLM] ✅ GT described: {len(spec.get('segments', []))} segments identified")
            return spec
        else:
            logger.warning(f"[A1 VLM] describe_gt returned empty spec, using fallback")
            return None
        
    except Exception as e:
        logger.error(f"[A1 VLM] Failed to describe GT renders: {e}", exc_info=True)
        return None


def run_e2e_real_agents(
    io_path: Path,
    sample_id: str,
    output_dir: Path,
    max_iterations: int = 2,
    use_real_spec: bool = True,
    use_permissive_gate: bool = False,
    use_few_shot: bool = False
) -> Optional[Dict[str, Any]]:
    """Run E2E loop with real agents on a single .io set.
    
    Args:
        io_path: Path to .io file
        sample_id: Sample identifier
        output_dir: Output directory
        max_iterations: Max iterations (default 2)
        use_real_spec: If True, use GT-derived spec (default True)
        use_permissive_gate: If True, set GATE_MAX_PENETRATIONS=15, GATE_MAX_FLOATING_ISLANDS=15 (FASE B.2)
        use_few_shot: If True, inject few-shot recipes into A2 prompt (FASE C)
    """
    print(f"\n{'='*70}")
    print(f"E2E Real Agents: {sample_id}")
    print(f"{'='*70}")
    
    output_dir = Path(output_dir) / sample_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load .io and extract GT graph
    print(f"\n1. Loading .io and extracting GT graph...")
    try:
        # Extract from filename or use defaults
        graph_gt = build_assembly_graph_gt(io_path, sample_id)
        parts_count = graph_gt.get('parts_count', 0)
        steps = 1  # Simplified
        print(f"  Parts: {parts_count}, Steps: {steps}")
        
        tier = infer_tier(parts_count)
        config = get_config_for_tier(tier)
        print(f"  Tier: {tier}, weight_structural={config['weight_structural']}")
        
        print(f"  GT graph: {graph_gt['parts_count']} parts, {len(graph_gt.get('edges_part', []))} edges")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return None
    
    # Create adapter early (needed for A1 VLM description)
    adapter = ProfileAdapter("generic", Path("dummy.json"), Path("dummy.json"))
    
    # ====== FASE 2: Renderizar GT desde .io y describir con A1 VLM ======
    print(f"\n1b. Rendering ground-truth views from .io...")
    gt_pngs = []
    gt_output_dir = output_dir / "gt_renders"
    try:
        gt_pngs = get_final_gt_renders(io_path, gt_output_dir)
        if gt_pngs:
            print(f"  ✅ Rendered {len(gt_pngs)} GT views: {[p.name for p in gt_pngs]}")
        else:
            print(f"  ⚠️ No GT renders produced (io may be too large or rendering failed)")
    except Exception as e:
        print(f"  ⚠️ GT rendering failed ({e}), will skip A1 VLM description")
    
    # ====== FASE 2b: Describe GT with A1 VLM (if renders available) ======
    print(f"\n1c. Describing ground-truth with A1 VLM...")
    spec = None
    if gt_pngs and len(gt_pngs) >= 4:
        try:
            spec = describe_gt_renders_with_a1(
                gt_pngs, 
                sample_id, 
                llm_config={
                    "base_url": os.getenv("LLM_BASE_URL"),
                    "secret": os.getenv("LLM_SECRET"),
                    "fallback_model": os.getenv("LLM_VLM_FALLBACK_MODEL"),
                    "fallback_base_url": os.getenv("LLM_VLM_FALLBACK_BASE_URL"),
                    "models": {"A1": os.getenv("LLM_A1_MODEL", "gemini-2.5-flash")}
                },
                adapter=adapter,
                output_dir_slug=str(sample_id)
            )
            if spec:
                print(f"  ✅ A1 described GT: {len(spec.get('segments', []))} segments identified")
        except Exception as e:
            print(f"  ⚠️ A1 VLM description failed ({e}), falling back to GT graph spec")
    
    # ====== Fallback: Generate spec from GT graph structure ======
    print(f"\n1d. Generating spec from GT graph structure (fallback)...")
    if spec is None and use_real_spec:
        try:
            spec = generate_spec_from_gt_graph(graph_gt, parts_count)
            print(f"  ✅ Generated spec with {len(spec.get('segments', []))} segments from GT graph")
        except Exception as e:
            print(f"  ⚠️ Failed to generate from GT graph ({e}), using synthetic spec fallback")
    
    # Fallback: synthetic spec if GT derivation disabled or failed
    if spec is None:
        print(f"  Using synthetic spec (fallback)")
        spec = {
            "version": 1,
            "profile": "generic",
            "segments": [
                {"id": f"seg_{i}", "type": "part", "color": "red", "description": f"Part {i}"}
                for i in range(min(3, parts_count))
            ]
        }
    
    # Create loop
    # (adapter already created earlier for A1 VLM)
    router = ModelRouter()
    
    # ====== FASE D: A2V2 Hardened Monkey-Patch ======
    # Apply geometric constraints (Z-offsets) to A2 generation
    try:
        from ldraw_tools import design_generator
        from ldraw_tools.a2_prompt_v2 import build_geometric_constraints_block
        
        _original_submodel_instructions = design_generator._submodel_instructions
        
        def _submodel_instructions_v2(segments):
            original = _original_submodel_instructions(segments)
            geo_constraints = build_geometric_constraints_block(segments)
            return geo_constraints + "\n\n" + original
        
        design_generator._submodel_instructions = _submodel_instructions_v2
        logger.info("[Harness] A2 V2 Hardened (geometric constraints) applied ✅")
    except Exception as e:
        logger.warning(f"[Harness] Failed to apply A2V2 hardening: {e}")
    
    # [LEARNING] Initialize learning hook if enabled
    learning_hook = None
    if os.getenv("LDRAW_ENABLE_LEARNING", "").lower() in {"1", "true", "yes"}:
        try:
            from ldraw_tools.learning_loop_integration import LearningHook
            learning_hook = LearningHook(output_dir, sample_id, router.llm_client)
            logger.info(f"[Harness] Learning hook initialized for {sample_id}")
        except Exception as e:
            logger.warning(f"[Harness] Failed to initialize learning hook: {e}")
    
    loop = ImprovementLoopV2WithStructural(
        spec=spec,
        adapter=adapter,
        output_dir=output_dir,
        max_iter=max_iterations,
        threshold=config['convergence_threshold'],
        router=router,
        io_path=io_path,
        sample_id=sample_id,
        enable_structural_diff=True,
        weight_structural=config['weight_structural'],
        tier=tier,
    )
    loop._learning_hook = learning_hook
    
    # Real agents
    class RealAgentRoles:
        design_3d = staticmethod(agent_roles.design_3d)
        describe_render_blind = staticmethod(agent_roles.describe_render_blind)
        judge_differ = staticmethod(agent_roles.judge_differ)
    
    llm_config = {
        "base_url": os.getenv("LLM_BASE_URL"),
        "secret": os.getenv("LLM_SECRET"),
        "fallback_model": os.getenv("LLM_VLM_FALLBACK_MODEL"),
        "fallback_base_url": os.getenv("LLM_VLM_FALLBACK_BASE_URL"),
        "models": {
            "A1": os.getenv("LLM_A1_MODEL", "gemini-2.5-flash"),
            "A2": os.getenv("LLM_A2_MODEL", "claude-haiku-4-5"),
            "A3": os.getenv("LLM_A3_MODEL", "gemini-2.5-flash"),
            "A4": os.getenv("LLM_A4_MODEL", "gemini-2.5-flash"),
        }
    }
    
    # FASE B.2: Set permissive gate if requested
    if use_permissive_gate:
        os.environ["GATE_MAX_PENETRATIONS"] = "15"
        os.environ["GATE_MAX_FLOATING_ISLANDS"] = "15"
        print(f"\n1c. Gate configured (PERMISSIVE): max_penetrations=15, max_islands=15")
    
    # FASE C: Load and select few-shot recipes if requested
    few_shot_recipes = None
    if use_few_shot:
        recipes_bank_path = Path(__file__).parent / "recipes_seed.json"
        all_recipes = load_recipes(recipes_bank_path)
        if all_recipes:
            few_shot_recipes = select_recipes(spec, all_recipes, k=3)
            llm_config["few_shot_recipes"] = few_shot_recipes
            print(f"\n1d. Few-shot recipes loaded: {len(few_shot_recipes)} selected from {len(all_recipes)}")
        else:
            print(f"\n1d. Few-shot requested but no recipes available")
    
    print(f"\n2. Running loop ({max_iterations} iterations)...")
    try:
        result = loop.run(RealAgentRoles(), llm_config=llm_config)
        
        converged = result.get("converged", False)
        reason = result.get("reason", "unknown")
        iterations = len(loop.iterations)
        best_score = loop.best.score if loop.best else 0
        
        print(f"  ✅ Loop completed:")
        print(f"    Iterations: {iterations}")
        print(f"    Best score: {best_score:.1f}")
        print(f"    Converged: {converged} ({reason})")
        
        # Save results
        results = {
            "sample_id": sample_id,
            "tier": tier,
            "parts_count": parts_count,
            "convergence": converged,
            "iterations": iterations,
            "best_score": best_score,
            "reason": reason,
            "structural_diff_enabled": loop.enable_structural_diff,
            "weight_structural": loop.weight_structural,
            "used_real_spec": use_real_spec and spec is not None and "connected" in spec.get("canonical_description", ""),
        }
        
        result_file = output_dir / "e2e_result.json"
        result_file.write_text(json.dumps(results, indent=2))
        print(f"  Saved: {result_file}")
        
        return results
    
    except Exception as e:
        print(f"  ❌ Loop failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--io-file", required=True, help="Path to .io file")
    parser.add_argument("--sample-id", required=True, help="Sample identifier")
    parser.add_argument("--output", default="/tmp/e2e_real", help="Output directory")
    parser.add_argument("--max-iter", type=int, default=2, help="Max iterations")
    parser.add_argument("--synthetic-spec", action="store_true", help="Use synthetic spec instead of A1 (GT render)")
    parser.add_argument("--permissive-gate", action="store_true", help="(FASE B.2) Set GATE_MAX_PENETRATIONS=15, GATE_MAX_FLOATING_ISLANDS=15")
    parser.add_argument("--few-shot", action="store_true", help="(FASE C) Inject few-shot recipes into A2 prompt")
    
    args = parser.parse_args()
    
    io_file = Path(args.io_file)
    if not io_file.exists():
        print(f"❌ Not found: {io_file}")
        sys.exit(1)
    
    result = run_e2e_real_agents(
        io_file, args.sample_id, args.output, args.max_iter, 
        use_real_spec=not args.synthetic_spec,
        use_permissive_gate=args.permissive_gate,
        use_few_shot=args.few_shot
    )
    if result:
        print(f"\n✅ SUCCESS: {args.sample_id}")
    else:
        print(f"\n❌ FAILED: {args.sample_id}")
        sys.exit(1)
