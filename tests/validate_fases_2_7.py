#!/usr/bin/env python3
"""Validation script for FASES 2-7."""
import sys
from pathlib import Path
import json
import tempfile

root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from ldraw_tools.improvement_loop import ImprovementLoop, IterationResult
from ldraw_tools.profile_adapter import ProfileAdapter
from ldraw_tools.shape_matcher import ShapeMatcher
from ldraw_tools.model_router import ModelRouter

def test_1():
    """Test ImprovementLoop initialization."""
    print("\n[TEST 1] ImprovementLoop")
    spec = {"version": 1, "profile": "brand_logo"}
    with tempfile.TemporaryDirectory() as tmp:
        adapter = ProfileAdapter("brand_logo", Path("dummy"), Path("dummy"))
        loop = ImprovementLoop(spec, adapter, tmp)
        assert loop.best is None
        assert len(loop.iterations) == 0
        print("✓ ImprovementLoop initializes correctly")

def test_2():
    """Test ProfileAdapter."""
    print("\n[TEST 2] ProfileAdapter")
    adapter = ProfileAdapter("test", Path("dummy1"), Path("dummy2"))
    assert adapter.profile_name == "test"
    weights = adapter.get_scoring_weights()
    assert sum(weights.values()) == 1.0
    print(f"✓ ProfileAdapter: {weights}")

def test_3():
    """Test ShapeMatcher."""
    print("\n[TEST 3] ShapeMatcher")
    with tempfile.TemporaryDirectory() as tmp:
        wl = {"categories": {"tiles_flat": [{"id": "3024.dat", "dims": [1, 1]}]}}
        wf = Path(tmp) / "whitelist.json"
        wf.write_text(json.dumps(wl))
        matcher = ShapeMatcher(wf)
        candidates = matcher.match({"primitive": "flat_tile"})
        assert len(candidates) > 0
        print(f"✓ ShapeMatcher: {len(candidates)} candidates")

def test_4():
    """Test ModelRouter."""
    print("\n[TEST 4] ModelRouter")
    router = ModelRouter()
    a1 = router.get_model_for_agent("A1")
    a3 = router.get_model_for_agent("A3")
    assert "sonnet" in a1.lower()
    assert "haiku" in a3.lower()
    print(f"✓ A1: {a1}, A3: {a3}")

def main():
    print("="*70)
    print("FASES 2-7 Validation")
    print("="*70)
    try:
        test_1()
        test_2()
        test_3()
        test_4()
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        return 0
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
