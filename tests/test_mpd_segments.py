"""Tests for ldraw_tools.mpd_segments (plan §4 Phase 2)."""
from pathlib import Path

import pytest

from ldraw_tools.mpd_segments import (
    find_segment_for_line,
    parse_segment_blocks,
    rewrite_segment,
)


SAMPLE_MPD = """0 FILE design.ldr
0 Name: design.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_head.ldr
1 16 0 -48 0 1 0 0 0 1 0 0 0 1 segment_torso.ldr
0 NOFILE

0 FILE segment_head.ldr
0 // SEGMENT_ID: head
0 // SEGMENT_SOURCE: spec.segments[0]
0 Name: segment_head.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE

0 FILE segment_torso.ldr
0 // SEGMENT_ID: torso
0 // SEGMENT_SOURCE: spec.segments[1]
0 Name: segment_torso.ldr
1 14 0 0 0 1 0 0 0 1 0 0 0 1 3003.dat
1 14 20 0 0 1 0 0 0 1 0 0 0 1 3003.dat
0 NOFILE
"""


@pytest.fixture
def mpd_path(tmp_path: Path) -> Path:
    p = tmp_path / "sample.mpd"
    p.write_text(SAMPLE_MPD)
    return p


def test_parse_segment_blocks_returns_two_segments(mpd_path: Path):
    blocks = parse_segment_blocks(mpd_path)
    assert set(blocks.keys()) == {"head", "torso"}
    head_start, head_end, head_text = blocks["head"]
    assert head_start == 7, f"expected head to start at line 7, got {head_start}"
    assert head_end == 12, f"expected head to end at line 12, got {head_end}"
    assert "3001.dat" in head_text
    torso_start, torso_end, torso_text = blocks["torso"]
    assert torso_start == 14
    assert torso_end == 20
    assert "3003.dat" in torso_text


def test_parse_segment_blocks_filename_fallback(tmp_path: Path):
    """Segment id falls back to the filename when SEGMENT_ID comment is missing."""
    content = (
        "0 FILE design.ldr\n0 Name: design.ldr\n0 NOFILE\n"
        "0 FILE segment_wing.ldr\n0 Name: segment_wing.ldr\n"
        "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 NOFILE\n"
    )
    p = tmp_path / "flat.mpd"
    p.write_text(content)
    blocks = parse_segment_blocks(p)
    assert "wing" in blocks


def test_parse_segment_blocks_empty_file(tmp_path: Path):
    p = tmp_path / "empty.mpd"
    p.write_text("")
    assert parse_segment_blocks(p) == {}


def test_find_segment_for_line(mpd_path: Path):
    blocks = parse_segment_blocks(mpd_path)
    assert find_segment_for_line(blocks, 8) == "head"
    assert find_segment_for_line(blocks, 16) == "torso"
    # Line 1 is inside the main design.ldr block, which has no segment id.
    assert find_segment_for_line(blocks, 1) is None


def test_rewrite_segment_replaces_body_only(mpd_path: Path):
    new_body = (
        "0 FILE segment_head.ldr\n"
        "0 // SEGMENT_ID: head\n"
        "0 Name: segment_head.ldr\n"
        "1 4 0 24 0 1 0 0 0 1 0 0 0 1 3005.dat\n"
        "0 NOFILE\n"
    )
    rewrite_segment(mpd_path, "head", new_body)
    text = mpd_path.read_text()
    # Head got replaced.
    assert "3005.dat" in text
    assert "3001.dat" not in text
    # Torso remains intact.
    assert text.count("3003.dat") == 2
    # Parse again -> still two segments.
    blocks = parse_segment_blocks(mpd_path)
    assert set(blocks.keys()) == {"head", "torso"}


def test_rewrite_segment_unknown_id_raises(mpd_path: Path):
    with pytest.raises(KeyError):
        rewrite_segment(mpd_path, "does_not_exist", "0 FILE x.ldr\n0 NOFILE\n")


def test_rewrite_segment_refuses_empty(mpd_path: Path):
    with pytest.raises(ValueError):
        rewrite_segment(mpd_path, "head", "   \n\n")
