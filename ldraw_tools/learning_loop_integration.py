"""Learning loop integration: hooks to capture, classify, and generalize incidents.

Non-invasive wrapper that adds learning capability to improvement_loop_v2
without modifying existing code. Activated via LDRAW_ENABLE_LEARNING flag.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Feature flag
ENABLE_LEARNING = os.getenv("LDRAW_ENABLE_LEARNING", "").lower() in {"1", "true", "yes"}


class LearningHook:
    """Captures incidents from the improvement loop and learns generalizations."""
    
    def __init__(self, output_dir: Path, sample_id: str, llm_client: Any = None):
        self.output_dir = Path(output_dir)
        self.sample_id = sample_id
        self.llm_client = llm_client
        self.enabled = ENABLE_LEARNING
        
        if not self.enabled:
            logger.debug("[LearningHook] Disabled (LDRAW_ENABLE_LEARNING not set)")
            return
        
        # Import learning modules (lazy, only if enabled)
        try:
            from ldraw_tools.incident_taxonomy import IncidentClassifier
            from ldraw_tools.knowledge_rules import RulesStore, create_seed_rules_file
            from ldraw_tools.root_cause_analyzer import analyze_root_cause_and_propose_fix
            
            self.classifier = IncidentClassifier()
            rules_file = self.output_dir.parent / "learned_rules.json"
            create_seed_rules_file(rules_file)
            self.rules_store = RulesStore(rules_file)
            self.analyzer = analyze_root_cause_and_propose_fix
            
            logger.info(f"[LearningHook] Initialized for sample {sample_id}")
        except Exception as e:
            logger.error(f"[LearningHook] Failed to initialize: {e}")
            self.enabled = False
    
    def on_incident_detected(self, diff: Dict[str, Any]) -> None:
        """Called after physical_gate detects an incident.
        
        Classifies it, potentially learns new rules, registers occurrences.
        """
        if not self.enabled:
            return
        
        try:
            # Step 1: Classify using deterministic taxonomy
            category, confidence = self.classifier.classify(diff)
            
            if category:
                # Known category - register occurrence
                logger.debug(f"[LearningHook] Classified as {category} (conf={confidence:.2f})")
                
                # Try to find existing rule for this category
                rule = self.rules_store.find_rule_by_category(category)
                if rule:
                    rule.register_occurrence(self.sample_id)
                    self.rules_store.save()
            else:
                # Unknown category - invoke LLM if available
                logger.debug(f"[LearningHook] Unknown incident, invoking LLM analyzer...")
                
                if not self.llm_client:
                    logger.warning(f"[LearningHook] No LLM client available for analysis")
                    return
                
                analysis = self.analyzer(diff, self.llm_client)
                if not analysis:
                    logger.warning(f"[LearningHook] LLM analysis failed")
                    return
                
                # Register new rule (will be promoted if appears in >= 2 sets)
                rule_id = f"rule_{analysis['category'].lower()}"
                self.rules_store.register_or_update(
                    rule_id=rule_id,
                    category=analysis["category"],
                    fix_pattern=analysis["fix_pattern"],
                    prompt_injection=analysis["prompt_injection"],
                    set_id=self.sample_id,
                    triggered_by=analysis["category"],
                )
                logger.info(f"[LearningHook] Created new rule from LLM analysis: {rule_id}")
        
        except Exception as e:
            logger.error(f"[LearningHook] Error in on_incident_detected: {e}")
    
    def get_learned_constraints(self) -> List[str]:
        """Get list of prompts to inject for a new design (only active rules).
        
        Called by design_generator before building the A2 prompt.
        """
        if not self.enabled:
            return []
        
        try:
            return self.rules_store.get_rules_for_injection(max_rules=5)
        except Exception as e:
            logger.error(f"[LearningHook] Error getting learned constraints: {e}")
            return []
