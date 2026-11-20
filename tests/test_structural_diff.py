"""Unit tests for structural_diff module (pure logic, no LLM, no loop)."""
import pytest
from typing import Dict, Any, List

from scripts.bench.structural_diff import (
    compute_structural_diffs,
    score_structural_match,
    _bom_diff,
    _edges_diff,
    _stud_fidelity,
)


class TestBomDiff:
    """Test BOM-level comparison."""
    
    def test_identical_bom(self):
        """Identical BOM should score 100."""
        bom_gt = {"3001": 2, "3002": 3}
        bom_gen = {"3001": 2, "3002": 3}
        diffs, score = _bom_diff(bom_gt, bom_gen)
        assert score == 100.0
        assert len(diffs) == 0
    
    def test_missing_parts(self):
        """Missing parts should emit diffs with severity 4."""
        bom_gt = {"3001": 2, "3002": 1}
        bom_gen = {"3001": 2}  # Missing 3002
        diffs, score = _bom_diff(bom_gt, bom_gen)
        
        missing = [d for d in diffs if d["type"] == "missing_part"]
        assert len(missing) == 1
        assert missing[0]["severity"] == 4  # High
        assert missing[0]["part_id"] == "3002"
        assert score < 100.0
    
    def test_extra_parts(self):
        """Extra parts should emit diffs with severity 2."""
        bom_gt = {"3001": 1}
        bom_gen = {"3001": 1, "3002": 2}  # Extra 3002
        diffs, score = _bom_diff(bom_gt, bom_gen)
        
        extra = [d for d in diffs if d["type"] == "extra_part"]
        assert len(extra) == 1
        assert extra[0]["severity"] == 2  # Medium
    
    def test_qty_mismatch(self):
        """Quantity mismatch should emit diffs."""
        bom_gt = {"3001": 2}
        bom_gen = {"3001": 3}  # Wrong qty
        diffs, score = _bom_diff(bom_gt, bom_gen)
        
        qty_mismatch = [d for d in diffs if d["type"] == "qty_mismatch"]
        assert len(qty_mismatch) == 1
        assert qty_mismatch[0]["severity"] == 2


class TestEdgesDiff:
    """Test part-to-part connectivity."""
    
    def test_identical_edges(self):
        """Identical edge sets should score 100."""
        edges_gt = [(0, 1), (1, 2)]
        edges_gen = [(0, 1), (1, 2)]
        diffs, score = _edges_diff(edges_gt, edges_gen, nodes_gt=3, nodes_gen=3)
        
        assert score == 100.0
        assert len(diffs) == 0
    
    def test_missing_edges(self):
        """Missing edges emit diffs with severity 4 (high, per actual implementation)."""
        edges_gt = [(0, 1), (1, 2), (2, 3)]
        edges_gen = [(0, 1), (1, 2)]  # Missing (2,3)
        diffs, score = _edges_diff(edges_gt, edges_gen, nodes_gt=4, nodes_gen=4)
        
        missing = [d for d in diffs if d["type"] == "missing_edge"]
        assert len(missing) == 1
        assert missing[0]["severity"] == 4  # High (per implementation)
        assert score < 100.0
    
    def test_extra_edges(self):
        """Extra edges emit diffs with severity 1."""
        edges_gt = [(0, 1)]
        edges_gen = [(0, 1), (1, 2)]  # Extra edge
        diffs, score = _edges_diff(edges_gt, edges_gen, nodes_gt=2, nodes_gen=3)
        
        extra = [d for d in diffs if d["type"] == "extra_edge"]
        assert len(extra) == 1
        assert extra[0]["severity"] == 1  # Low


