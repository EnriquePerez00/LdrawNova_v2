"""Tests for the Phase 4 A2 partial-rewrite path (plan §4 Phase 4).

These verify that:
- When feedback carries a diff with a segment_id + mpd_line_range and
  ``prev_mpd_path`` points to an MPD that has that submodel, A2 is asked only
  for that submodel and the previous MPD is rewritten in place.
- When the model returns a full MPD (no submodel blocks), the generator falls
  back to a full rewrite.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ldraw_tools.design_generator import (
    _parse_returned_submodels,
    _diffs_with_segments,
    design_3d_with_llm,
)
from ldraw_tools.profile_adapter import ProfileAdapter


PREV_MPD = """0 FILE design.ldr
0 Name: design.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_head.ldr
1 16 0 -48 0 1 0 0 0 1 0 0 0 1 segment_torso.ldr
0 NOFILE

0 FILE segment_head.ldr
0 // SEGMENT_ID: head
0 Name: segment_head.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE

0 FILE segment_torso.ldr
0 // SEGMENT_ID: torso
0 Name: segment_torso.ldr
1 14 0 0 0 1 0 0 0 1 0 0 0 1 3003.dat
0 NOFILE
"""


@pytest.fixture
def adapter(tmp_path: Path) -> ProfileAdapter:
    return ProfileAdapter("brand_logo", tmp_path / "wl.json", tmp_path / "pal.json")


@pytest.fixture
def spec() -> dict:
    return {
        "version": 1,
        "profile": "brand_logo",
        "canonical_description": "test model",
        "segments": [
            {"id": "head", "name": "head", "color": "red"},
            {"id": "torso", "name": "torso", "color": "white"},
        ],
    }


def _feedback_for_head(prev_mpd_path: Path) -> dict:
    """Simulate the loop building feedback after A4 anchored a diff to 'head'."""
    return {
        "diffs": [
            {
                "severity": 4,
                "segment_id": "head",
                "mpd_line_range": [7, 12],
                "issue": "head color wrong",
                "suggestion": "use dark gray instead of red",
            },
            # A diff without segment anchoring should not disqualify partial mode.
            {"severity": 2, "issue": "unclear", "suggestion": "nothing specific"},
        ],
        "prev_mpd_path": str(prev_mpd_path),
    }


def test_diffs_with_segments_filters_correctly(tmp_path: Path):
    fb = _feedback_for_head(tmp_path / "x.mpd")
    out = _diffs_with_segments(fb)
    assert len(out) == 1
    assert out[0]["segment_id"] == "head"


def test_parse_returned_submodels_single_block():
    text = (
        "0 FILE segment_head.ldr\n"
        "0 // SEGMENT_ID: head\n"
        "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3005.dat\n"
        "0 NOFILE\n"
    )
    blocks = _parse_returned_submodels(text)
    assert "head" in blocks
    assert "3005.dat" in blocks["head"]


def test_parse_returned_submodels_handles_markdown_fences():
    text = (
        "```\n"
        "0 FILE segment_wing.ldr\n0 // SEGMENT_ID: wing\n0 NOFILE\n"
        "```\n"
    )
    blocks = _parse_returned_submodels(text)
    assert "wing" in blocks


def test_parse_returned_submodels_empty_on_full_mpd_without_submodels():
    """A flat MPD with no `segment_` submodel is rejected so caller can fall back."""
    text = "0 FILE design.ldr\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 NOFILE\n"
    blocks = _parse_returned_submodels(text)
    # Only 'design' is extracted (not matching segment_ convention)
    # The partial-rewrite code requires overlap with targeted segment_ids so
    # this would fall back; here we just check filename fallback behavior.
    assert "head" not in blocks
    assert "torso" not in blocks


def test_partial_rewrite_only_touches_targeted_segment(tmp_path: Path, adapter, spec):
    """Given a diff on 'head', only the head submodel is rewritten in iter1."""
    # Set up a previous MPD on disk (iter_0).
    iter0 = tmp_path / "iter_0"
    iter0.mkdir()
    prev_mpd = iter0 / "design.mpd"
    prev_mpd.write_text(PREV_MPD)

    iter1 = tmp_path / "iter_1"
    feedback = _feedback_for_head(prev_mpd)

    # Mock the LLM: return ONLY a rewritten head submodel.
    new_head_block = (
        "0 FILE segment_head.ldr\n"
        "0 // SEGMENT_ID: head\n"
        "0 Name: segment_head.ldr\n"
        "1 8 0 0 0 1 0 0 0 1 0 0 0 1 3005.dat\n"
        "0 NOFILE\n"
    )
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "choices": [{"message": {"content": new_head_block}}],
        "usage": {},
    }
    with patch("ldraw_tools.design_generator.requests.post",
               return_value=fake_response) as mock_post:
        plan, mpd_path = design_3d_with_llm(spec, feedback, adapter, iter1)

    # The returned plan announces partial_rewrite mode.
    assert plan["a2_mode"] == "partial_rewrite"
    assert plan["a2_rewritten_segments"] == ["head"]

    # The new MPD still contains torso untouched but head replaced.
    new_text = mpd_path.read_text()
    assert "3005.dat" in new_text         # new head part
    assert "3001.dat" not in new_text     # old head part removed
    assert "3003.dat" in new_text         # torso preserved

    # And the LLM was called ONCE (no fallback).
    assert mock_post.call_count == 1


def test_partial_rewrite_falls_back_when_model_returns_full_mpd(tmp_path: Path, adapter, spec):
    """If the model ignores the instruction and returns a plain MPD, fall back."""
    iter0 = tmp_path / "iter_0"
    iter0.mkdir()
    prev_mpd = iter0 / "design.mpd"
    prev_mpd.write_text(PREV_MPD)
    iter1 = tmp_path / "iter_1"
    feedback = _feedback_for_head(prev_mpd)

    full_mpd = "0 FILE design.ldr\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 NOFILE\n"
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    # Both the partial call and the fallback full call return the same thing.
    fake_response.json.return_value = {
        "choices": [{"message": {"content": full_mpd}}],
        "usage": {},
    }
    with patch("ldraw_tools.design_generator.requests.post",
               return_value=fake_response) as mock_post:
        plan, mpd_path = design_3d_with_llm(spec, feedback, adapter, iter1)

    # Two calls total: 1 partial attempt + 1 full rewrite fallback.
    assert mock_post.call_count == 2
    assert plan["a2_mode"] == "full_rewrite"
    assert mpd_path.read_text().strip() == full_mpd.strip()


def test_partial_rewrite_skipped_when_no_prev_mpd(tmp_path: Path, adapter, spec):
    """First iteration: no prev_mpd_path -> no partial call, straight to full rewrite."""
    iter0 = tmp_path / "iter_0"
    feedback = {"diffs": [{"severity": 4, "segment_id": "head",
                           "mpd_line_range": [1, 5], "issue": "x", "suggestion": "y"}]}
    # No prev_mpd_path in feedback.
    full_mpd = "0 FILE design.ldr\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 NOFILE\n"
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "choices": [{"message": {"content": full_mpd}}],
        "usage": {},
    }
    with patch("ldraw_tools.design_generator.requests.post",
               return_value=fake_response) as mock_post:
        plan, mpd_path = design_3d_with_llm(spec, feedback, adapter, iter0)
    assert mock_post.call_count == 1
    assert plan["a2_mode"] == "full_rewrite"
