"""Simulation harness for scale test validation (no external dependencies).

Simulates the behavior of harness_e2e_real.py for testing the constraint
injection mechanism WITHOUT requiring LLM, leocad, requests, etc.

Used for validation when full environment is not available.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import random


class SimulatedLearningHook:
    """Simulates learning hook behavior."""
    
    def __init__(self, output_dir: Path):
        self.rules_file = output_dir / "learned_rules.json"
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict[str, Any]:
        """Load rules from JSON."""
        if self.rules_file.exists():
            with open(self.rules_file) as f:
                return json.load(f)
        return {"total_rules": 0, "active_rules": 0, "rules": []}
    
    def get_learned_constraints(self) -> list:
        """Return active rule descriptions."""
        active = [r["description"] for r in self.rules.get("rules", []) 
                  if r.get("is_active", False)]
        return active
    
    def register_incident(self, incident_type: str, set_id: str):
        """Simulate incident registration."""
        # For simulation: after 2 sets, promote
        for rule in self.rules.get("rules", []):
            if rule["type"] == incident_type:
                if set_id not in rule.get("sets_affected", []):
                    rule["sets_affected"].append(set_id)
                if len(rule["sets_affected"]) >= 2:
                    rule["is_active"] = True
                return
        
        # New rule
        self.rules["rules"].append({
            "type": incident_type,
            "description": f"Rule: {incident_type}",
            "sets_affected": [set_id],
            "is_active": False
        })
        self.rules["total_rules"] = len(self.rules["rules"])
        self.rules["active_rules"] = sum(1 for r in self.rules["rules"] if r.get("is_active"))
    
    def save(self):
        """Save rules to JSON."""
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.rules_file, "w") as f:
            json.dump(self.rules, f, indent=2)


class SimulatedSet:
    """Simulates a single design generation iteration."""
    
    def __init__(self, sample_id: str, parts_count: int, learning_enabled: bool, hook: SimulatedLearningHook):
        self.sample_id = sample_id
        self.parts_count = parts_count
        self.learning_enabled = learning_enabled
        self.hook = hook
    
    def simulate_generation(self, iteration: int) -> Dict[str, Any]:
        """Simulate A2 generation + gate validation."""
        
        # Simulate: base score depends on parts
        base_score = 40 + (self.parts_count * 0.5)
        
        # Simulate incident detection by gate
        incident_types = ["z_spacing_violation", "overlap_violation", "underflow"]
        incident = random.choice(incident_types)
        
        # Simulate: learning improves score
        constraints_injected = self.hook.get_learned_constraints()
        if self.learning_enabled and constraints_injected:
            # Each constraint helps reduce incidents
            improvement = len(constraints_injected) * 2.0
            base_score += improvement
        
        # Add randomness (simulates variation)
        score = base_score + random.uniform(-5, 5)
        score = min(100, max(0, score))
        
        # Simulate: register incident for learning
        if self.learning_enabled:
            self.hook.register_incident(incident, self.sample_id)
        
        return {
            "sample_id": self.sample_id,
            "iteration": iteration,
            "score": score,
            "incident": incident,
            "constraints_injected": len(constraints_injected),
            "learning_enabled": self.learning_enabled
        }


def simulate_scale_test(
    n_sets: int = 10,
    max_iter: int = 2,
    output_base: Path = Path("/tmp/scale_test_simulation")
) -> Dict[str, Any]:
    """Simulate full scale test without external dependencies."""
    
    output_base.mkdir(parents=True, exist_ok=True)
    
    # Sample sets for simulation
    sample_sets = [(f"RB-MOC-{21519 + i}", 6 + (i % 3)) for i in range(n_sets)]
    
    print(f"\n{'='*70}")
    print(f"SCALE TEST SIMULATION: {n_sets} sets, {max_iter} iterations")
    print(f"{'='*70}")
    
    # BASELINE: learning OFF
    print(f"\n[BASELINE] Learning OFF")
    baseline_results = []
    for sample_id, parts in sample_sets:
        hook = SimulatedLearningHook(output_base / "baseline")
        sim = SimulatedSet(sample_id, parts, learning_enabled=False, hook=hook)
        
        iteration_scores = []
        for it in range(max_iter):
            result = sim.simulate_generation(it)
            iteration_scores.append(result["score"])
        
        best_score = max(iteration_scores)
        baseline_results.append({
            "sample_id": sample_id,
            "best_score": best_score,
            "iterations": len(iteration_scores)
        })
        print(f"  {sample_id}: score={best_score:.1f}, iters={len(iteration_scores)}")
    
    # LEARNING: learning ON
    print(f"\n[LEARNING] Learning ON (shared output)")
    learning_hook = SimulatedLearningHook(output_base / "learning")
    learning_results = []
    
    for set_idx, (sample_id, parts) in enumerate(sample_sets):
        print(f"  [{set_idx+1}/{n_sets}] {sample_id}...", end="")
        sim = SimulatedSet(sample_id, parts, learning_enabled=True, hook=learning_hook)
        
        iteration_scores = []
        for it in range(max_iter):
            result = sim.simulate_generation(it)
            iteration_scores.append(result["score"])
            if it == 0 and set_idx == 0:
                print(f" (iter 0: constraints_injected={result['constraints_injected']})")
                if set_idx > 0:
                    print()
        
        best_score = max(iteration_scores)
        learning_results.append({
            "sample_id": sample_id,
            "best_score": best_score,
            "iterations": len(iteration_scores)
        })
        print(f"    score={best_score:.1f}, iters={len(iteration_scores)}")
    
    learning_hook.save()
    
    # Aggregate
    def agg(results):
        if not results:
            return {}
        valid = [r for r in results if "best_score" in r]
        return {
            "count": len(valid),
            "avg_score": sum(r["best_score"] for r in valid) / len(valid),
            "avg_iter": sum(r["iterations"] for r in valid) / len(valid),
        } if valid else {}
    
    baseline_agg = agg(baseline_results)
    learning_agg = agg(learning_results)
    
    # Report
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"\nBASELINE:")
    print(f"  Avg score: {baseline_agg.get('avg_score', 0):.1f}")
    print(f"  Avg iter: {baseline_agg.get('avg_iter', 0):.1f}")
    
    print(f"\nLEARNING:")
    print(f"  Avg score: {learning_agg.get('avg_score', 0):.1f}")
    print(f"  Avg iter: {learning_agg.get('avg_iter', 0):.1f}")
    print(f"  Active rules: {learning_hook.rules.get('active_rules', 0)}")
    
    score_delta = learning_agg.get('avg_score', 0) - baseline_agg.get('avg_score', 0)
    iter_delta = learning_agg.get('avg_iter', 0) - baseline_agg.get('avg_iter', 0)
    
    print(f"\nDELTA (Learning - Baseline):")
    print(f"  Score: {score_delta:+.1f} {'(better!)' if score_delta > 0 else ''}")
    print(f"  Iter: {iter_delta:+.1f}")
    
    report = {
        "timestamp": str(Path(__file__).parent),
        "mode": "simulation",
        "n_sets": n_sets,
        "sets": [s[0] for s in sample_sets],
        "baseline": baseline_agg,
        "learning": learning_agg,
        "results": {
            "baseline": baseline_results,
            "learning": learning_results,
        }
    }
    
    report_file = output_base / "SCALE_TEST_SIMULATION_REPORT.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✅ Report saved: {report_file}")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="Number of sets")
    parser.add_argument("--max-iter", type=int, default=2, help="Max iterations")
    parser.add_argument("--output", type=Path, default=Path("/tmp/scale_test_simulation"), help="Output dir")
    args = parser.parse_args()
    
    simulate_scale_test(n_sets=args.n, max_iter=args.max_iter, output_base=args.output)
