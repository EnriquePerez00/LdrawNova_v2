"""Integration tests: Loop blending with structural diffs (no LLM required)."""
import pytest
import json
from pathlib import Path
from unittest.mock import patch

from ldraw_tools.improvement_loop_v2 import ImprovementLoopV2
from ldraw_tools.profile_adapter import ProfileAdapter


class MockAgentRoles:
    """Mock agent orchestrator matching ImprovementLoopV2.run() expectations."""
    
    def __init__(self, iter_scores=None):
        self.iter_scores = iter_scores or [70, 80, 85, 90]
        self.iter_count = 0
        self.hook_calls = []  # Track if hook was called
    
    def design_3d(self, spec, feedback=None, adapter=None, output_dir=None, llm_config=None):
        """Mock A2 design agent."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        mpd_path = output_dir / "design.mpd"
        mpd_path.write_text("0 FILE design.ldr\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 NOFILE\n")
        plan_path = output_dir / "design.plan.json"
        plan_path.write_text(json.dumps({"version": 1, "sections": []}))
        return {"version": 1}, mpd_path
    
    def describe_render_blind(self, renders_dir, adapter, llm_config=None, output_slug=None):
        """Mock A3 describe agent."""
        return {"version": 1, "profile": adapter.profile_name, "segments": [{"id": "s1"}]}
    
    def judge_differ(self, spec_gt, render_spec, renders_dir, adapter, iteration_number, llm_config=None, output_slug=None):
        """Mock A4 judge agent."""
        a4_score = self.iter_scores[min(self.iter_count, len(self.iter_scores) - 1)]
        self.iter_count += 1
        
        return {
            "version": 1,
            "global_score": a4_score,
            "per_axis_scores": {"structure": a4_score},
            "diffs": [{"severity": "high"}],
        }, {"judge": "gemini-2.5-flash"}


class TestLoopBaseNoRegression:
    """Verify ImprovementLoopV2 base class has no regressions."""
    
    def test_base_loop_with_hook_no_regression(self, tmp_path):
        """Base loop should work unchanged with hook present."""
        spec = {"version": 1, "profile": "brand_logo", "segments": []}
        adapter = ProfileAdapter("brand_logo", Path("dummy_wl.json"), Path("dummy_pal.json"))
        output_dir = tmp_path / "loop_test"
        
        agents = MockAgentRoles(iter_scores=[70.0, 90.0])
        
        with patch("ldraw_tools.renderer.LeoCADRenderer.render_views", return_value={"home": Path("fake.png")}):
            loop = ImprovementLoopV2(
                spec=spec,
                adapter=adapter,
                output_dir=output_dir,
                max_iter=4,
                threshold=85.0
            )
            result = loop.run(agents)
            
            # Verify loop completed
            assert result is not None
            assert "converged" in result
            assert result["converged"] is True
            assert "reason" in result
            
            # Base loop should NOT have structural_diff key
            assert "structural_diff" not in result
            
            # Verify agents were called
            assert agents.iter_count > 0
    
    def test_hook_called_during_loop(self, tmp_path):
        """Verify _post_judge_hook is invoked during loop."""
        spec = {"version": 1, "profile": "brand_logo", "segments": []}
        adapter = ProfileAdapter("brand_logo", Path("dummy_wl.json"), Path("dummy_pal.json"))
        output_dir = tmp_path / "loop_test_hook"
        
        agents = MockAgentRoles(iter_scores=[85.0])
        
        with patch("ldraw_tools.renderer.LeoCADRenderer.render_views", return_value={"home": Path("fake.png")}):
            loop = ImprovementLoopV2(
                spec=spec,
                adapter=adapter,
                output_dir=output_dir,
                max_iter=2,
                threshold=85.0
            )
            
            # Track hook calls
            hook_calls = []
            original_hook = loop._post_judge_hook
            
            def tracked_hook(report, mpd_path, iteration):
                hook_calls.append({"iteration": iteration, "score": report.get("global_score")})
                return original_hook(report, mpd_path, iteration)
            
            loop._post_judge_hook = tracked_hook
            
            # Run loop
            result = loop.run(agents)
            
            # Verify hook was called
            assert len(hook_calls) > 0, "Hook should be called at least once during loop"
            assert all(isinstance(call["iteration"], int) for call in hook_calls)
            assert all(isinstance(call["score"], (int, float)) for call in hook_calls)


class TestLoopWithStructuralIntegration:
    """Test ImprovementLoopV2WithStructural integration."""
    
    @pytest.mark.skipif(
        not Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io/OMR-7610-1_normalized.io").exists(),
        reason="Test corpus OMR-7610-1 not found"
    )
    def test_structural_loop_initializes_correctly(self, tmp_path):
        """Verify ImprovementLoopV2WithStructural initializes with correct config."""
        from ldraw_tools.improvement_loop_v2_with_structural import ImprovementLoopV2WithStructural
        
        io_path = Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io/OMR-7610-1_normalized.io")
        sample_id = "OMR-7610-1"
        
        spec = {"version": 1, "profile": "brand_logo", "segments": []}
        adapter = ProfileAdapter("brand_logo", Path("dummy_wl.json"), Path("dummy_pal.json"))
        output_dir = tmp_path / "structural_loop_test"
        
        # Create structural loop
        loop = ImprovementLoopV2WithStructural(
            spec=spec,
            adapter=adapter,
            output_dir=output_dir,
            max_iter=2,
            io_path=io_path,
            sample_id=sample_id,
            enable_structural_diff=True,
        )
        
        # Verify initialization
        assert loop.enable_structural_diff is True
        assert loop.io_path == io_path
        assert loop.sample_id == sample_id
        assert loop.tier in ["MICRO", "SMALL", "MEDIUM"]
        assert loop.weight_structural > 0
        assert loop.weight_structural <= 1.0
    
    @pytest.mark.skipif(
        not Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io/OMR-7610-1_normalized.io").exists(),
        reason="Test corpus OMR-7610-1 not found"
    )
    def test_structural_loop_with_hook_override(self, tmp_path):
        """Verify _post_judge_hook is overridden in structural loop."""
        from ldraw_tools.improvement_loop_v2_with_structural import ImprovementLoopV2WithStructural
        
        io_path = Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io/OMR-7610-1_normalized.io")
        
        spec = {"version": 1, "profile": "brand_logo", "segments": []}
        adapter = ProfileAdapter("brand_logo", Path("dummy_wl.json"), Path("dummy_pal.json"))
        output_dir = tmp_path / "structural_loop_hook_test"
        
        loop = ImprovementLoopV2WithStructural(
            spec=spec,
            adapter=adapter,
            output_dir=output_dir,
            max_iter=2,
            io_path=io_path,
            sample_id="OMR-7610-1",
            enable_structural_diff=True,
        )
        
        # Verify that the subclass has overridden _post_judge_hook
        from ldraw_tools.improvement_loop_v2 import ImprovementLoopV2
        base_hook = ImprovementLoopV2._post_judge_hook
        structural_hook = ImprovementLoopV2WithStructural._post_judge_hook
        
        # Check that they are different methods (override occurred)
        assert structural_hook != base_hook, "Subclass should override _post_judge_hook"
    
    @pytest.mark.skipif(
        not Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io/OMR-7610-1_normalized.io").exists(),
        reason="Test corpus OMR-7610-1 not found"
    )
    def test_structural_loop_run_with_hook_integration(self, tmp_path):
        """Verify structural loop runs with hook integration (may use mock A4)."""
        from ldraw_tools.improvement_loop_v2_with_structural import ImprovementLoopV2WithStructural
        
        io_path = Path("/Users/I764690/Code_personal/LegoGPT/data/normalized_io/OMR-7610-1_normalized.io")
        
        spec = {"version": 1, "profile": "brand_logo", "segments": []}
        adapter = ProfileAdapter("brand_logo", Path("dummy_wl.json"), Path("dummy_pal.json"))
        output_dir = tmp_path / "structural_loop_run_test"
        
        agents = MockAgentRoles(iter_scores=[70.0, 85.0])
        
        with patch("ldraw_tools.renderer.LeoCADRenderer.render_views", return_value={"home": Path("fake.png")}):
            loop = ImprovementLoopV2WithStructural(
                spec=spec,
                adapter=adapter,
                output_dir=output_dir,
                max_iter=2,
                io_path=io_path,
                sample_id="OMR-7610-1",
                enable_structural_diff=True,
            )
            
            result = loop.run(agents)
            
            # Verify loop completed
            assert result is not None
            assert "converged" in result
            
            # Verify structural_diff metadata is present
            assert "structural_diff" in result
            assert result["structural_diff"]["enabled"] is True
            assert result["structural_diff"]["tier"] == loop.tier
            assert "io_path" in result["structural_diff"]
