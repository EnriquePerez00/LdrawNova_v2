"""Tests for shape matcher and model router."""
import json
import pytest
from pathlib import Path
from ldraw_tools.shape_matcher import ShapeMatcher
from ldraw_tools.model_router import ModelRouter


class TestShapeMatcher:
    """Test shape matching volume → parts."""

    def test_matcher_initialization(self, tmp_path):
        """Test ShapeMatcher initializes."""
        whitelist = {"categories": {}}
        whitelist_file = tmp_path / "whitelist.json"
        whitelist_file.write_text(json.dumps(whitelist))
        
        matcher = ShapeMatcher(whitelist_file)
        assert matcher.parts_index == []

    def test_match_flat_tile(self, tmp_path):
        """Test matching flat tile volumes."""
        whitelist = {
            "categories": {
                "tiles_flat": [
                    {"id": "3024.dat", "name": "Tile 1x1", "dims": [1, 1]},
                    {"id": "3023.dat", "name": "Tile 1x2", "dims": [1, 2]},
                ]
            }
        }
        whitelist_file = tmp_path / "whitelist.json"
        whitelist_file.write_text(json.dumps(whitelist))
        
        matcher = ShapeMatcher(whitelist_file)
        candidates = matcher.match({"primitive": "flat_tile"})
        
        assert len(candidates) > 0
        assert all(c[1] >= 50 for c in candidates)  # fit_score >= 50

    def test_match_curved_arc(self, tmp_path):
        """Test matching curved arc (macaroni) volumes."""
        whitelist = {"categories": {}}
        whitelist_file = tmp_path / "whitelist.json"
        whitelist_file.write_text(json.dumps(whitelist))
        
        matcher = ShapeMatcher(whitelist_file)
        candidates = matcher.match({
            "primitive": "curved_arc",
            "curvature_radius_studs": 2,
        })
        
        assert len(candidates) >= 3
        # First result should be best match for R=2
        assert "27925" in candidates[0][0]  # Macaroni 2x2

    def test_match_sorted_by_score(self, tmp_path):
        """Test matches are sorted by fit_score descending."""
        whitelist = {"categories": {}}
        whitelist_file = tmp_path / "whitelist.json"
        whitelist_file.write_text(json.dumps(whitelist))
        
        matcher = ShapeMatcher(whitelist_file)
        candidates = matcher.match({"primitive": "curved_arc"})
        
        # Scores should be descending
        scores = [c[1] for c in candidates]
        assert scores == sorted(scores, reverse=True)


class TestModelRouter:
    """Test model routing logic."""

    def test_router_initialization(self):
        """Test ModelRouter initializes."""
        router = ModelRouter()
        assert router.escalation_enabled

    def test_get_model_a1(self):
        """Test A1 uses Gemini 2.5 Flash (VLM for GT analysis)."""
        router = ModelRouter()
        model = router.get_model_for_agent("A1")
        
        assert "gemini" in model.lower()
        assert "2.5-flash" in model
        print(f"✓ A1 model: {model}")

    def test_get_model_a3_is_vlm(self):
        """Test A3 uses Gemini 2.5 Flash (VLM for render blind description)."""
        router = ModelRouter()
        model = router.get_model_for_agent("A3")
        
        assert "gemini" in model.lower()
        print(f"✓ A3 model: {model}")
    
    def test_get_model_a2_is_code(self):
        """Test A2 uses Claude Haiku (code generation, not VLM)."""
        router = ModelRouter()
        model = router.get_model_for_agent("A2")
        
        assert "claude" in model.lower()
        assert "haiku" in model.lower()
        print(f"✓ A2 model: {model}")

    def test_a4_no_escalation_with_improvement(self):
        """Test A4 doesn't escalate with score improvement."""
        router = ModelRouter()
        scores = [80.0, 85.0, 90.0]
        model = router.get_model_for_agent("A4", "job1", scores)
        
        # Scores improving, no escalation - should stay on gemini-2.5-flash
        assert "2.5-flash" in model

    def test_a4_escalation_on_stagnation(self):
        """Test A4 escalates to gemini-2.5-pro on stagnation."""
        router = ModelRouter()
        scores = [85.0, 85.0, 80.0, 80.0]
        model = router.get_model_for_agent("A4", "job1", scores)
        
        # Stagnant: last 2 scores not improving
        # Should escalate from gemini-2.5-flash to gemini-2.5-pro
        assert "gemini" in model.lower()
        assert "pro" in model
        print(f"✓ A4 escalation: {model}")

    def test_reset_job(self):
        """Test job reset clears stagnation tracking."""
        router = ModelRouter()
        router.stagnation_iterations["job1"] = 2
        
        router.reset_job("job1")
        
        assert "job1" not in router.stagnation_iterations



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
