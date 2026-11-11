"""Tests for FASES 8.5 + 9: Design generation, validators, rendering, persistence."""
import json
import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch, MagicMock


class TestValidators:
    """Test validator classes."""
    
    def test_bom_validator_extract(self, tmp_path):
        """Test BOM extraction from MPD."""
        from ldraw_tools.validators import BOMValidator
        
        mpd_content = """0 FILE test.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
1 16 0 10 0 1 0 0 0 1 0 0 0 1 3001.dat
1 16 0 20 0 1 0 0 0 1 0 0 0 1 3002.dat
0 NOFILE
"""
        mpd_file = tmp_path / "test.mpd"
        mpd_file.write_text(mpd_content)
        
        validator = BOMValidator()
        bom = validator.extract_bom(mpd_file)
        
        assert bom["3001.dat"] == 2
        assert bom["3002.dat"] == 1
        print(f"✓ BOM extracted: {bom}")
    
    def test_bom_validator_constraints(self):
        """Test BOM constraint validation."""
        from ldraw_tools.validators import BOMValidator
        
        validator = BOMValidator()
        bom = {"3001.dat": 50, "3002.dat": 30}
        constraints = {"min_parts": 10, "max_parts": 100}
        
        is_valid, errors = validator.validate_bom_constraints(bom, constraints)
        assert is_valid
        assert len(errors) == 0
        print("✓ BOM constraints valid")
    
    def test_color_validator_delta_e(self):
        """Test ΔE color distance calculation."""
        from ldraw_tools.validators import ColorValidator
        
        validator = ColorValidator()
        
        # Same color
        de = validator.delta_e_cie76((255, 0, 0), (255, 0, 0))
        assert de == 0
        
        # Very different color
        de = validator.delta_e_cie76((255, 0, 0), (0, 0, 0))
        assert de > 50
        
        print(f"✓ ΔE calculation works: same=0, max≈{de:.1f}")
    
    def test_color_validator_find_closest(self):
        """Test finding closest LEGO color."""
        from ldraw_tools.validators import ColorValidator
        
        validator = ColorValidator()
        
        # Pure red should match "red"
        closest, de = validator.find_closest_lego_color((255, 0, 0))
        print(f"✓ Red RGB(255,0,0) → {closest} (ΔE={de:.1f})")


class TestDesignGenerator:
    """Test design generation with Claude Haiku-5."""
    
    @patch('ldraw_tools.design_generator.requests.post')
    def test_design_3d_with_llm(self, mock_post, tmp_path):
        """Test A2 design generation with LLM."""
        from ldraw_tools.design_generator import design_3d_with_llm
        
        # Mock LLM response
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": """0 FILE design.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE"""}}]
        }
        mock_post.return_value = mock_response
        
        profile_adapter = Mock()
        profile_adapter.profile_name = "test_profile"
        
        spec = {"version": 1, "profile": "test_profile", "segments": [{"name": "base"}]}
        
        plan, mpd_path = design_3d_with_llm(
            spec=spec,
            feedback=None,
            profile_adapter=profile_adapter,
            output_dir=tmp_path,
            llm_config={"base_url": "http://localhost:6655/litellm", "secret": "test"}
        )
        
        assert mpd_path.exists()
        assert plan["profile"] == "test_profile"
        print(f"✓ A2 design generation: {mpd_path.name}")


class TestRenderer:
    """Test rendering pipeline."""
    
    def test_renderer_initialization(self):
        """Test renderer initialization."""
        from ldraw_tools.renderer import LeoCADRenderer
        
        renderer = LeoCADRenderer(leocad_path="leocad")
        # May not be available, but should initialize
        assert renderer.leocad_path == "leocad"
        print("✓ Renderer initialized")
    
    def test_color_extractor_init(self):
        """Test color extractor."""
        from ldraw_tools.renderer import ColorExtractor
        
        extractor = ColorExtractor()
        # Simple placeholder test
        assert extractor is not None
        print("✓ ColorExtractor initialized")
    
    def test_overlap_detector_init(self):
        """Test overlap detector."""
        from ldraw_tools.renderer import OverlapDetector
        
        detector = OverlapDetector()
        assert detector is not None
        print("✓ OverlapDetector initialized")


class TestLoopStateManager:
    """Test loop state persistence."""
    
    def test_state_initialization(self, tmp_path):
        """Test state initialization."""
        from ldraw_tools.loop_state_manager import LoopStateManager
        
        mgr = LoopStateManager(tmp_path)
        state = mgr.initialize_state(profile="test", slug="test_slug", max_iterations=3)
        
        assert state["profile"] == "test"
        assert state["slug"] == "test_slug"
        assert state["converged"] == False
        assert mgr.state_file.exists()
        print(f"✓ State initialized: {mgr.state_file}")
    
    def test_state_persistence(self, tmp_path):
        """Test saving and loading state."""
        from ldraw_tools.loop_state_manager import LoopStateManager
        
        mgr = LoopStateManager(tmp_path)
        initial_state = mgr.initialize_state(profile="test", slug="test")
        
        mgr.update_iteration(
            iteration_number=0,
            global_score=75.5,
            per_axis_scores={"color": 80, "geometry": 70},
            num_diffs=5,
            max_severity=2,
            top_diffs=[]
        )
        
        # Load and verify
        loaded = mgr.load_state()
        assert loaded["best_score"] == 75.5
        assert len(loaded["iterations"]) == 1
        print(f"✓ State persisted and reloaded")


class TestImprovementLoopV2:
    """Test integrated improvement loop."""
    
    @patch('ldraw_tools.improvement_loop_v2.LeoCADRenderer')
    @patch('ldraw_tools.improvement_loop_v2.GeometryValidator')
    def test_loop_initialization(self, mock_geom_val, mock_renderer, tmp_path):
        """Test loop initialization."""
        from ldraw_tools.improvement_loop_v2 import ImprovementLoopV2
        
        profile_adapter = Mock()
        profile_adapter.profile_name = "test_profile"
        profile_adapter.get_whitelist.return_value = {"categories": {}}
        profile_adapter.get_bom_constraints.return_value = {"min_parts": 1, "max_parts": 500}
        
        spec = {"version": 1, "profile": "test", "segments": []}
        
        loop = ImprovementLoopV2(
            spec=spec,
            adapter=profile_adapter,
            output_dir=tmp_path,
            max_iter=2,
            threshold=85.0,
        )
        
        assert loop.max_iter == 2
        assert loop.threshold == 85.0
        assert (tmp_path / "loop_state.json").exists()
        print("✓ ImprovementLoopV2 initialized")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
