"""Unit tests for assembly_graph_gt: GT extraction with connectivity (gate test)."""
import os
import pytest
from pathlib import Path

# Skip entire module if LDRAW_DIR not set (connectivity extraction requires it)
pytestmark = pytest.mark.skipif(
    not os.getenv("LDRAW_DIR"),
    reason="LDRAW_DIR not set; connectivity extraction unavailable"
)


class TestAssemblyGraphGt:
    """Test ground-truth assembly graph extraction with connectivity."""
    
    @pytest.mark.skipif(
        not Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io/OMR-7610-1_normalized.io").exists(),
        reason="Test corpus OMR-7610-1 not found"
    )
    def test_gate_omr_7610_1(self):
        """Gate test: OMR-7610-1 should extract 17 edges, 38 studs, connectivity extracted.
        
        This is the reproducible gate test from Etapa 1.
        """
        from scripts.bench.assembly_graph_gt import build_assembly_graph_gt
        
        io_path = Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io/OMR-7610-1_normalized.io")
        
        graph = build_assembly_graph_gt(io_path, "OMR-7610-1")
        
        # Assertions from gate test
        assert graph.get("connectivity_status") == "extracted", \
            f"Expected connectivity_status='extracted', got {graph.get('connectivity_status')}"
        
        edges_part = graph.get("edges_part", [])
        assert len(edges_part) == 17, \
            f"Expected 17 part-to-part edges, got {len(edges_part)}"
        
        edges_stud = graph.get("edges_stud", [])
        assert len(edges_stud) == 38, \
            f"Expected 38 stud-exact edges, got {len(edges_stud)}"
        
        # Additional sanity checks
        assert graph.get("parts_count") == 18, \
            f"Expected 18 parts, got {graph.get('parts_count')}"
        assert len(graph.get("nodes", [])) == 18, \
            f"Expected 18 nodes, got {len(graph.get('nodes', []))}"
