"""Tests for improvement loop — CORE orchestration."""
import json
import pytest
from pathlib import Path
from ldraw_tools.improvement_loop import ImprovementLoop, IterationResult
from ldraw_tools.profile_adapter import ProfileAdapter


class TestImprovementLoop:
    """Test improvement loop orchestration."""

    def test_loop_initialization(self, tmp_path):
        """Test loop initializes correctly."""
        spec = {"version": 1, "profile": "brand_logo", "brand_name": "Test"}
        adapter = ProfileAdapter("brand_logo", Path("dummy1"), Path("dummy2"))
        
        loop = ImprovementLoop(spec, adapter, str(tmp_path))
        
        assert loop.best_iteration is None
        assert len(loop.iterations) == 0
        assert loop.best_mpd_path is None

    def test_convergence_by_score_threshold(self):
        """Test convergence when score >= threshold."""
        converged, reason = ImprovementLoop._check_convergence(
            None,  # self
            global_score=90.0,
            max_severity=3,
            iteration_number=0,
        )
        
        assert converged
        assert reason == "score_threshold_met"

    def test_convergence_by_severity(self):
        """Test convergence when no critical diffs."""
        converged, reason = ImprovementLoop._check_convergence(
            None,
            global_score=50.0,
            max_severity=3,  # < 4 (severity_stop_threshold)
            iteration_number=0,
        )
        
        assert converged
        assert reason == "no_high_severity_diffs"

    def test_convergence_by_max_iterations(self):
        """Test convergence when max iterations reached."""
        converged, reason = ImprovementLoop._check_convergence(
            None,
            global_score=50.0,
            max_severity=5,
            iteration_number=3,  # >= max_iterations - 1 (default max=4)
        )
        
        assert converged
        assert reason == "max_iterations_reached"

    def test_non_convergence(self):
        """Test non-convergence when none of the conditions met."""
        converged, reason = ImprovementLoop._check_convergence(
            None,
            global_score=50.0,
            max_severity=5,
            iteration_number=0,
        )
        
        assert not converged
        assert reason == "not_converged"


class TestProfileAdapter:
    """Test ProfileAdapter base class."""

    def test_adapter_initialization(self):
        """Test ProfileAdapter initialization."""
        adapter = ProfileAdapter("test_profile", Path("dummy1"), Path("dummy2"))
        
        assert adapter.profile_name == "test_profile"
        assert adapter.scoring_weights["color_fidelity"] == 0.30

    def test_get_scoring_weights(self):
        """Test scoring weights retrieval."""
        adapter = ProfileAdapter("test", Path("dummy1"), Path("dummy2"))
        weights = adapter.get_scoring_weights()
        
        assert sum(weights.values()) == pytest.approx(1.0)
        assert "color_fidelity" in weights

    def test_evaluation_rubric(self):
        """Test evaluation rubric retrieval."""
        adapter = ProfileAdapter("test", Path("dummy1"), Path("dummy2"))
        rubric = adapter.get_evaluation_rubric()
        
        assert isinstance(rubric, str)
        assert len(rubric) > 0


class TestIterationResult:
    """Test IterationResult dataclass."""

    def test_iteration_result_creation(self):
        """Test IterationResult can be created."""
        result = IterationResult(
            iteration_number=0,
            global_score=75.0,
            per_axis_scores={"color": 80, "geometry": 70},
            num_diffs=2,
            max_severity=2,
            converged=False,
            stop_reason="not_converged",
            top_diffs=[],
            timestamp="2026-11-11T00:00:00",
        )
        
        assert result.iteration_number == 0
        assert result.global_score == 75.0
        assert not result.converged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
