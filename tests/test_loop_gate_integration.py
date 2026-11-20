"""Integration test: ImprovementLoopV2 short-circuits on physical gate failure.

The plan requires that when the gate fails, A3 and A4 are not invoked and
the iteration is scored with PRE_RENDER_GATE_SCORE. This test uses a MockAgent
that counts invocations, and an A2 mock that writes a deliberately-colliding
MPD into iter_dir / "design.mpd".
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

LDRAW_DIR = os.environ.get("LDRAW_DIR") or str(Path.home() / "LDraw")
if not (Path(LDRAW_DIR) / "parts").is_dir():
    pytest.skip(f"LDraw library missing at {LDRAW_DIR}", allow_module_level=True)
os.environ.setdefault("LDRAW_DIR", LDRAW_DIR)

from ldraw_tools.improvement_loop_v2 import ImprovementLoopV2
from ldraw_tools.physical_gate import PRE_RENDER_GATE_SCORE
from ldraw_tools.profile_adapter import ProfileAdapter


COLLIDING_MPD = """0 FILE design.ldr
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
"""


class GateSpyAgentRoles:
    def __init__(self):
        self.a3_calls = 0
        self.a4_calls = 0

    def design_3d(self, spec, feedback, adapter, output_dir, llm_config=None):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        mpd_path = output_dir / "design.mpd"
        mpd_path.write_text(COLLIDING_MPD)
        plan_path = output_dir / "design.plan.json"
        plan_path.write_text(json.dumps({"version": 1, "sections": []}))
        return {"version": 1}, mpd_path

    def describe_render_blind(self, renders_dir, adapter, llm_config=None, output_slug=None):
        self.a3_calls += 1
        return {"version": 1, "segments": []}

    def judge_differ(self, spec_gt, render_spec, renders_dir, adapter,
                     iteration_number, llm_config=None, output_slug=None):
        self.a4_calls += 1
        return {"version": 1, "global_score": 90.0, "per_axis_scores": {},
                "diffs": []}, {"judge": "gemini-2.5-flash"}


def test_loop_short_circuits_on_colliding_mpd(tmp_path):
    spec = {"version": 1, "profile": "brand_logo", "segments": [
        {"id": "a"}, {"id": "b"},
    ]}
    adapter = ProfileAdapter("brand_logo", tmp_path / "wl.json", tmp_path / "pal.json")
    out = tmp_path / "loop_gate"
    spy = GateSpyAgentRoles()

    # Patch the renderer so even if the gate check is misconfigured we don't
    # accidentally require LeoCAD. The test asserts the renderer is not called
    # on gate failure by checking A3/A4 counters instead.
    with patch("ldraw_tools.improvement_loop_v2.LeoCADRenderer.render_views",
               return_value={}):
        loop = ImprovementLoopV2(spec=spec, adapter=adapter, output_dir=out,
                                 max_iter=1, threshold=85.0)
        res = loop.run(spy)

    # 1 iteration executed, gate failed, A3/A4 never ran.
    assert len(loop.iterations) == 1
    assert spy.a3_calls == 0, "A3 should be skipped when gate fails"
    assert spy.a4_calls == 0, "A4 should be skipped when gate fails"

    iter0 = json.loads((out / "iter_0" / "results.json").read_text())
    assert iter0["gate_failed"] is True
    assert iter0["score"] == PRE_RENDER_GATE_SCORE
    assert iter0["gate"]["penetration_count"] >= 1
    assert iter0["diffs"], "synthetic diffs must be persisted"
    assert iter0["diffs"][0]["type"] == "collision"
    assert iter0["diffs"][0]["severity"] == 5
