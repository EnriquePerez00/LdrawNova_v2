"""Build ground-truth assembly graph from .io corpus."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime

from scripts.bench.io_loader_extended import count_steps_and_parts_extended, read_model_ldr_extended

logger = logging.getLogger(__name__)

__all__ = ["build_assembly_graph_gt", "write_assembly_graph_gt"]


def _parse_mpd_parts(ldr_text: str) -> Tuple[List[Dict[str, Any]], Dict[int, int]]:
    """Extract type-1 lines (parts) from LDraw text."""
    parts = []
    color_freq: Dict[int, int] = {}
    step_idx = 0
    
    for line in ldr_text.splitlines():
        s = line.strip()
        if not s or s.startswith("0"):
            if s.upper().startswith("0 STEP"):
                step_idx += 1
            continue
        
        tok = s.split()
        if len(tok) < 15 or tok[0] != "1":
            continue
        
        try:
            color = int(tok[1])
            x, y, z = float(tok[2]), float(tok[3]), float(tok[4])
            part_name = " ".join(tok[14:]).strip()
            
            parts.append({
                "part_id": part_name,
                "color": color,
                "x": x,
                "y": y,
                "z": z,
                "step_idx": step_idx,
            })
            
            color_freq[color] = color_freq.get(color, 0) + 1
        except (ValueError, IndexError):
            continue
    
    return parts, color_freq


def _extract_connectivity(io_path: Path) -> Dict[str, Any]:
    """Extract connectivity from .io using ldraw_tools."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    try:
        from ldraw_tools.document import parse_source
        from ldraw_tools.connectivity import inspect_connections
        from ldraw_tools.connection_adapter import connection_contacts
        from ldraw_tools.common import get_parts
    except ImportError as e:
        logger.warning(f"[connectivity] Import failed: {e}")
        return {
            "edges_part": [],
            "edges_stud": [],
            "occurrences": [],
            "note": "connectivity module unavailable",
        }
    
    try:
        text = read_model_ldr_extended(io_path)
        model = parse_source(text)
        parts = get_parts(model)
        
        inspection = inspect_connections(model, parts)
        contacts = connection_contacts(inspection)
        
        edges_part: Set[Tuple[int, int]] = set()
        edges_stud: List[Dict[str, Any]] = []
        
        for contact in contacts:
            a_idx = contact.first_occurrence.index
            b_idx = contact.second_occurrence.index
            edges_part.add(tuple(sorted((a_idx, b_idx))))
            
            edges_stud.append({
                "occurrence_a": a_idx,
                "occurrence_b": b_idx,
                "feature_a": str(contact.first.feature_id),
                "feature_b": str(contact.second.feature_id),
                "status": str(contact.status),
            })
        
        return {
            "edges_part": sorted(list(edges_part)),
            "edges_stud": edges_stud,
            "note": "extracted",
        }
    except Exception as e:
        logger.warning(f"[connectivity] extraction failed: {e}")
        return {
            "edges_part": [],
            "edges_stud": [],
            "note": f"extraction failed: {e}",
        }


def build_assembly_graph_gt(io_path: Path, sample_id: str) -> Dict[str, Any]:
    """Build ground-truth assembly graph."""
    logger.info(f"[GraphGT] Building {sample_id} from {io_path.name}")
    
    text = read_model_ldr_extended(io_path)
    parts_list, color_freq = _parse_mpd_parts(text)
    
    step_parts = count_steps_and_parts_extended(io_path)
    step_count, _ = (step_parts if step_parts else (1, len(parts_list)))
    
    connectivity = _extract_connectivity(io_path)
    
    bom: Dict[str, int] = {}
    for part in parts_list:
        pid = part["part_id"]
        bom[pid] = bom.get(pid, 0) + 1
    
    nodes = []
    for idx, part in enumerate(parts_list):
        nodes.append({
            "idx": idx,
            "part_id": part["part_id"],
            "color": part["color"],
            "pos": [part["x"], part["y"], part["z"]],
            "step_idx": part["step_idx"],
        })
    
    graph = {
        "version": 1,
        "sample_id": sample_id,
        "parts_count": len(parts_list),
        "step_count": step_count,
        "nodes": nodes,
        "edges_part": connectivity["edges_part"],
        "edges_stud": connectivity["edges_stud"],
        "bom": bom,
        "connectivity_status": connectivity.get("note", "unknown"),
        "timestamp": datetime.now().isoformat(),
    }
    
    logger.info(f"[GraphGT] Complete: {len(nodes)} nodes, {len(graph['edges_part'])} edges, {len(bom)} parts")
    return graph


def write_assembly_graph_gt(
    io_path: Path,
    sample_id: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """Write assembly_graph_GT.json."""
    if output_dir is None:
        output_dir = Path.cwd()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = build_assembly_graph_gt(io_path, sample_id)
    
    output_path = output_dir / f"{sample_id}_assembly_graph_GT.json"
    with open(output_path, "w") as f:
        json.dump(graph, f, indent=2)
    
    logger.info(f"[GraphGT] Written: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.bench.assembly_graph_gt <io_path> <sample_id> [output_dir]")
        sys.exit(1)
    
    io_file = Path(sys.argv[1])
    sample = sys.argv[2]
    out_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.cwd()
    
    result_path = write_assembly_graph_gt(io_file, sample, out_dir)
    print(f"✅ Graph: {result_path}")
