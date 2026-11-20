"""Tests: loop policy + agent report drift check."""
import subprocess
import sys
from pathlib import Path

from ldraw_tools.loop_policy import (
    check_convergence, max_severity, normalize_diffs, normalize_severity, should_revert,
)

ROOT = Path(__file__).resolve().parent.parent


def test_severity_strings_and_numbers():
    assert normalize_severity("high") == 4
    assert normalize_severity("LOW") == 1
    assert normalize_severity(3) == 3
    assert normalize_severity("garbage") == 0
    assert normalize_severity(None) == 0


def test_mixed_severity_does_not_raise():
    diffs = normalize_diffs([{"severity": "high"}, {"severity": 2}, {}])
    assert max_severity(diffs) == 4


def test_convergence_rules():
    assert check_convergence(90, 5, 0, 4) == (True, "score_threshold_met")
    assert check_convergence(50, 2, 0, 4) == (True, "no_high_severity_diffs")
    assert check_convergence(50, 5, 3, 4) == (True, "max_iterations_reached")
    assert check_convergence(50, 5, 0, 4) == (False, "")


def test_unjudged_never_converges_by_severity():
    assert check_convergence(50, 0, 0, 4, judged=False) == (False, "")


def test_revert():
    assert should_revert(60, 80)
    assert not should_revert(78, 80)
    assert not should_revert(10, None)


def test_agent_report_generates_without_drift(tmp_path):
    out = tmp_path / "arch.md"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_agent_report.py"),
                        "--out", str(out), "--check"], capture_output=True, text=True)
    assert out.exists()
    assert r.returncode == 0, r.stdout + r.stderr
