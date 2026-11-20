"""End-to-end integration tests for ImprovementLoopV2 with mocked agents."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ldraw_tools.improvement_loop_v2 import ImprovementLoopV2
from ldraw_tools.profile_adapter import ProfileAdapter
from ldraw_tools.model_router import ModelRouter


class MockAgentRoles:
    def __init__(self, scores, diffs_list, judge_status="gemini-2.5-flash"):
        self.scores = scores
        self.diffs_list = diffs_list
        self.judge_status = judge_status
        self.call_count = 0
        self.recorded_models = []

    def design_3d(self, spec, feedback, adapter, output_dir, llm_config=None):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        mpd_path = output_dir / "design.mpd"
        mpd_path.write_text("0 FILE design.ldr\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 NOFILE\n")
        plan_path = output_dir / "design.plan.json"
        plan_path.write_text(json.dumps({"version": 1, "sections": []}))
        if llm_config and "models" in llm_config:
            self.recorded_models.append(llm_config["models"].get("A2"))
        return {"version": 1}, mpd_path

    def describe_render_blind(self, renders_dir, adapter, llm_config=None, output_slug=None):
        return {"version": 1, "profile": adapter.profile_name, "segments": [{"id": "s1"}]}

    def judge_differ(self, spec_gt, render_spec, renders_dir, adapter, iteration_number, llm_config=None, output_slug=None):
        idx = min(self.call_count, len(self.scores) - 1)
        score = self.scores[idx]
        diffs = self.diffs_list[idx]
        self.call_count += 1
        judge = "error" if self.judge_status == "error" else ((llm_config or {}).get("models", {}).get("A4", "gemini-2.5-flash"))
        return {
            "version": 1,
            "global_score": score,
            "per_axis_scores": {"structure": score},
            "diffs": diffs,
        }, {"judge": judge}


@pytest.fixture
def base_setup(tmp_path):
    spec = {"version": 1, "profile": "brand_logo", "segments": []}
    adapter = ProfileAdapter("brand_logo", Path("dummy_wl.json"), Path("dummy_pal.json"))
    out_dir = tmp_path / "loop_test"
    return spec, adapter, out_dir


def test_convergence_by_score(base_setup):
    spec, adapter, out_dir = base_setup
    mock_roles = MockAgentRoles(scores=[70.0, 90.0], diffs_list=[[{"severity": "high"}], [{"severity": "low"}]])
    
    with patch("ldraw_tools.renderer.LeoCADRenderer.render_views", return_value={"home": Path("fake.png")}):
        loop = ImprovementLoopV2(spec=spec, adapter=adapter, output_dir=out_dir, max_iter=4, threshold=85.0)
        res = loop.run(mock_roles)
        
        assert res["converged"] is True
        assert res["reason"] == "score_threshold_met"
        assert len(loop.iterations) == 2
        assert (out_dir / "best" / "design.mpd").exists()


def test_convergence_by_string_severity(base_setup):
    spec, adapter, out_dir = base_setup
    mock_roles = MockAgentRoles(scores=[75.0], diffs_list=[[{"severity": "low"}, {"severity": "medium"}]])
    
    with patch("ldraw_tools.renderer.LeoCADRenderer.render_views", return_value={"home": Path("fake.png")}):
        loop = ImprovementLoopV2(spec=spec, adapter=adapter, output_dir=out_dir, max_iter=4, threshold=85.0)
        res = loop.run(mock_roles)
        
        assert res["converged"] is True
        assert res["reason"] == "no_high_severity_diffs"
        assert len(loop.iterations) == 1


def test_anti_regression_revert(base_setup):
    spec, adapter, out_dir = base_setup
    mock_roles = MockAgentRoles(
        scores=[80.0, 65.0, 82.0],
        diffs_list=[[{"severity": "high"}], [{"severity": "high"}], [{"severity": "low"}]]
    )
    
    with patch("ldraw_tools.renderer.LeoCADRenderer.render_views", return_value={"home": Path("fake.png")}):
        loop = ImprovementLoopV2(spec=spec, adapter=adapter, output_dir=out_dir, max_iter=4, threshold=85.0)
        res = loop.run(mock_roles)
        
        # Iteration 1 (score 65) is a revert from iteration 0 (score 80)
        iter1_res = json.loads((out_dir / "iter_1" / "results.json").read_text())
        assert iter1_res.get("reverted") is True
        assert loop.best.score == 82.0


def test_a4_failure_does_not_falsely_converge(base_setup):
    spec, adapter, out_dir = base_setup
    mock_roles = MockAgentRoles(scores=[50.0], diffs_list=[[]], judge_status="error")
    
    with patch("ldraw_tools.renderer.LeoCADRenderer.render_views", return_value={"home": Path("fake.png")}):
        loop = ImprovementLoopV2(spec=spec, adapter=adapter, output_dir=out_dir, max_iter=2, threshold=85.0)
        res = loop.run(mock_roles)
        
        # Should not falsely converge under 'no_high_severity_diffs' when A4 errored
        assert res["converged"] is True
        assert res["reason"] == "max_iterations_reached"
        assert len(loop.iterations) == 2


def test_a4_escalation_on_stagnation(base_setup):
    spec, adapter, out_dir = base_setup
    mock_roles = MockAgentRoles(
        scores=[50.0, 50.0, 50.0],
        diffs_list=[[{"severity": "high"}], [{"severity": "high"}], [{"severity": "high"}]]
    )
    
    with patch("ldraw_tools.renderer.LeoCADRenderer.render_views", return_value={"home": Path("fake.png")}):
        loop = ImprovementLoopV2(spec=spec, adapter=adapter, output_dir=out_dir, max_iter=3, threshold=85.0)
        res = loop.run(mock_roles)
        
        # On iter 2 (after 2 stagnant scores of 50.0), A4 should escalate to gemini-2.5-pro
        iter2_res = json.loads((out_dir / "iter_2" / "results.json").read_text())
        assert iter2_res["models"]["A4"] == "gemini-2.5-pro"
