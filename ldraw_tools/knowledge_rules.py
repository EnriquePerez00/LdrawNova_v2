"""Knowledge rules: persistence and management of learned generalizations.

Stores rules derived from incident analysis, tracks occurrences across sets,
and promotes rules to "active" status when they appear in >= N distinct sets
(conservative threshold prevents overfitting to single-set artifacts).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Promote rule to "active" (injectable into future sets) after N distinct sets
MIN_SETS_FOR_RULE = int(__import__('os').getenv('MIN_SETS_FOR_RULE', '2'))


class KnowledgeRule:
    """Represents a single learned rule."""
    
    def __init__(
        self,
        rule_id: str,
        category: str,
        fix_pattern: str,
        prompt_injection: str,
        triggered_by: str = "",
        created_at: str = "",
    ):
        self.rule_id = rule_id
        self.category = category
        self.fix_pattern = fix_pattern
        self.prompt_injection = prompt_injection
        self.triggered_by = triggered_by  # incident category that triggered creation
        self.created_at = created_at or datetime.now().isoformat()
        
        # Accumulation
        self.occurrences = 0
        self.sets_affected: Set[str] = set()
        self.confidence = 0.5
        self.last_seen = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "fix_pattern": self.fix_pattern,
            "prompt_injection": self.prompt_injection,
            "triggered_by": self.triggered_by,
            "created_at": self.created_at,
            "occurrences": self.occurrences,
            "sets_affected": sorted(self.sets_affected),
            "confidence": self.confidence,
            "last_seen": self.last_seen,
        }
    
    @staticmethod
    def from_dict(d: Dict[str, Any]) -> KnowledgeRule:
        """Deserialize from JSON dict."""
        rule = KnowledgeRule(
            rule_id=d["rule_id"],
            category=d["category"],
            fix_pattern=d["fix_pattern"],
            prompt_injection=d["prompt_injection"],
            triggered_by=d.get("triggered_by", ""),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )
        rule.occurrences = d.get("occurrences", 0)
        rule.sets_affected = set(d.get("sets_affected", []))
        rule.confidence = d.get("confidence", 0.5)
        rule.last_seen = d.get("last_seen", "")
        return rule
    
    def is_active(self, min_sets: int = MIN_SETS_FOR_RULE) -> bool:
        """Rule is 'active' (injectable) if it's appeared in >= min_sets distinct sets."""
        return len(self.sets_affected) >= min_sets
    
    def register_occurrence(self, set_id: str) -> bool:
        """Register this rule as seen in a set.
        
        Returns:
            True if the rule was just promoted to active (crossed min_sets threshold)
        """
        was_active = self.is_active()
        self.occurrences += 1
        self.sets_affected.add(set_id)
        self.confidence = min(0.99, 0.5 + len(self.sets_affected) * 0.1)
        self.last_seen = datetime.now().isoformat()
        is_now_active = self.is_active()
        
        return not was_active and is_now_active  # newly promoted


class RulesStore:
    """Persistent store of learned rules."""
    
    def __init__(self, rules_file: Path):
        self.rules_file = Path(rules_file)
        self.rules: Dict[str, KnowledgeRule] = {}
        self._load()
    
    def _load(self) -> None:
        """Load rules from JSON file."""
        if not self.rules_file.exists():
            logger.info(f"[RulesStore] No existing rules file, starting fresh")
            return
        
        try:
            data = json.loads(self.rules_file.read_text())
            for rule_dict in data.get("rules", []):
                rule = KnowledgeRule.from_dict(rule_dict)
                self.rules[rule.rule_id] = rule
            logger.info(f"[RulesStore] Loaded {len(self.rules)} rules")
        except Exception as e:
            logger.error(f"[RulesStore] Failed to load: {e}")
    
    def save(self) -> None:
        """Persist rules to JSON file."""
        try:
            self.rules_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "timestamp": datetime.now().isoformat(),
                "total_rules": len(self.rules),
                "active_rules": len([r for r in self.rules.values() if r.is_active()]),
                "rules": [r.to_dict() for r in self.rules.values()],
            }
            self.rules_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"[RulesStore] Failed to save: {e}")
    
    def register_or_update(self, rule_id, category, fix_pattern, prompt_injection, set_id, triggered_by=""):
        """Register/update a rule."""
        if rule_id not in self.rules:
            self.rules[rule_id] = KnowledgeRule(
                rule_id=rule_id, category=category, fix_pattern=fix_pattern,
                prompt_injection=prompt_injection, triggered_by=triggered_by,
            )
        rule = self.rules[rule_id]
        was_promoted = rule.register_occurrence(set_id)
        if was_promoted:
            logger.info(f"[RulesStore] Rule {rule_id} PROMOTED to active")
        self.save()
        return (was_promoted, rule)
    
    def get_active_rules(self):
        """Get all active rules."""
        return [r for r in self.rules.values() if r.is_active()]
    
    def get_rules_for_injection(self, max_rules=5):
        """Get prompts to inject."""
        active = self.get_active_rules()
        active.sort(key=lambda r: (-r.confidence, r.last_seen), reverse=True)
        return [r.prompt_injection for r in active[:max_rules]]
    
    def find_rule_by_category(self, category: str):
        """Find existing rule for a given incident category."""
        for rule in self.rules.values():
            if rule.triggered_by == category:
                return rule
        return None


def create_seed_rules_file(rules_file: Path) -> None:
    """Initialize seed rules file with NO destructive default rules.
    
    AUDIT FIX: Removed the broken Z=i*40 rule which was creating floating islands.
    New rules will be learned during execution, validated by deterministic gate.
    """
    if rules_file.exists():
        return
    seed_rules = []  # Start empty; rules are discovered, not pre-seeded with broken patterns
    rules_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "timestamp": datetime.now().isoformat(),
        "total_rules": len(seed_rules),
        "active_rules": 0,
        "rules": seed_rules,
    }
    rules_file.write_text(json.dumps(data, indent=2))
    logger.info(f"[RulesStore] Created seed rules file (empty - rules learned during execution)")
