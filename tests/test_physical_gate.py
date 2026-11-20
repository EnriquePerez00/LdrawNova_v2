"""Tests for the deterministic pre-render physical gate (plan §4 Phase 3).

These tests require the LDraw library at ``LDRAW_DIR``. Skipped when absent.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

LDRAW_DIR = os.environ.get("LDRAW_DIR") or os.environ.get("LDRAWDIR") or str(Path.home() / "LDraw")
if not (Path(LDRAW_DIR) / "parts").is_dir():
    pytest.skip(f"LDraw library missing at {LDRAW_DIR}", allow_module_level=True)
os.environ.setdefault("LDRAW_DIR", LDRAW_DIR)

from ldraw_tools.physical_gate import (
    PRE_RENDER_GATE_SCORE,
    PhysicalGateResult,
    run_physical_gate,
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


def test_valid_model_passes_gate(tmp_path: Path):
    """A well-formed MPD with two touching bricks passes the gate."""
    mpd = _write(tmp_path, "ok.mpd", """0 FILE design.ldr
0 Name: design.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_a.ldr
1 16 0 -24 0 1 0 0 0 1 0 0 0 1 segment_b.ldr
0 NOFILE

0 FILE segment_a.ldr
0 // SEGMENT_ID: a
0 Name: segment_a.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 3003.dat
0 NOFILE

0 FILE segment_b.ldr
0 // SEGMENT_ID: b
0 Name: segment_b.ldr
1 14 0 0 0 1 0 0 0 1 0 0 0 1 3003.dat
0 NOFILE
""")
    result = run_physical_gate(mpd)
    assert isinstance(result, PhysicalGateResult)
    assert result.ok, f"expected gate to pass; penetrations={result.penetrations}, islands={result.floating_islands}"
    assert result.synthetic_diffs == []


def test_collision_is_detected_as_critical_diff(tmp_path: Path):
    """Two bricks at the same position penetrate; gate.ok is False with one diff."""
    mpd = _write(tmp_path, "collide.mpd", """0 FILE design.ldr
0 Name: design.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_a.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_b.ldr
0 NOFILE

0 FILE segment_a.ldr
0 // SEGMENT_ID: a
0 Name: segment_a.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE

0 FILE segment_b.ldr
0 // SEGMENT_ID: b
0 Name: segment_b.ldr
1 14 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE
""")
    result = run_physical_gate(mpd)
    assert not result.ok
    assert len(result.penetrations) == 1
    pen = result.penetrations[0]
    assert pen["depth_ldu"] and pen["depth_ldu"] > 0
    assert set((pen["segment_a"], pen["segment_b"])) == {"a", "b"}

    # One synthetic diff, severity=5 after normalization.
    assert len(result.synthetic_diffs) == 1
    diff = result.synthetic_diffs[0]
    assert diff["type"] == "collision"
    assert diff["severity"] == 5
    assert diff["segment_id"] in {"a", "b"}
    assert diff["mpd_line_range"] is not None
    assert "source" in diff and diff["source"] == "physical_gate"


def test_floating_island_is_detected(tmp_path: Path):
    """An island far above the base plate with no contact is flagged."""
    # Two separate bricks: base at Y=0 (so max.y = 0), island positioned so
    # its max.y is far above (i.e. in LDraw world, it is raised off the plate).
    # Brick 3001 is 24 LDU tall (y span: -4..24). Placing it at y=-200 raises
    # it 200 LDU above the base brick.
    mpd = _write(tmp_path, "float.mpd", """0 FILE design.ldr
0 Name: design.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment_base.ldr
1 16 0 -200 0 1 0 0 0 1 0 0 0 1 segment_island.ldr
0 NOFILE

0 FILE segment_base.ldr
0 // SEGMENT_ID: base
0 Name: segment_base.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE

0 FILE segment_island.ldr
0 // SEGMENT_ID: island
0 Name: segment_island.ldr
1 14 500 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE
""")
    result = run_physical_gate(mpd)
    assert not result.ok, f"expected island failure; penetrations={result.penetrations}"
    assert len(result.floating_islands) == 1
    island = result.floating_islands[0]
    assert "island" in island["segment_ids"]
    assert island["distance_to_base_ldu"] > 100  # well above tolerance


def test_parse_error_becomes_synthetic_diff(tmp_path: Path):
    """An invalid MPD produces a gate_failed=True with a parse_error diff."""
    mpd = _write(tmp_path, "bad.mpd", "this is not LDraw at all")
    result = run_physical_gate(mpd)
    assert not result.ok
    assert result.parse_error is not None
    assert len(result.synthetic_diffs) >= 1
    assert result.synthetic_diffs[0]["type"] == "parse_error"
    assert result.synthetic_diffs[0]["severity"] == 5


def test_gate_score_constant_below_revert_margin():
    """PRE_RENDER_GATE_SCORE must be low enough to trigger revert vs a decent best."""
    from ldraw_tools.loop_policy import REVERT_MARGIN
    # The plan requires a gate failure to drop below best - margin so the
    # orchestrator reverts. 10.0 vs any best >= 15.0 satisfies this.
    assert PRE_RENDER_GATE_SCORE + REVERT_MARGIN <= 50.0
