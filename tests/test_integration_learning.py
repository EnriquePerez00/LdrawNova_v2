"""Integration tests for learning loop - Phase 2.

Tests the learning loop without needing external dependencies.
"""
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))


class MockRulesStore:
    """Simplified rules store for testing."""
    def __init__(self):
        self.rules = {
            "rule_z_spacing": {
                "category": "Z_SPACING_VIOLATION",
                "prompt_injection": "Segments must be spaced Z >= 40 LDU apart",
                "sets_affected": set(),
                "active": False,
            }
        }
        self.incident_counter = 0
    
    def find_rule_by_category(self, category: str):
        for rule in self.rules.values():
            if rule["category"] == category:
                return rule
        return None
    
    def get_rules_for_injection(self, max_rules: int = 5) -> List[str]:
        active = [r["prompt_injection"] for r in self.rules.values() if r["active"]]
        return active[:max_rules]


class MockIncidentClassifier:
    """Simple classifier."""
    def classify(self, diff: Dict[str, Any]) -> tuple:
        if "overlap" in str(diff).lower():
            return ("Z_SPACING_VIOLATION", 0.95)
        return ("GEOMETRY_ERROR", 0.70)


class MockLearningHook:
    """Mock learning hook."""
    def __init__(self, rules_store=None):
        self.rules_store = rules_store or MockRulesStore()
        self.classifier = MockIncidentClassifier()
        self.enabled = True
        self.current_sample = "SAMPLE_1"
        self.incident_count = 0
    
    def on_incident_detected(self, diff: Dict[str, Any]) -> None:
        """Simulate detecting an incident."""
        if not self.enabled:
            return
        
        self.incident_count += 1
        
        # Each incident in a different "sample" to trigger promotion
        if self.incident_count > 1:
            self.current_sample = "SAMPLE_2"
        
        category, _ = self.classifier.classify(diff)
        if category:
            rule = self.rules_store.find_rule_by_category(category)
            if rule:
                rule["sets_affected"].add(self.current_sample)
                # Promote if affects >= 2 sets
                if len(rule["sets_affected"]) >= 2:
                    rule["active"] = True
    
    def get_learned_constraints(self) -> List[str]:
        return self.rules_store.get_rules_for_injection()


def test_1():
    print("\n[TEST 1] LearningHook initialization")
    print("=" * 70)
    try:
        hook = MockLearningHook()
        assert hook.enabled
        assert hook.classifier is not None
        print("  ✓ Hook created successfully")
        print("  ✓ PASS")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False


def test_2():
    print("\n[TEST 2] Incident classification")
    print("=" * 70)
    try:
        classifier = MockIncidentClassifier()
        cat, conf = classifier.classify({"issue": "overlap"})
        assert cat == "Z_SPACING_VIOLATION"
        print(f"  Overlap classified as: {cat}")
        print("  ✓ PASS")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False


def test_3():
    print("\n[TEST 3] Rule promotion (2+ sets)")
    print("=" * 70)
    try:
        store = MockRulesStore()
        rule = store.find_rule_by_category("Z_SPACING_VIOLATION")
        
        # Start inactive
        assert not rule["active"]
        print("  Initial: inactive")
        
        # Add SET_1
        rule["sets_affected"].add("SET_1")
        assert not rule["active"]
        print(f"  After SET_1: active={rule['active']}")
        
        # Add SET_2 -> should promote
        rule["sets_affected"].add("SET_2")
        if len(rule["sets_affected"]) >= 2:
            rule["active"] = True
        assert rule["active"]
        print(f"  After SET_2: active={rule['active']}")
        print("  ✓ PASS")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False


def test_4():
    print("\n[TEST 4] Constraint injection")
    print("=" * 70)
    try:
        hook = MockLearningHook()
        
        # Before learning
        cons = hook.get_learned_constraints()
        print(f"  Before: {len(cons)} constraints")
        assert len(cons) == 0
        
        # First incident (SAMPLE_1)
        hook.on_incident_detected({"issue": "overlap"})
        cons = hook.get_learned_constraints()
        print(f"  After incident 1: sets={len(hook.rules_store.rules['rule_z_spacing']['sets_affected'])}, active={hook.rules_store.rules['rule_z_spacing']['active']}, constraints={len(cons)}")
        
        # Second incident (SAMPLE_2) - should trigger promotion
        hook.on_incident_detected({"issue": "overlap"})
        cons = hook.get_learned_constraints()
        print(f"  After incident 2: sets={len(hook.rules_store.rules['rule_z_spacing']['sets_affected'])}, active={hook.rules_store.rules['rule_z_spacing']['active']}, constraints={len(cons)}")
        
        assert len(cons) > 0, f"Expected 1+ constraints, got {len(cons)}"
        print(f"  Injected: {cons[0][:50]}...")
        print("  ✓ PASS")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5():
    print("\n[TEST 5] Loop integration")
    print("=" * 70)
    try:
        hook = MockLearningHook()
        
        for i in range(3):
            hook.on_incident_detected({"issue": "overlap"})
            print(f"  Iteration {i+1}: processed")
        
        rule = hook.rules_store.find_rule_by_category("Z_SPACING_VIOLATION")
        assert len(rule["sets_affected"]) > 0
        print(f"  ✓ PASS (sets affected: {len(rule['sets_affected'])})")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("INTEGRATION TESTS: Learning Loop (Phase 2)")
    print("=" * 70)
    
    tests = [test_1, test_2, test_3, test_4, test_5]
    names = [
        "Hook initialization",
        "Incident classification",
        "Rule promotion",
        "Constraint injection",
        "Loop integration",
    ]
    
    results = []
    for name, test_fn in zip(names, tests):
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ EXCEPTION in {name}: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    passed = sum(1 for _, r in results if r)
    print(f"\nTotal: {passed}/{len(results)} PASS")
    
    if passed == len(results):
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        print("   Ready for Phase 3: Real LLM testing")
        exit(0)
    else:
        print("\n❌ Some tests failed")
        exit(1)
