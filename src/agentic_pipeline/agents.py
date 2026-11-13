"""
Implementation of the 6 Specialized AI Agents for the Independent
PDF -> .io Graph Inference Pipeline.

Optimized for Apple Silicon M4 (P_CORES=8, 48 GB Unified RAM, Metal MPS GPU)
and configured with cost-optimal LLM routing per agent role.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch

from src.apple_silicon import P_CORES, workers_for
from src.connector_occupancy_map import ConnectorOccupancyMap
from src.ldraw_geometry import LDrawGeometryResolver
from src.physical_hypothesis_generator import ConnectionHypothesis, PhysicalHypothesisGenerator
from src.solid_collision_validator import SolidCollisionValidator
from src.step_axonometric_renderer import StepAxonometricRenderer
from src.visual_pose_scorer import VisualPoseScorer
from src.agentic_pipeline.schemas import (
    MODEL_ROUTING_CONFIG,
    CandidatePlacement,
    FailureRootCause,
    GTAuditDiagnosis,
    ProposedFix,
    StepContext,
    VisualROIEvaluation,
)

# LiteLLM client — optional import so the pipeline still runs without it
try:
    from src.agentic_pipeline.litellm_client import LiteLLMClient as _LiteLLMClient
except ImportError:
    _LiteLLMClient = None  # type: ignore


LEARNED_RULES_PATH = "data/agentic_fixes/learned_rules.json"
MIN_FIX_EVIDENCE = 3  # observations of the same failure class before a fix is auto-applied


def classify_part_family(part_id: str) -> str:
    """
    Classifies any LEGO part into a broad functional and geometric taxonomy
    so that learned fixes generalize across sets and across parts of the same family.
    """
    clean = str(part_id).lower().replace(".dat", "").strip()

    # SNOT / Brackets / Modified Studs
    if any(k in clean for k in ["bracket", "44728", "99780", "99781", "36840", "36841", "2436", "99207", "4070", "87087", "11211", "11212", "30414", "32952", "22885"]):
        return "BRACKET_AND_SNOT"

    # Hinges, Turntables, and Articulations
    if any(k in clean for k in ["hinge", "turntable", "click", "3937", "3938", "44301", "44302", "73983", "3614", "2429", "2430"]):
        return "HINGE_AND_ARTICULATION"

    # Technic Pins, Axles, and Beams
    if any(k in clean for k in ["technic", "pin", "axle", "beam", "bush", "32062", "2780", "6558", "4274", "32556", "3705"]):
        return "TECHNIC_CONNECTORS"

    # Slopes and Inverted Slopes
    if any(k in clean for k in ["slope", "curved", "bow", "3040", "3039", "3665", "3660", "85984", "54200", "11477", "15068"]):
        return "SLOPES_AND_CURVES"

    # Plates with Specialized Connectors (clips, bars, handles)
    if any(k in clean for k in ["clip", "bar", "handle", "4081", "2540", "48336", "61252", "11476", "60470", "48729", "30237", "13547"]):
        return "PLATES_WITH_CLIPS_BARS"

    # Tiles (Flat surfaces without studs)
    if any(k in clean for k in ["tile", "3070", "3069", "63864", "98138", "14769", "1751", "35380"]):
        return "TILES_SMOOTH"

    # Jumpers (offset single stud)
    if any(k in clean for k in ["jumper", "15573", "3794", "34103", "88646"]):
        return "JUMPER_PLATES"

    # Thin Plates
    if any(k in clean for k in ["plate", "3024", "3023", "3022", "3021", "3020", "3710", "3666", "3460", "3034", "3832", "4477", "43710"]):
        return "PLATES_STANDARD"

    # Standard Bricks
    if any(k in clean for k in ["brick", "3005", "3004", "3003", "3002", "3001", "3010", "3009", "3008"]):
        return "BRICKS_STANDARD"

    return "GENERAL_PARTS"


def load_learned_rules(rules_path: str = LEARNED_RULES_PATH) -> Dict[str, Any]:
    """Loads accumulated self-improvement rules synthesized by the GT Auditor Agent."""
    default_rules: Dict[str, Any] = {
        "version": 2,
        # Generalized Family-Level Overrides (applies to ALL parts in that family across all MOCs)
        "family_clearance_overrides": {
            "BRACKET_AND_SNOT": 1.2,
            "HINGE_AND_ARTICULATION": 1.5,
            "PLATES_WITH_CLIPS_BARS": 1.0,
            "SLOPES_AND_CURVES": 0.8,
            "JUMPER_PLATES": 0.8,
            "TILES_SMOOTH": 0.5,
            "PLATES_STANDARD": 0.5,
            "BRICKS_STANDARD": 0.5,
        },
        "family_roi_margin_overrides": {
            "BRACKET_AND_SNOT": 0.45,
            "HINGE_AND_ARTICULATION": 0.50,
            "PLATES_WITH_CLIPS_BARS": 0.45,
            "SLOPES_AND_CURVES": 0.40,
            "JUMPER_PLATES": 0.42,
            "PLATES_STANDARD": 0.42,
            "BRICKS_STANDARD": 0.38,
            "TILES_SMOOTH": 0.40,
        },
        "scorer_weight_adjustments": {
            "w_edge": 0.42,
            "w_color": 0.23,
            "w_stud_contact": 0.20,
            "w_neighbor_context": 0.18,
        },
        # Generalized Families that require 3D SO(3) rotations & lateral port exploration
        "families_with_3d_rotations": [
            "BRACKET_AND_SNOT",
            "PLATES_WITH_CLIPS_BARS",
            "HINGE_AND_ARTICULATION",
            "TECHNIC_CONNECTORS",
        ],
        # Specific part overrides (fallback)
        "part_clearance_overrides": {},
        "roi_margin_overrides": {},
        "force_lateral_snot_parts": [],
        "callout_pages_registry": {},
        "flip_pages_registry": {},
        "fixes_history": [],
    }
    if os.path.exists(rules_path):
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Merge nested dictionaries cleanly
            for k, v in loaded.items():
                if isinstance(v, dict) and k in default_rules and isinstance(default_rules[k], dict):
                    default_rules[k].update(v)
                else:
                    default_rules[k] = v
        except Exception:
            pass
    return default_rules


def save_learned_rules(rules: Dict[str, Any], rules_path: str = LEARNED_RULES_PATH) -> None:
    """Persists updated rules synthesized by the GT Auditor Agent."""
    os.makedirs(os.path.dirname(os.path.abspath(rules_path)), exist_ok=True)
    if os.path.exists(rules_path):  # keep a rollback copy before overwriting learned rules
        import shutil
        shutil.copy2(rules_path, rules_path + ".bak")
    with open(rules_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)


# ============================================================================
# AGENT 1: Context & Camera Agent (Cost Tier: flash_lite)
# ============================================================================

class ContextAndCameraAgent:
    """
    Agent 1 (`lego-context-agent`, model=`flash_lite`):
    Detects page-level build context (flip icons, callout subassemblies, part quantities)
    and calibrates the initial 2D axonometric camera parameters from G_{t-1}.
    """
    agent_id = "lego-context-agent"
    model_tier = MODEL_ROUTING_CONFIG["lego-context-agent"]["model"]

    def __init__(self, visual_scorer: VisualPoseScorer, llm_client: Optional[Any] = None):
        self.visual_scorer = visual_scorer
        # Accept an explicit client or auto-create one from env var
        self._llm: Optional[Any] = llm_client
        if self._llm is None and _LiteLLMClient is not None:
            model = os.getenv("LITELLM_MODEL_CONTEXT_AGENT", "")
            if model:
                self._llm = _LiteLLMClient(model=model)

    def _call_context_vlm(self, crop_path: str) -> Dict[str, Any]:
        """
        Calls the VLM with the step crop image to extract structured page metadata.

        Returns a dict with keys: is_flip_step, is_callout, is_docking_step,
        step_number, camera_hint.  Returns {} on any failure so callers can
        fall back to deterministic logic.
        """
        if self._llm is None:
            return {}
        try:
            with open(crop_path, "rb") as fh:
                img_bytes = fh.read()
            # Convert to PNG if needed (OpenCV round-trip)
            if not crop_path.lower().endswith(".png"):
                import cv2 as _cv2
                import numpy as _np
                arr = _np.frombuffer(img_bytes, dtype=_np.uint8)
                decoded = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
                if decoded is not None:
                    _, buf = _cv2.imencode(".png", decoded)
                    img_bytes = buf.tobytes()
            prompt = (
                "You are analyzing a step image from a LEGO instruction manual. "
                "Respond ONLY with a valid JSON object (no markdown fences) with these keys:\n"
                '{"is_flip_step": bool, "is_callout": bool, "is_docking_step": bool, '
                '"step_number": int, "camera_hint": "top"|"front"|"back"|"default"}\n\n'
                "- is_flip_step: true if there is a circular arrow or rotation icon indicating "
                "the model should be flipped or rotated before the next step.\n"
                "- is_callout: true if there is a separate inset box with sub-instructions for "
                "a sub-assembly.\n"
                "- is_docking_step: true if the step shows attaching a completed sub-assembly "
                "onto the main model without any new loose parts.\n"
                "- step_number: the visible step number printed on the page (0 if not visible).\n"
                "- camera_hint: suggested camera angle implied by the illustration."
            )
            result = self._llm.chat(prompt, images=[img_bytes], json_response=True)
            # Normalise booleans in case the model returns strings
            for k in ("is_flip_step", "is_callout", "is_docking_step"):
                if k in result:
                    result[k] = bool(result[k])
            return result
        except Exception:
            return {}

    def analyze_step_page(
        self,
        step_page_data: Dict[str, Any],
        existing_nodes: List[Dict[str, Any]],
        flip_pages: Dict[int, bool],
        current_flipped_state: bool,
        learned_rules: Dict[str, Any],
        set_num: str = "",
    ) -> Tuple[StepContext, Dict[str, Any], Dict[str, Any]]:
        page_num = int(step_page_data.get("page_num", 1))
        step_label = str(step_page_data.get("step_label", f"Step {page_num}"))
        crop_path = str(step_page_data.get("assembly_crop_path", "") or step_page_data.get("crop_path", ""))

        # Check both PDF detector and learned registry for flip icons
        learned_flips = learned_rules.get("flip_pages_registry", {}).get(set_num, [])
        is_flipped = current_flipped_state
        if page_num in flip_pages or page_num in learned_flips:
            is_flipped = not current_flipped_state

        # Check if page is a callout subassembly
        learned_callouts = learned_rules.get("callout_pages_registry", {}).get(set_num, [])
        is_callout = bool(step_page_data.get("is_callout", False) or (page_num in learned_callouts))
        sub_id = f"callout_p{page_num}" if is_callout else "main_model"

        # VLM override — enrich flip/callout detection with visual understanding when crop is available
        if crop_path and os.path.exists(crop_path) and self._llm is not None:
            vlm_ctx = self._call_context_vlm(crop_path)
            if vlm_ctx:
                if vlm_ctx.get("is_flip_step", False):
                    is_flipped = not current_flipped_state  # VLM confirms a flip
                is_callout = is_callout or bool(vlm_ctx.get("is_callout", False))
                if vlm_ctx.get("is_docking_step", False) and not step_page_data.get("items"):
                    # Docking steps have no new parts; VLM confirmation is a signal to skip
                    pass  # items list stays empty — handled downstream
                sub_id = f"callout_p{page_num}" if is_callout else "main_model"

        # Expand part items considering quantity multipliers (1x, 2x, 4x)
        flat_parts: List[Dict[str, Any]] = []
        for it_idx, item in enumerate(step_page_data.get("items", [])):
            el_id = str(item.get("matched_element_id", item.get("element_id", "3001")))
            mt = item.get("matched_template", {})
            raw_p_num = str(mt.get("part_num", item.get("part_id", "3001")))
            color_id = int(mt.get("color_id", item.get("color_code", 71)))
            qty = max(1, int(item.get("qty", 1)))
            for inst_i in range(qty):
                flat_parts.append({
                    "key": f"{it_idx}_{inst_i}",
                    "item_index": it_idx,
                    "instance_index": inst_i,
                    "raw_part_id": raw_p_num,
                    "element_id": el_id,
                    "color_id": color_id,
                    "qty_in_group": qty,
                })

        # Extract visual evidence & calibrate camera from G_{t-1}
        evidence = (
            self.visual_scorer.extract_visual_evidence(crop_path)
            if crop_path and os.path.exists(crop_path)
            else {}
        )
        calib = (
            self.visual_scorer.calibrate_camera_from_prior_state(existing_nodes, evidence, is_flip=is_flipped)
            if evidence and existing_nodes
            else {
                "scale": 2.65,
                "offset": (200.0, 200.0),
                "az_deg": 45.0,
                "el_deg": -25.0 if is_flipped else 30.0,
            }
        )

        ctx = StepContext(
            page_num=page_num,
            step_label=step_label,
            is_flipped=is_flipped,
            is_callout_subassembly=is_callout,
            subassembly_id=sub_id,
            camera_azimuth_deg=float(calib.get("az_deg", 45.0)),
            camera_elevation_deg=float(calib.get("el_deg", -25.0 if is_flipped else 30.0)),
            camera_scale=float(calib.get("scale", 2.65)),
            camera_offset=tuple(calib.get("offset", (200.0, 200.0))),
            parts_to_place=flat_parts,
            crop_image_path=crop_path,
        )
        return ctx, evidence, calib


# ============================================================================
# AGENT 2: Identifier 3D Agent (Cost Tier: flash)
# ============================================================================

class Identifier3DAgent:
    """
    Agent 2 (`lego-identifier-agent`, model=`flash`):
    Identifies candidate 3D placements for each new part based on:
      - Associated 3D LDraw geometry (`LDrawGeometryResolver`)
      - Available free ports in the prior graph (`ConnectorOccupancyMap`)
      - Necessary orientations (canonical Y, full SO(3) SNOT, or hinge angles)
      - Bilateral symmetry when placing paired parts (`qty >= 2`)
    """
    agent_id = "lego-identifier-agent"
    model_tier = MODEL_ROUTING_CONFIG["lego-identifier-agent"]["model"]

    def __init__(
        self,
        geom_resolver: LDrawGeometryResolver,
        hypothesis_gen: PhysicalHypothesisGenerator,
    ):
        self.geom = geom_resolver
        self.hypothesis_gen = hypothesis_gen

    def propose_placements(
        self,
        part_spec: Dict[str, Any],
        existing_nodes: List[Dict[str, Any]],
        occupancy_map: ConnectorOccupancyMap,
        step_context: StepContext,
        calib: Optional[Dict[str, Any]],
        learned_rules: Dict[str, Any],
        prior_sibling_hypothesis: Optional[ConnectionHypothesis] = None,
        relax_roi_filter: bool = False,
    ) -> List[ConnectionHypothesis]:
        raw_part_id = part_spec["raw_part_id"]
        resolved_part_id = self.geom.resolve_compatible_part_id(raw_part_id)
        element_id = part_spec["element_id"]
        color_id = int(part_spec["color_id"])

        # Root part on empty graph -> place at origin on ground Y=0.0
        if not existing_nodes:
            tf = np.eye(4, dtype=np.float32)
            meta = self.geom.get_part_meta(resolved_part_id)
            bbox = meta.get("bbox", [-10, -8, -10, 10, 0, 10])
            root_hyp = ConnectionHypothesis(
                child_part_id=resolved_part_id,
                child_element_id=element_id,
                rotation_matrix=np.eye(3, dtype=np.float32),
                translation=np.array([0.0, 0.0, 0.0], dtype=np.float32),
                absolute_transform=tf,
                parent_part_index=-1,
                matched_studs=[(0.0, 0.0, 0.0)],
                stud_count=len(meta.get("studs", [])) or 1,
                world_bbox=[float(v) for v in bbox],
                color_id=color_id,
                total_score=1.0,
            )
            return [root_hyp]

        candidates: List[ConnectionHypothesis] = []

        # 1. If placing the 2nd instance of an identical part in the same step, prioritize symmetric twin
        if prior_sibling_hypothesis is not None and prior_sibling_hypothesis.child_part_id == resolved_part_id:
            twins = self.hypothesis_gen.generate_symmetric_twin_hypothesis(
                prior_sibling_hypothesis,
                resolved_part_id,
                element_id,
                existing_nodes,
                color_id=color_id,
            )
            for tw in twins:
                tw.is_symmetric_twin = True
                candidates.append(tw)

        # 2. Port-matching gating via ConnectorOccupancyMap when free ports are tracked
        conn_filter = None if relax_roi_filter else calib
        try:
            port_gated = self.hypothesis_gen.generate_candidates_from_port_matching(
                child_part_id=resolved_part_id,
                child_element_id=element_id,
                occupancy_map=occupancy_map,
                existing_nodes=existing_nodes,
                is_flip=step_context.is_flipped,
                color_id=color_id,
                lazy_collision_check=True,
                connector_2d_filter=conn_filter,
            )
            candidates.extend(port_gated)
        except Exception:
            pass

        # 3. Standard geometric stud-to-socket + SNOT hypothesis generation
        part_fam = classify_part_family(resolved_part_id)
        families_3d = learned_rules.get("families_with_3d_rotations", [])
        force_snot = (
            resolved_part_id in learned_rules.get("force_lateral_snot_parts", [])
            or part_fam in families_3d
        )
        geom_cands = self.hypothesis_gen.generate_candidate_hypotheses(
            resolved_part_id,
            element_id,
            existing_nodes,
            is_flip=step_context.is_flipped,
            color_id=color_id,
            connector_2d_filter=conn_filter,
            lazy_collision_check=True,
            force_3d_rotations=force_snot,
        )
        if not geom_cands and conn_filter is not None:
            geom_cands = self.hypothesis_gen.generate_candidate_hypotheses(
                resolved_part_id,
                element_id,
                existing_nodes,
                is_flip=step_context.is_flipped,
                color_id=color_id,
                connector_2d_filter=None,
                lazy_collision_check=True,
                force_3d_rotations=force_snot,
            )
        candidates.extend(geom_cands)

        # Deduplicate hypotheses by (translation rounded to 1 LDU, yaw rounded to 5 deg)
        unique_cands: List[ConnectionHypothesis] = []
        seen_poses = set()
        for c in candidates:
            pose_key = (
                round(float(c.translation[0]), 0),
                round(float(c.translation[1]), 0),
                round(float(c.translation[2]), 0),
                round(float(c.yaw_deg) % 360.0, 0),
            )
            if pose_key not in seen_poses:
                seen_poses.add(pose_key)
                # Compute Identifier structural prior score (stud contacts + parent bridging + symmetry bonus)
                sym_bonus = 0.35 if getattr(c, "is_symmetric_twin", False) else 0.0
                bridge_bonus = 0.20 * max(0, int(getattr(c, "bridged_parents", 1)) - 1)
                stud_score = min(1.0, float(len(c.matched_studs)) / 4.0)
                c.total_score = stud_score + bridge_bonus + sym_bonus
                unique_cands.append(c)

        unique_cands.sort(key=lambda h: h.total_score, reverse=True)
        return unique_cands


# ============================================================================
# AGENT 3: Physical Guardian Agent (Cost Tier: flash_lite)
# ============================================================================

class PhysicalGuardianAgent:
    """
    Agent 3 (`lego-guardian-agent`, model=`flash_lite`):
    Deterministically validates physical constraints before expensive 3D visual rendering:
      1. Stud-to-Socket / compatible PortType alignment.
      2. Zero solid volumetric collision (SAT OBB / mesh intersection).
      3. Stud exclusivity within the current step.
      4. Surface & Ground level rules (at most 4 parts touching ground after normalization).
    """
    agent_id = "lego-guardian-agent"
    model_tier = MODEL_ROUTING_CONFIG["lego-guardian-agent"]["model"]

    def __init__(self, solid_validator: SolidCollisionValidator):
        self.solid_validator = solid_validator

    def filter_physically_valid(
        self,
        candidates: List[ConnectionHypothesis],
        existing_nodes: List[Dict[str, Any]],
        occupied_step_studs: set,
        learned_rules: Dict[str, Any],
        is_flipped: bool = False,
        max_keep: int = 36,
    ) -> Tuple[List[ConnectionHypothesis], List[Dict[str, Any]]]:
        if not existing_nodes:
            return candidates[:max_keep], []

        valid_list: List[ConnectionHypothesis] = []
        rejection_diagnostics: List[Dict[str, Any]] = []

        for cand in candidates:
            part_id = cand.child_part_id
            part_fam = classify_part_family(part_id)
            # Check family-level clearance override first, then part-specific override
            fam_tol = float(
                learned_rules.get("family_clearance_overrides", {}).get(part_fam, 0.5)
            )
            pen_thresh = float(
                learned_rules.get("part_clearance_overrides", {}).get(part_id, fam_tol)
            )

            # 1. Check stud exclusivity with siblings already placed in this step
            cand_studs = {tuple(np.round(s, 1)) for s in cand.matched_studs}
            if cand_studs and cand_studs.intersection(occupied_step_studs):
                rejection_diagnostics.append({
                    "part_id": part_id,
                    "translation": cand.translation.tolist(),
                    "reason": "STUD_ALREADY_OCCUPIED_IN_STEP",
                })
                continue

            # 2. Check Stud-to-Socket / Port connection existence
            if not cand.matched_studs and not cand.matched_port_pairs and cand.parent_part_index is None:
                rejection_diagnostics.append({
                    "part_id": part_id,
                    "translation": cand.translation.tolist(),
                    "reason": "NO_STUD_OR_PORT_CONNECTION",
                })
                continue

            # 3. Solid 3D OBB / Polygon Non-Penetration check
            is_solid_ok, err_msg = self.solid_validator.validate_new_part_placement(
                part_id,
                cand.absolute_transform,
                existing_nodes,
                penetration_threshold=pen_thresh,
            )
            if not is_solid_ok:
                rejection_diagnostics.append({
                    "part_id": part_id,
                    "translation": cand.translation.tolist(),
                    "reason": f"SOLID_COLLISION: {err_msg}",
                })
                continue

            valid_list.append(cand)
            if len(valid_list) >= max_keep:
                break

        return valid_list, rejection_diagnostics


# ============================================================================
# AGENT 4: Placer Visual ROI Agent (Cost Tier: flash + MPS GPU)
# ============================================================================

class PlacerVisualROIAgent:
    """
    Agent 4 (`lego-placer-agent`, model=`flash`, accelerator=`mps`):
    Mounts candidate graphs onto G_{t-1}, renders their 3D axonometric projections,
    and visually compares the rendered 3D model against the 2D manual page image
    specifically within the **Region of Interest (ROI) dilated with a context margin**
    so neighboring reference pieces are included in the visual verification.
    """
    agent_id = "lego-placer-agent"
    model_tier = MODEL_ROUTING_CONFIG["lego-placer-agent"]["model"]

    def __init__(
        self,
        step_renderer: StepAxonometricRenderer,
        visual_scorer: VisualPoseScorer,
        geom_resolver: LDrawGeometryResolver,
        llm_client: Optional[Any] = None,
    ):
        self.renderer = step_renderer
        self.visual_scorer = visual_scorer
        self.geom = geom_resolver
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        # VLM client for tiebreaking — auto-create from env var if not provided
        self._llm: Optional[Any] = llm_client
        if self._llm is None and _LiteLLMClient is not None:
            model = os.getenv("LITELLM_MODEL_PLACER_AGENT", "")
            if model:
                self._llm = _LiteLLMClient(model=model)

    def _render_candidate_to_png(
        self,
        candidate: ConnectionHypothesis,
        existing_nodes: List[Dict[str, Any]],
        step_context: StepContext,
        calib: Dict[str, Any],
        width: int = 512,
        height: int = 512,
    ) -> Optional[bytes]:
        """
        Renders the existing assembly plus the candidate part as the active new piece.
        Returns PNG bytes for VLM consumption, or None on failure.
        """
        try:
            # Build a temporary node for the candidate
            cand_node = {
                "part_index": -1,  # temporary index
                "part_id": candidate.child_part_id,
                "element_id": candidate.child_element_id,
                "color_id": candidate.color_id,
                "absolute_transform": candidate.absolute_transform.flatten().tolist(),
                "connections": [{"parent_part_index": candidate.parent_part_index}] if candidate.parent_part_index >= 0 else [],
                "is_minifig": False,
            }

            # Combine existing nodes with candidate as the only "step" node
            all_nodes = existing_nodes + [cand_node]
            step_nodes = [cand_node]

            # Get color template mapping
            tmpl_by_element = {}
            for n in existing_nodes:
                el_id = n.get("element_id")
                if el_id and el_id not in tmpl_by_element:
                    tmpl_by_element[el_id] = {"color_rgb": n.get("color_rgb", "#94a3b8")}
            # Add candidate's color
            tmpl_by_element[candidate.child_element_id] = {"color_rgb": "#94a3b8"}

            # Render using the step renderer
            img = self.renderer.render_step_assembly(
                current_page_num=step_context.page_num,
                step_nodes=step_nodes,
                all_nodes=all_nodes,
                tmpl_by_element=tmpl_by_element,
                is_flip=step_context.is_flipped,
                width=width,
                height=height,
            )

            # Encode to PNG bytes
            ok, buf = cv2.imencode(".png", img)
            if ok:
                return buf.tobytes()
            return None
        except Exception:
            return None

    def _call_placer_vlm(
        self,
        crop_path: str,
        render_a_bytes: bytes,
        render_b_bytes: bytes,
    ) -> Dict[str, Any]:
        """
        Calls the VLM with 3 images: [manual_crop, render_A, render_B].
        Asks which render visually matches the manual step better.
        Returns dict with 'winner': 'A'|'B', 'reason': str, or {} on failure.
        """
        if self._llm is None:
            return {}
        try:
            # Read and convert manual crop to PNG bytes
            with open(crop_path, "rb") as fh:
                crop_bytes = fh.read()
            if not crop_path.lower().endswith(".png"):
                arr = np.frombuffer(crop_bytes, dtype=np.uint8)
                decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if decoded is not None:
                    _, buf = cv2.imencode(".png", decoded)
                    crop_bytes = buf.tobytes()

            prompt = (
                "You are comparing two 3D renders of a LEGO part placement against a manual step image.\n\n"
                "Image 1: The manual step crop from the instruction booklet.\n"
                "Image 2: Render A — candidate placement A in context.\n"
                "Image 3: Render B — candidate placement B in context.\n\n"
                "Which render (A or B) visually matches the manual step BETTER? Consider:\n"
                "- Position relative to neighboring parts\n"
                "- Orientation and stud alignment\n"
                "- Overall visual coherence with the step illustration\n\n"
                "Respond ONLY with a valid JSON object (no markdown) with these keys:\n"
                '{"winner": "A"|"B", "reason": "brief explanation"}'
            )

            result = self._llm.chat(prompt, images=[crop_bytes, render_a_bytes, render_b_bytes], json_response=True)
            if result and "winner" in result and result["winner"] in ("A", "B"):
                return result
            return {}
        except Exception:
            return {}

    def compute_contextual_roi_bbox(
        self,
        hypothesis: ConnectionHypothesis,
        existing_nodes: List[Dict[str, Any]],
        calib: Dict[str, Any],
        image_shape: Tuple[int, int],
        roi_margin_ratio: float = 0.35,
    ) -> Tuple[Tuple[int, int, int, int], List[Dict[str, Any]]]:
        """
        Projects the candidate 3D part AND its immediate 3D neighboring parts (within 40 LDU)
        onto the 2D manual image plane, expanding the bounding box by `roi_margin_ratio`
        so that local topological alignment with adjacent pieces is captured.
        """
        img_h, img_w = image_shape[:2]
        scale = float(calib.get("scale", 2.65))
        offset = calib.get("offset", (img_w / 2.0, img_h / 2.0))
        az_deg = float(calib.get("az_deg", 45.0))
        el_deg = float(calib.get("el_deg", 30.0))

        # Project the 8 corners of the candidate's world bounding box
        wb = hypothesis.world_bbox
        if not wb or len(wb) < 6:
            t = hypothesis.translation
            wb = [t[0] - 20, t[1] - 24, t[2] - 20, t[0] + 20, t[1], t[2] + 20]

        corners_3d = np.array([
            [wb[0], wb[1], wb[2]],
            [wb[3], wb[1], wb[2]],
            [wb[0], wb[4], wb[2]],
            [wb[3], wb[4], wb[2]],
            [wb[0], wb[1], wb[5]],
            [wb[3], wb[1], wb[5]],
            [wb[0], wb[4], wb[5]],
            [wb[3], wb[4], wb[5]],
        ], dtype=np.float32)

        pts_2d, _ = self.renderer.project_points(
            corners_3d, az_deg=az_deg, el_deg=el_deg, scale=scale, offset=offset
        )
        xs = pts_2d[:, 0]
        ys = pts_2d[:, 1]
        x0, x1 = float(np.min(xs)), float(np.max(xs))
        y0, y1 = float(np.min(ys)), float(np.max(ys))

        # Find neighboring 3D parts within 45 LDU of the candidate center to include in ROI context
        cand_center = np.array(hypothesis.translation, dtype=np.float32)
        neighbor_nodes: List[Dict[str, Any]] = []
        for n in existing_nodes:
            tf_flat = n.get("absolute_transform", [])
            if len(tf_flat) == 16:
                n_pos = np.array([tf_flat[3], tf_flat[7], tf_flat[11]], dtype=np.float32)
                if float(np.linalg.norm(n_pos - cand_center)) <= 55.0:
                    neighbor_nodes.append(n)

        # Apply slack margin (`roi_margin_ratio`) around the projected piece box
        box_w = max(24.0, x1 - x0)
        box_h = max(24.0, y1 - y0)
        pad_x = box_w * roi_margin_ratio + 14.0
        pad_y = box_h * roi_margin_ratio + 14.0

        rx0 = max(0, int(round(x0 - pad_x)))
        ry0 = max(0, int(round(y0 - pad_y)))
        rx1 = min(img_w, int(round(x1 + pad_x)))
        ry1 = min(img_h, int(round(y1 + pad_y)))

        return (rx0, ry0, rx1, ry1), neighbor_nodes

    def evaluate_and_rank_in_roi(
        self,
        valid_candidates: List[ConnectionHypothesis],
        existing_nodes: List[Dict[str, Any]],
        evidence: Dict[str, Any],
        calib: Dict[str, Any],
        step_context: StepContext,
        learned_rules: Dict[str, Any],
    ) -> Tuple[List[ConnectionHypothesis], Dict[int, VisualROIEvaluation]]:
        """
        Mounts each physically valid hypothesis onto the existing assembly, evaluates
        the 2D-3D visual match inside the contextual ROI (with margin for neighboring parts)
        on MPS GPU, and returns candidates sorted by combined score.
        """
        if not valid_candidates:
            return [], {}

        roi_evals: Dict[int, VisualROIEvaluation] = {}
        weights = learned_rules.get("scorer_weight_adjustments", {})
        w_edge = float(weights.get("w_edge", 0.42))
        w_color = float(weights.get("w_color", 0.23))
        w_stud = float(weights.get("w_stud_contact", 0.20))
        w_neighbor = float(weights.get("w_neighbor_context", 0.15))

        # If no raster/vector image is available, rank by physical contact & neighbor proximity
        if not evidence:
            for idx, c in enumerate(valid_candidates):
                stud_sc = min(1.0, len(c.matched_studs) / 4.0)
                bridge_sc = min(1.0, getattr(c, "bridged_parents", 1) / 2.0)
                c.total_score = 0.65 * stud_sc + 0.35 * bridge_sc
                roi_evals[id(c)] = VisualROIEvaluation(
                    roi_bbox_px=(0, 0, 0, 0),
                    roi_margin_ratio=0.35,
                    neighbor_parts_included=0,
                    stud_occlusion_score=stud_sc,
                    neighbor_context_score=bridge_sc,
                    combined_visual_score=c.total_score,
                )
            valid_candidates.sort(key=lambda h: h.total_score, reverse=True)
            return valid_candidates, roi_evals

        scale = float(calib.get("scale", 2.65))
        offset = calib.get("offset", (200.0, 200.0))
        az_deg = float(calib.get("az_deg", 45.0))
        el_deg = float(calib.get("el_deg", -25.0 if step_context.is_flipped else 30.0))

        # 1. Prune to top candidates that overlap the 2D differential ROI
        roi_filtered = self.visual_scorer.filter_hypotheses_by_2d_roi(
            valid_candidates,
            evidence,
            scale=scale,
            offset=offset,
            el_deg=el_deg,
            max_keep=min(36, len(valid_candidates)),
        )
        if not roi_filtered:
            roi_filtered = valid_candidates[:24]

        # 2. Batch MPS GPU evaluation of wireframe Chamfer edges & Color consistency
        edge_scores = self.visual_scorer.score_chamfer_batch_mps(
            roi_filtered,
            evidence,
            scale=scale,
            offset=offset,
            az_deg=az_deg,
            el_deg=el_deg,
        )
        color_scores = self.visual_scorer.score_color_batch_mps(
            roi_filtered,
            evidence,
            scale=scale,
            offset=offset,
            az_deg=az_deg,
            el_deg=el_deg,
        )

        img_shape = evidence.get("img_bgr", np.zeros((400, 400, 3), dtype=np.uint8)).shape

        # 3. Contextual ROI evaluation (including neighboring pieces within margin)
        for cand, e_sc, c_sc in zip(roi_filtered, edge_scores, color_scores):
            part_fam = classify_part_family(cand.child_part_id)
            fam_margin = float(
                learned_rules.get("family_roi_margin_overrides", {}).get(part_fam, 0.40)
            )
            part_margin = float(
                learned_rules.get("roi_margin_overrides", {}).get(cand.child_part_id, fam_margin)
            )
            roi_bbox, neighbors = self.compute_contextual_roi_bbox(
                cand,
                existing_nodes,
                calib,
                image_shape=img_shape,
                roi_margin_ratio=part_margin,
            )

            # Neighbor context score: rewards placements that connect coherently with local neighborhood
            # and bridge multiple parent bricks in the ROI
            neighbor_cnt = len(neighbors)
            bridge_bonus = min(1.0, 0.35 * max(0, int(getattr(cand, "bridged_parents", 1)) - 1))
            local_coherence = min(1.0, 0.25 * min(neighbor_cnt, 4) + bridge_bonus)
            stud_contact_sc = min(1.0, float(len(cand.matched_studs)) / 4.0)
            sym_bonus = 0.15 if getattr(cand, "is_symmetric_twin", False) else 0.0

            combined_sc = (
                w_edge * float(e_sc)
                + w_color * float(c_sc)
                + w_stud * stud_contact_sc
                + w_neighbor * local_coherence
                + sym_bonus
            )
            cand.edge_score = float(e_sc)
            cand.color_score = float(c_sc)
            cand.neighbor_score = float(local_coherence)
            cand.total_score = float(combined_sc)

            roi_evals[id(cand)] = VisualROIEvaluation(
                roi_bbox_px=roi_bbox,
                roi_margin_ratio=part_margin,
                neighbor_parts_included=neighbor_cnt,
                edge_chamfer_score=round(float(e_sc), 4),
                silhouette_iou_score=round(float(getattr(cand, "iou_score", e_sc * 0.92)), 4),
                color_match_score=round(float(c_sc), 4),
                stud_occlusion_score=round(stud_contact_sc, 4),
                neighbor_context_score=round(local_coherence, 4),
                combined_visual_score=round(float(combined_sc), 4),
            )

        roi_filtered.sort(key=lambda h: h.total_score, reverse=True)

        # VLM Tiebreaker: if top-2 candidates are very close in score, use VLM to decide
        tie_threshold = float(os.getenv("PLACER_VLM_TIE_THRESHOLD", "0.05"))
        crop_path = step_context.crop_image_path
        if (
            len(roi_filtered) >= 2
            and self._llm is not None
            and crop_path
            and os.path.exists(crop_path)
            and abs(roi_filtered[0].total_score - roi_filtered[1].total_score) < tie_threshold
        ):
            # Render top-2 candidates to PNG bytes
            render_a = self._render_candidate_to_png(roi_filtered[0], existing_nodes, step_context, calib)
            render_b = self._render_candidate_to_png(roi_filtered[1], existing_nodes, step_context, calib)
            if render_a and render_b:
                vlm_result = self._call_placer_vlm(crop_path, render_a, render_b)
                winner = vlm_result.get("winner")
                if winner == "A":
                    roi_filtered[0].total_score += 1e-3
                elif winner == "B":
                    roi_filtered[1].total_score += 1e-3
                # Re-sort after potential score boost
                roi_filtered.sort(key=lambda h: h.total_score, reverse=True)

        return roi_filtered, roi_evals


# ============================================================================
# AGENT 5: Temporal Supervisor Agent (Cost Tier: flash)
# ============================================================================

class TemporalSupervisorAgent:
    """
    Agent 5 (`lego-supervisor-agent`, model=`flash`):
    Enforces final ground normalization (Y <= 0.0, <= 4 base parts).
    NOTE: temporal beam search / cross-step backtracking is NOT implemented; the only
    backtracking is the per-piece Guardian -> Identifier ROI relaxation in the orchestrator.
    """
    agent_id = "lego-supervisor-agent"
    model_tier = MODEL_ROUTING_CONFIG["lego-supervisor-agent"]["model"]

    @staticmethod
    def normalize_assembly_ground(nodes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Renormalizes the assembly so that min(Y_bottom) aligns with ground Y = 0.0
        (in LDraw coordinates +Y points downward, so max(y_bottom_ldu) is the ground plane).
        """
        if not nodes:
            return nodes, 0

        max_y = max(float(n.get("y_bottom_ldu", 0.0)) for n in nodes)
        for n in nodes:
            y_norm = float(n.get("y_bottom_ldu", 0.0)) - max_y
            n["y_bottom_normalized"] = round(y_norm, 3)
            n["level_normalized"] = int(round(abs(y_norm) / 8.0))
            if "absolute_transform" in n and len(n["absolute_transform"]) == 16:
                n["absolute_transform"][7] = round(float(n["absolute_transform"][7]) - max_y, 3)

        ground_touching = sum(
            1 for n in nodes if abs(float(n.get("y_bottom_normalized", 999.0))) <= 1.0
        )
        return nodes, ground_touching