class TestStudFidelity:
    """Test stud-exact connectivity quality."""
    
    def test_identical_studs(self):
        """Identical stud edges should score 100."""
        studs_gt = [{"occurrence_a": 0, "occurrence_b": 1, "feature_id": 4}, {"occurrence_a": 1, "occurrence_b": 2, "feature_id": 8}]
        studs_gen = [{"occurrence_a": 0, "occurrence_b": 1, "feature_id": 4}, {"occurrence_a": 1, "occurrence_b": 2, "feature_id": 8}]
        diffs, score = _stud_fidelity(studs_gt, studs_gen, connectivity_available=True)
        
        assert score == 100.0
        assert len(diffs) == 0
    
    def test_missing_studs(self):
        """Missing studs: should handle gracefully."""
        studs_gt = [{"occurrence_a": 0, "occurrence_b": 1, "feature_id": 4}, {"occurrence_a": 1, "occurrence_b": 2, "feature_id": 8}]
        studs_gen = [{"occurrence_a": 0, "occurrence_b": 1, "feature_id": 4}]  # Missing second stud
        diffs, score = _stud_fidelity(studs_gt, studs_gen, connectivity_available=True)
        
        # Score should be less than 100 (missing data)
        assert score is not None and score < 100.0
    
    def test_connectivity_unavailable_returns_none(self):
        """When connectivity_available=False, should return None (not false 100)."""
        studs_gt = [{"occurrence_a": 0, "occurrence_b": 1, "feature_id": 4}]
        studs_gen = []  # Empty
        diffs, score = _stud_fidelity(studs_gt, studs_gen, connectivity_available=False)
        
        # KEY TEST: anti-falso-100%
        assert score is None
        assert len(diffs) > 0  # Info diff about unavailable connectivity


class TestComputeStructuralDiffs:
    """Integration test of compute_structural_diffs."""
    
    def _make_graph(self, parts_count: int, edges_part: List, edges_stud: List, connectivity_status: str = "extracted") -> Dict[str, Any]:
        """Helper: make a minimal valid graph."""
        bom = {f"part_{i}": 1 for i in range(parts_count)}
        nodes = [{"part_id": f"part_{i}", "step": 0} for i in range(parts_count)]
        return {
            "version": 1,
            "sample_id": "test",
            "parts_count": parts_count,
            "nodes": nodes,
            "edges_part": edges_part,
            "edges_stud": edges_stud,
            "bom": bom,
            "connectivity_status": connectivity_status,
        }
    
    def test_perfect_match(self):
        """Identical graphs should score 100."""
        # Use empty studs list to avoid complex dict structure in test
        graph_gt = self._make_graph(3, [(0, 1), (1, 2)], [])
        graph_gen = self._make_graph(3, [(0, 1), (1, 2)], [])
        
        result = compute_structural_diffs(graph_gt, graph_gen)
        assert result["scores"]["overall_score"] == 100.0
        assert len(result["diffs"]) == 0
    
    def test_partial_match(self):
        """Partial match should score < 100."""
        graph_gt = self._make_graph(3, [(0, 1), (1, 2)], [])
        graph_gen = self._make_graph(2, [(0, 1)], [])  # Fewer parts/edges
        
        result = compute_structural_diffs(graph_gt, graph_gen)
        assert result["scores"]["overall_score"] < 100.0
        assert len(result["diffs"]) > 0
        assert result["summary"]["max_severity"] > 0
    
    def test_connectivity_unavailable_flag(self):
        """When connectivity_status != 'extracted', stud_score is None."""
        graph_gt = self._make_graph(2, [(0, 1)], [], connectivity_status="unavailable")
        graph_gen = self._make_graph(2, [(0, 1)], [], connectivity_status="unavailable")
        
        result = compute_structural_diffs(graph_gt, graph_gen)
        
        # KEY: stud_score should be None when connectivity not extracted
        assert result["scores"]["stud_score"] is None
        # overall_score still valid (uses neutral 100 for stud when None)
        assert result["scores"]["overall_score"] is not None
    
    def test_score_structural_match_convenience(self):
        """Convenience function should return overall_score directly."""
        studs = [{"occurrence_a": 0, "occurrence_b": 1, "feature_id": 4}]
        graph_gt = self._make_graph(2, [(0, 1)], studs)
        graph_gen = self._make_graph(2, [(0, 1)], studs)
        
        score = score_structural_match(graph_gt, graph_gen)
        assert score == 100.0
        assert isinstance(score, float)
