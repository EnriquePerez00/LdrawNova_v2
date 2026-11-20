"""Phase 1 regression tests for the untruncations in A2 and A4 prompts.

These assert that:
- A2 includes every spec segment in its prompt (no [:5] truncation).
- A2 default max_tokens is 4096.
- A4 includes the full spec JSON (no [:500] truncation).
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ldraw_tools import agent_roles
from ldraw_tools.design_generator import (
    A2_MAX_TOKENS,
    _build_prompt,
    _count_submodels,
    _segment_id,
    design_3d_with_llm,
)
from ldraw_tools.profile_adapter import ProfileAdapter


@pytest.fixture
def adapter(tmp_path):
    return ProfileAdapter("brand_logo", tmp_path / "wl.json", tmp_path / "pal.json")


def _spec(n_segments: int, extra_text: str = "") -> dict:
    return {
        "version": 1,
        "profile": "brand_logo",
        "canonical_description": extra_text or "test model",
        "segments": [
            {
                "id": f"seg_{i}",
                "name": f"segment_{i}",
                "type": "brick",
                "color": "red",
                "estimated_size_studs": [2, 2, 1],
                "description": f"part number {i} of {n_segments}" + extra_text,
            }
            for i in range(n_segments)
        ],
    }


def test_a2_prompt_contains_all_segments(adapter):
    """Given a spec with 10 segments, A2 prompt lists all 10 (no [:5])."""
    spec = _spec(10)
    prompt, count = _build_prompt(spec, None, adapter)
    assert count == 10
    for i in range(10):
        assert f"seg_{i}" in prompt, f"segment seg_{i} missing from A2 prompt"


def test_a2_prompt_declares_submodels_per_segment(adapter):
    """A2 prompt must require one submodel per segment id (plan §4 Phase 2)."""
    spec = _spec(3)
    prompt, _ = _build_prompt(spec, None, adapter)
    # The required-ids list and the example header must mention the ids.
    for i in range(3):
        assert f"segment_seg_{i}.ldr" in prompt or f"seg_{i}" in prompt


def test_a2_max_tokens_default_is_4096():
    """Plan §4 Phase 1: default A2_MAX_TOKENS is 4096."""
    assert A2_MAX_TOKENS >= 4096


def test_a2_calls_llm_with_configured_max_tokens(adapter, tmp_path):
    """The actual HTTP payload must carry A2_MAX_TOKENS, not the legacy 1000."""
    spec = _spec(3)
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "0 FILE design.ldr\n0 NOFILE\n"}}],
        "usage": {"completion_tokens": 42},
    }
    with patch("ldraw_tools.design_generator.requests.post",
               return_value=fake_response) as mock_post:
        plan, mpd_path = design_3d_with_llm(spec, None, adapter, tmp_path / "out")
    assert mock_post.called
    payload = mock_post.call_args.kwargs["json"]
    assert payload["max_tokens"] == A2_MAX_TOKENS
    assert plan["max_tokens"] == A2_MAX_TOKENS
    assert plan["spec_segments"] == 3
    assert plan["expected_segment_ids"] == ["seg_0", "seg_1", "seg_2"]
    assert mpd_path.exists()


def test_a2_submodel_coverage_metric(adapter, tmp_path):
    """Plan §4 Phase 2: submodel_coverage is recorded in plan.json."""
    spec = _spec(2)
    mpd_text = (
        "0 FILE design.ldr\n"
        "1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_seg_0.ldr\n"
        "0 NOFILE\n\n"
        "0 FILE segment_seg_0.ldr\n"
        "0 // SEGMENT_ID: seg_0\n"
        "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
        "0 NOFILE\n"
    )
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "choices": [{"message": {"content": mpd_text}}],
        "usage": {},
    }
    with patch("ldraw_tools.design_generator.requests.post",
               return_value=fake_response):
        plan, _ = design_3d_with_llm(spec, None, adapter, tmp_path / "out")
    # Only 1 of 2 segments covered -> 0.5.
    assert plan["submodel_coverage"] == 0.5


def test_a4_prompt_contains_full_spec_no_500_truncation(adapter):
    """Plan §4 Phase 1: A4 must receive the full spec_gt JSON (no [:500])."""
    # Large spec that would be cut at 500 chars.
    spec_gt = _spec(10, extra_text=" with a lot of extra text " * 5)
    full_text = json.dumps(spec_gt, indent=2)
    assert len(full_text) > 2048, "sanity: spec_gt should be >2KB"

    captured = {}

    def fake_vlm_chat(model, prompt, image_paths, llm_config, timeout, agent, output_dir_slug):
        captured["prompt"] = prompt
        return '{"version": 1, "global_score": 50, "diffs": []}'

    with patch.object(agent_roles, "vlm_chat", side_effect=fake_vlm_chat):
        agent_roles.judge_differ(
            spec_gt=spec_gt,
            render_spec={"segments": []},
            renders_dir=Path("/tmp/does_not_matter"),
            profile_adapter=adapter,
            iteration_number=0,
        )

    prompt = captured["prompt"]
    # Every segment id from spec_gt must appear verbatim in the prompt.
    for seg in spec_gt["segments"]:
        assert seg["id"] in prompt, f"A4 prompt missing segment id {seg['id']}"
    # And the legacy '...' truncation marker must no longer follow the spec.
    assert full_text in prompt or full_text.replace("\n", "\n") in prompt, (
        "A4 prompt should contain the full spec_gt JSON"
    )


def test_segment_id_is_sanitized():
    """The helper used for submodel filenames must not leak dangerous characters."""
    assert _segment_id({"id": "head/left"}, 0) == "head_left"
    assert _segment_id({"name": "wing 1"}, 0) == "wing_1"
    assert _segment_id({}, 3) == "segment_3"


def test_count_submodels_counts_segment_id_comment():
    ids = ["a", "b", "c"]
    text = (
        "0 FILE segment_a.ldr\n0 // SEGMENT_ID: a\n0 NOFILE\n"
        "0 FILE other.ldr\n0 // SEGMENT_ID: b\n0 NOFILE\n"
    )
    matched, coverage = _count_submodels(text, ids)
    assert matched == 2
    assert round(coverage, 3) == round(2 / 3, 3)
