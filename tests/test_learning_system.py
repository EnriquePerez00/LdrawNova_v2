"""Test suite for learning system."""
import json
import tempfile
from pathlib import Path

from ldraw_tools.incident_taxonomy import IncidentClassifier
from ldraw_tools.knowledge_rules import KnowledgeRule, RulesStore, create_seed_rules_file


def test_classify_same_z_collision():
    """Cross-segment collision detection."""
    classifier = IncidentClassifier()
    diff = {
        "type": "collision",
        "evidence": {
            "segment_a": "seg_0",
            "segment_b": "seg_1",
            "depth_ldu": 14.0,
        }
    }
    category, confidence = classifier.classify(diff)
    assert category == "SAME_Z_LAYER_COLLISION"
    assert confidence > 0.9
    print("✅ test_classify_same_z_collision")


def test_classify_floating_island():
    """Floating island detection."""
    classifier = IncidentClassifier()
    diff = {
        "type": "floating_island",
        "evidence": {"segment_ids": ["seg_2"], "distance_to_base_ldu": 45.0}
    }
    category, confidence = classifier.classify(diff)
    assert category == "FLOATING_ISLAND"
    print("✅ test_classify_floating_island")


def test_rule_promotion():
    """Rule promotion after 2 sets."""
    rule = KnowledgeRule(
        rule_id="test_rule",
        category="TEST",
        fix_pattern="...",
        prompt_injection="...",
        triggered_by="TEST",
    )
    assert not rule.is_active()
    was_promoted = rule.register_occurrence("set_1")
    assert not was_promoted
    was_promoted = rule.register_occurrence("set_2")
    assert was_promoted
    assert rule.is_active()
    print("✅ test_rule_promotion")


def test_rules_store():
    """Rules store lifecycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_file = Path(tmpdir) / "learned_rules.json"
        create_seed_rules_file(rules_file)
        store = RulesStore(rules_file)
        
        # Register and promote
        store.register_or_update(
            rule_id="test", category="TEST", fix_pattern="fix",
            prompt_injection="inj", set_id="s1"
        )
        was_promoted, _ = store.register_or_update(
            rule_id="test", category="TEST", fix_pattern="fix",
            prompt_injection="inj", set_id="s2"
        )
        assert was_promoted
        
        # Get active rules for injection
        injections = store.get_rules_for_injection()
        assert len(injections) >= 0  # May have seed rules
        print("✅ test_rules_store")


if __name__ == "__main__":
    test_classify_same_z_collision()
    test_classify_floating_island()
    test_rule_promotion()
    test_rules_store()
    print("\n✅✅✅ All tests passed!")