# ============================================================================
# AGENT 6: Ground-Truth (.io) Auditor & Auto-Fixer Agent (Cost Tier: pro)
# ============================================================================

class GTAuditorAndFixerAgent:
    """
    Agent 6 (`lego-gt-auditor-agent`, model=`pro`):
    Leverages the ~300 pairs of (.pdf manual, .io Ground Truth graph) to:
      1. Verify if each placed part matches the Ground Truth .io pose (accounting for part symmetry).
      2. When a discrepancy occurs, inspect the trace of Identifier -> Guardian -> Placer
         to diagnose the exact root cause.
      3. Synthesize and persist an actionable Fix into `learned_rules.json` so subsequent
         runs and holdout manuals automatically benefit.
    """
    agent_id = "lego-gt-auditor-agent"
    model_tier = MODEL_ROUTING_CONFIG["lego-gt-auditor-agent"]["model"]

    def __init__(
        self,
        geom_resolver: LDrawGeometryResolver,
        pos_tol_ldu: float = 1.5,
        rot_tol_deg: float = 5.0,
        llm_client: Optional[Any] = None,
    ):
        self.geom = geom_resolver
        self.pos_tol_ldu = pos_tol_ldu
        self.rot_tol_deg = rot_tol_deg
        # LLM client for deep diagnosis — auto-create from env var if not provided
        self._llm: Optional[Any] = llm_client
        if self._llm is None and _LiteLLMClient is not None:
            model = os.getenv("LITELLM_MODEL_AUDITOR_AGENT", "")
            if model:
                self._llm = _LiteLLMClient(model=model)

    def _call_auditor_llm(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep LLM diagnosis for unresolved IDENTIFIER_RECALL_MISS failures.

        Builds a JSON context dict from the funnel trace and asks the model for:
          - root_cause_hypothesis: string explanation
          - parameter_patch: dict of parameter changes to try
          - recommendation: human-readable summary

        Returns {} on any failure.
        """
        if self._llm is None:
            return {}
        try:
            ctx_str = json.dumps(context, ensure_ascii=False, indent=2)
            prompt = (
                "You are an expert LEGO assembly AI debugger.\n\n"
                "A 3D part placement pipeline failed to find the correct pose for a part. "
                "Here is the full diagnostic context from the inference funnel:\n\n"
                f"{ctx_str}\n\n"
                "Analyze this failure and respond ONLY with a valid JSON object (no markdown) "
                "containing:\n"
                '{"root_cause_hypothesis": "<concise explanation of why the GT pose was missed>",\n'
                ' "parameter_patch": {<optional: parameter key-value pairs to try, e.g. '
                '"family_clearance_overrides": {"PLATES_STANDARD": 1.5}>},\n'
                ' "recommendation": "<actionable fix in one sentence>"}'
            )
            result = self._llm.chat(prompt, images=None, json_response=True, cache=True)
            return result
        except Exception:
            return {}

    def _pose_matches_gt(
        self,
        cand_tf: np.ndarray,
        gt_tf: np.ndarray,
        part_id: str,
    ) -> Tuple[bool, float, float]:
        """Checks if candidate 4x4 transform matches GT transform within LDU & symmetry tolerances."""
        cand_t = cand_tf[:3, 3]
        gt_t = gt_tf[:3, 3]
        pos_err = float(np.linalg.norm(cand_t - gt_t))

        cand_R = cand_tf[:3, :3]
        gt_R = gt_tf[:3, :3]
        meta = self.geom.get_part_meta(part_id)
        sym_order = max(1, int(meta.get("symmetry_order", 1)))

        best_rot_err = 180.0
        for k in range(sym_order):
            rad = math.radians(k * (360.0 / sym_order))
            c, s = math.cos(rad), math.sin(rad)
            Ry = np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]], dtype=np.float32)
            R_rel = cand_R.T @ (gt_R @ Ry)
            cos_val = max(-1.0, min(1.0, (float(np.trace(R_rel)) - 1.0) / 2.0))
            err = float(math.degrees(math.acos(cos_val)))
            if err < best_rot_err:
                best_rot_err = err

        is_exact = (pos_err <= self.pos_tol_ldu) and (best_rot_err <= self.rot_tol_deg)
        return is_exact, round(pos_err, 3), round(best_rot_err, 2)

    def audit_part_placement(
        self,
        step_num: int,
        piece_idx: int,
        part_id: str,
        color_id: int,
        chosen_hypothesis: Optional[ConnectionHypothesis],
        identifier_candidates: List[ConnectionHypothesis],
        guardian_valid_candidates: List[ConnectionHypothesis],
        placer_ranked_candidates: List[ConnectionHypothesis],
        gt_node: Dict[str, Any],
        learned_rules: Dict[str, Any],
        set_num: str = "",
        prior_audit_results: Optional[List["GTAuditDiagnosis"]] = None,
    ) -> GTAuditDiagnosis:
        gt_tf = np.array(gt_node["absolute_transform"], dtype=np.float32).reshape(4, 4)
        gt_pos = gt_tf[:3, 3].tolist()

        if chosen_hypothesis is not None:
            pred_tf = chosen_hypothesis.absolute_transform
            pred_pos = chosen_hypothesis.translation.tolist()
            is_exact, pos_err, rot_err = self._pose_matches_gt(pred_tf, gt_tf, part_id)
        else:
            pred_pos = None
            is_exact, pos_err, rot_err = False, 999.0, 180.0

        # Check where the GT pose was in the pipeline funnel
        gt_in_identifier = any(
            self._pose_matches_gt(c.absolute_transform, gt_tf, part_id)[0]
            for c in identifier_candidates
        )
        gt_in_guardian = any(
            self._pose_matches_gt(c.absolute_transform, gt_tf, part_id)[0]
            for c in guardian_valid_candidates
        )
        gt_rank_in_placer: Optional[int] = None
        for r_idx, c in enumerate(placer_ranked_candidates):
            if self._pose_matches_gt(c.absolute_transform, gt_tf, part_id)[0]:
                gt_rank_in_placer = r_idx + 1
                break

        if is_exact:
            return GTAuditDiagnosis(
                step_num=step_num,
                piece_idx=piece_idx,
                part_id=part_id,
                color_id=color_id,
                is_exact_match=True,
                pos_error_ldu=pos_err,
                rot_error_deg=rot_err,
                gt_translation_ldu=[round(v, 2) for v in gt_pos],
                inferred_translation_ldu=[round(v, 2) for v in pred_pos] if pred_pos else None,
                gt_was_in_identifier_candidates=True,
                gt_survived_guardian_filter=True,
                gt_visual_rank_in_placer=1,
                root_cause=FailureRootCause.EXACT_MATCH.value,
                diagnostic_explanation="La pieza coincide exactamente con el grafo Ground Truth (.io).",
                proposed_fix=None,
            )

        # Fix 2.1 — Detect UPSTREAM_CASCADE_ERROR before any other branch.
        # If the immediately-preceding piece in the same step also failed, it is
        # very likely that the current piece failed because it tried to connect
        # to a wrongly-placed parent, not because of an independent recall miss.
        if prior_audit_results:
            recent_failures = [
                r for r in prior_audit_results
                if r.step_num == step_num and not r.is_exact_match
                and r.root_cause != FailureRootCause.UPSTREAM_CASCADE_ERROR.value
            ]
            if recent_failures:
                part_family = classify_part_family(part_id)
                fix_id = f"gen_fix_{part_family}_{set_num}_s{step_num}_p{piece_idx}"
                upstream_part = recent_failures[-1].part_id
                explanation = (
                    f"Cascada detectada: la pieza precedente `{upstream_part}` en el paso {step_num} "
                    f"también falló. La pose GT {gt_pos} de `{part_id}` es inalcanzable porque el padre "
                    f"inmediato está mal colocado (pos_err={pos_err} LDU)."
                )
                proposed_fix = ProposedFix(
                    fix_id=fix_id,
                    target_agent="lego-identifier-agent",
                    root_cause=FailureRootCause.UPSTREAM_CASCADE_ERROR.value,
                    part_id=part_id,
                    step_num=step_num,
                    description=(
                        f"[CASCADE] La pieza `{part_id}` falla porque su padre `{upstream_part}` "
                        f"estaba mal colocado. No aplicar patch de parámetros — resolver la causa raíz upstream."
                    ),
                    parameter_patch={},
                    applied_automatically=False,
                )
                # Cascade errors are counted in root_causes but do NOT apply
                # parameter patches (the upstream root cause will handle that).
                key = f"{proposed_fix.target_agent}:{proposed_fix.root_cause}:{part_family}"
                learned_rules.setdefault("fix_evidence", {})[key] = (
                    int(learned_rules["fix_evidence"].get(key, 0)) + 1
                )
                history = learned_rules.setdefault("fixes_history", [])
                if not any(h.get("fix_id") == fix_id for h in history):
                    history.append({
                        "fix_id": fix_id,
                        "target_agent": proposed_fix.target_agent,
                        "root_cause": proposed_fix.root_cause,
                        "part_id": part_id,
                        "step_num": step_num,
                        "description": proposed_fix.description,
                    })
                return GTAuditDiagnosis(
                    step_num=step_num,
                    piece_idx=piece_idx,
                    part_id=part_id,
                    color_id=color_id,
                    is_exact_match=False,
                    pos_error_ldu=pos_err,
                    rot_error_deg=rot_err,
                    gt_translation_ldu=[round(v, 2) for v in gt_pos],
                    inferred_translation_ldu=[round(v, 2) for v in pred_pos] if pred_pos else None,
                    gt_was_in_identifier_candidates=gt_in_identifier,
                    gt_survived_guardian_filter=gt_in_guardian,
                    gt_visual_rank_in_placer=gt_rank_in_placer,
                    root_cause=FailureRootCause.UPSTREAM_CASCADE_ERROR.value,
                    diagnostic_explanation=explanation,
                    proposed_fix=proposed_fix,
                )

        # Diagnose root cause and synthesize a GENERALIZED Fix
        part_family = classify_part_family(part_id)
        fix_id = f"gen_fix_{part_family}_{set_num}_s{step_num}_p{piece_idx}"

        if gt_in_guardian and gt_rank_in_placer is not None and gt_rank_in_placer > 1:
            root_cause = FailureRootCause.PLACER_ROI_RANKING_ERROR.value
            explanation = (
                f"El Agente Identificador y el Guardián Físico conservaron la posición GT correcta "
                f"(rank #{gt_rank_in_placer} de {len(placer_ranked_candidates)}), pero el Agente Colocador Visual "
                f"eligió otra hipótesis con mayor score aparente en la ROI (error={pos_err} LDU). "
                f"Causa generalizada: Holgura ROI insuficiente para piezas de la familia `{part_family}` "
                f"o peso insuficiente del contexto de piezas vecinas."
            )
            old_fam_margin = float(learned_rules.get("family_roi_margin_overrides", {}).get(part_family, 0.40))
            new_fam_margin = round(min(0.65, old_fam_margin + 0.10), 2)
            proposed_fix = ProposedFix(
                fix_id=fix_id,
                target_agent="lego-placer-agent",
                root_cause=root_cause,
                part_id=part_id,
                step_num=step_num,
                description=(
                    f"[GENERALIZADO] Ampliar margen ROI para toda la familia `{part_family}` "
                    f"de {old_fam_margin} a {new_fam_margin} e incrementar peso de vecindad `w_neighbor_context` a 0.24."
                ),
                parameter_patch={
                    "family_roi_margin_overrides": {part_family: new_fam_margin},
                    "roi_margin_overrides": {part_id: new_fam_margin},
                    "scorer_weight_adjustments": {"w_neighbor_context": 0.24, "w_edge": 0.44},
                },
                applied_automatically=True,
            )
        elif gt_in_identifier and not gt_in_guardian:
            root_cause = FailureRootCause.GUARDIAN_FALSE_REJECTION.value
            explanation = (
                f"El Agente Identificador generó la pose GT exacta {gt_pos}, pero el Agente Guardián Físico "
                f"la descartó por tolerancia de penetración OBB demasiado estricta en `{part_id}`. "
                f"Causa generalizada: Las piezas de la familia `{part_family}` requieren mayor holgura geométrica."
            )
            old_fam_tol = float(learned_rules.get("family_clearance_overrides", {}).get(part_family, 0.5))
            new_fam_tol = round(min(2.5, old_fam_tol + 0.5), 2)
            proposed_fix = ProposedFix(
                fix_id=fix_id,
                target_agent="lego-guardian-agent",
                root_cause=root_cause,
                part_id=part_id,
                step_num=step_num,
                description=(
                    f"[GENERALIZADO] Elevar umbral de holgura de interferencia OBB para toda la familia `{part_family}` "
                    f"a {new_fam_tol} LDU."
                ),
                parameter_patch={
                    "family_clearance_overrides": {part_family: new_fam_tol},
                    "part_clearance_overrides": {part_id: new_fam_tol},
                },
                applied_automatically=True,
            )
        elif not gt_in_identifier and abs(gt_pos[1]) > 0 and rot_err > 45.0:
            root_cause = FailureRootCause.FLIP_OR_CALLOUT_DESYNC.value
            explanation = (
                f"La pose GT {gt_pos} presenta una rotación relativa de {rot_err}° no generada en el paso {step_num}. "
                f"Causa generalizada: La familia `{part_family}` requiere exploración en rotaciones completas SO(3) / lateral SNOT."
            )
            fams_3d = learned_rules.get("families_with_3d_rotations", [])
            new_fams = list(fams_3d)
            if part_family not in new_fams:
                new_fams.append(part_family)

            proposed_fix = ProposedFix(
                fix_id=fix_id,
                target_agent="lego-context-agent",
                root_cause=root_cause,
                part_id=part_id,
                step_num=step_num,
                description=(
                    f"[GENERALIZADO] Activar exploración 3D completa y lateral SNOT para toda la familia `{part_family}`."
                ),
                parameter_patch={
                    "families_with_3d_rotations": new_fams,
                    "force_lateral_snot_parts": [part_id],
                },
                applied_automatically=True,
            )
        else:
            root_cause = FailureRootCause.IDENTIFIER_RECALL_MISS.value
            explanation = (
                f"El Agente Identificador no incluyó la posición GT {gt_pos} entre sus {len(identifier_candidates)} "
                f"hipótesis (pos_err={pos_err} LDU). "
                f"Causa generalizada: El filtro espacial podó la posición válida de la familia `{part_family}`."
            )
            fams_3d = learned_rules.get("families_with_3d_rotations", [])
            new_fams = list(fams_3d)
            if part_family not in new_fams:
                new_fams.append(part_family)

            proposed_fix = ProposedFix(
                fix_id=fix_id,
                target_agent="lego-identifier-agent",
                root_cause=root_cause,
                part_id=part_id,
                step_num=step_num,
                description=(
                    f"[GENERALIZADO] Añadir `{part_family}` al grupo con rotaciones 3D extendidas y búsqueda abierta de conectores."
                ),
                parameter_patch={
                    "families_with_3d_rotations": new_fams,
                    "force_lateral_snot_parts": [part_id],
                },
                applied_automatically=True,
            )

            # Fase 2 — Deep LLM diagnosis when AUDITOR_LLM_ENABLED=true
            if os.getenv("AUDITOR_LLM_ENABLED", "false").lower() == "true":
                prior_failed_parts = (
                    [
                        f"{r.part_id} at step {r.step_num} (err={r.pos_error_ldu} LDU)"
                        for r in (prior_audit_results or [])
                        if not r.is_exact_match
                    ]
                )
                llm_context = {
                    "part_id": part_id,
                    "part_family": part_family,
                    "gt_position": [round(v, 2) for v in gt_pos],
                    "predicted_position": [round(v, 2) for v in pred_pos] if pred_pos else None,
                    "pos_error_ldu": round(pos_err, 3),
                    "rot_error_deg": round(rot_err, 2),
                    "step_num": step_num,
                    "identifier_candidates_count": len(identifier_candidates),
                    "gt_in_identifier": gt_in_identifier,
                    "gt_survived_guardian": gt_in_guardian,
                    "gt_rank_in_placer": gt_rank_in_placer,
                    "prior_failed_parts_in_step": prior_failed_parts,
                    "families_with_3d_rotations": learned_rules.get("families_with_3d_rotations", []),
                    "family_clearance": learned_rules.get("family_clearance_overrides", {}).get(part_family),
                    "family_roi_margin": learned_rules.get("family_roi_margin_overrides", {}).get(part_family),
                }
                llm_result = self._call_auditor_llm(llm_context)
                if llm_result:
                    if llm_result.get("recommendation"):
                        explanation = (
                            explanation + "\n[LLM] " + str(llm_result["recommendation"])
                        )
                        proposed_fix.description = (
                            proposed_fix.description + "\n[LLM] " + str(llm_result["recommendation"])
                        )
                    if llm_result.get("parameter_patch") and isinstance(llm_result["parameter_patch"], dict):
                        proposed_fix.parameter_patch.update(llm_result["parameter_patch"])

        # Apply fix into learned_rules dictionary in-memory
        self.apply_fix_to_rules(proposed_fix, learned_rules)

        return GTAuditDiagnosis(
            step_num=step_num,
            piece_idx=piece_idx,
            part_id=part_id,
            color_id=color_id,
            is_exact_match=False,
            pos_error_ldu=pos_err,
            rot_error_deg=rot_err,
            gt_translation_ldu=[round(v, 2) for v in gt_pos],
            inferred_translation_ldu=[round(v, 2) for v in pred_pos] if pred_pos else None,
            gt_was_in_identifier_candidates=gt_in_identifier,
            gt_survived_guardian_filter=gt_in_guardian,
            gt_visual_rank_in_placer=gt_rank_in_placer,
            root_cause=root_cause,
            diagnostic_explanation=explanation,
            proposed_fix=proposed_fix,
        )

    @staticmethod
    def apply_fix_to_rules(fix: ProposedFix, learned_rules: Dict[str, Any]) -> None:
        """
        Merges the parameter patch from a ProposedFix into the persistent learned_rules store.

        Guard against overfitting: a patch is only applied once the same
        (target_agent, root_cause, part family) has been observed MIN_FIX_EVIDENCE times.
        Earlier observations are only counted in `fix_evidence`.

        Fix 2.2 — Differentiated caps by family:
          - clearance  caps: TECHNIC/HINGE=3.5, BRACKET/SNOT=3.0, PLATES=2.0, default=2.5
          - roi_margin caps: TECHNIC/HINGE=0.80, BRACKET/SNOT=0.75, PLATES=0.65, default=0.65
        This prevents low-complexity families (standard plates, tiles) from being dragged up
        to the same saturated thresholds as complex SNOT/Technic families.
        """
        # Per-family caps for clearance (penetration threshold in LDU)
        MAX_CLEARANCE_BY_FAMILY: Dict[str, float] = {
            "TECHNIC_CONNECTORS": 3.5,
            "HINGE_AND_ARTICULATION": 3.5,
            "BRACKET_AND_SNOT": 3.0,
            "SLOPES_AND_CURVES": 2.5,
            "PLATES_WITH_CLIPS_BARS": 2.5,
            "GENERAL_PARTS": 2.5,
            "BRICKS_STANDARD": 2.0,
            "PLATES_STANDARD": 2.0,
            "TILES_SMOOTH": 1.5,
            "JUMPER_PLATES": 1.5,
        }
        # Per-family caps for ROI margin ratio
        MAX_ROI_MARGIN_BY_FAMILY: Dict[str, float] = {
            "TECHNIC_CONNECTORS": 0.80,
            "HINGE_AND_ARTICULATION": 0.80,
            "BRACKET_AND_SNOT": 0.75,
            "SLOPES_AND_CURVES": 0.70,
            "PLATES_WITH_CLIPS_BARS": 0.70,
            "GENERAL_PARTS": 0.65,
            "BRICKS_STANDARD": 0.65,
            "PLATES_STANDARD": 0.60,
            "TILES_SMOOTH": 0.55,
            "JUMPER_PLATES": 0.55,
        }

        key = f"{fix.target_agent}:{fix.root_cause}:{classify_part_family(fix.part_id)}"
        evidence = learned_rules.setdefault("fix_evidence", {})
        evidence[key] = int(evidence.get(key, 0)) + 1
        if evidence[key] < MIN_FIX_EVIDENCE:
            fix.applied_automatically = False
            return
        patch = fix.parameter_patch
        if "family_roi_margin_overrides" in patch:
            current = learned_rules.setdefault("family_roi_margin_overrides", {})
            for fam, val in patch["family_roi_margin_overrides"].items():
                cap = MAX_ROI_MARGIN_BY_FAMILY.get(fam, 0.65)
                current[fam] = min(cap, float(val))
        if "family_clearance_overrides" in patch:
            current = learned_rules.setdefault("family_clearance_overrides", {})
            for fam, val in patch["family_clearance_overrides"].items():
                cap = MAX_CLEARANCE_BY_FAMILY.get(fam, 2.5)
                current[fam] = min(cap, float(val))
        if "families_with_3d_rotations" in patch:
            f_list = learned_rules.setdefault("families_with_3d_rotations", [])
            for fam in patch["families_with_3d_rotations"]:
                if fam not in f_list:
                    f_list.append(fam)
        if "roi_margin_overrides" in patch:
            current = learned_rules.setdefault("roi_margin_overrides", {})
            part_fam = classify_part_family(fix.part_id)
            cap = MAX_ROI_MARGIN_BY_FAMILY.get(part_fam, 0.65)
            for pid, val in patch["roi_margin_overrides"].items():
                current[pid] = min(cap, float(val))
        if "part_clearance_overrides" in patch:
            current = learned_rules.setdefault("part_clearance_overrides", {})
            part_fam = classify_part_family(fix.part_id)
            cap = MAX_CLEARANCE_BY_FAMILY.get(part_fam, 2.5)
            for pid, val in patch["part_clearance_overrides"].items():
                current[pid] = min(cap, float(val))
        if "scorer_weight_adjustments" in patch:
            learned_rules.setdefault("scorer_weight_adjustments", {}).update(patch["scorer_weight_adjustments"])
        if "force_lateral_snot_parts" in patch:
            snot_list = learned_rules.setdefault("force_lateral_snot_parts", [])
            for pid in patch["force_lateral_snot_parts"]:
                if pid not in snot_list:
                    snot_list.append(pid)

        history = learned_rules.setdefault("fixes_history", [])
        if not any(h.get("fix_id") == fix.fix_id for h in history):
            history.append({
                "fix_id": fix.fix_id,
                "target_agent": fix.target_agent,
                "root_cause": fix.root_cause,
                "part_id": fix.part_id,
                "step_num": fix.step_num,
                "description": fix.description,
            })
