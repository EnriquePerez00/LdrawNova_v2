#!/usr/bin/env python3
"""
Paso 3: Leer y analizar resultados del scale test
Ejecutar cuando SCALE_TEST_REPORT.json esté disponible
"""
import json
import sys
from pathlib import Path

def main():
    output_dir = Path("output/bench/scale_test_real")
    report_file = output_dir / "SCALE_TEST_REPORT.json"
    
    if not report_file.exists():
        print("❌ SCALE_TEST_REPORT.json no encontrado")
        print(f"   Buscando en: {report_file}")
        print(f"   Directorio existe: {output_dir.exists()}")
        if output_dir.exists():
            print(f"   Contenido: {list(output_dir.glob('*'))}")
        return False
    
    print("\n" + "="*80)
    print("PASO 3: LECTURA Y ANÁLISIS DE RESULTADOS")
    print("="*80 + "\n")
    
    with open(report_file) as f:
        report = json.load(f)
    
    baseline = report.get("baseline", {})
    learning = report.get("learning", {})
    
    print(f"⏱️  Timestamp: {report.get('timestamp', 'N/A')}\n")
    
    print("📊 BASELINE (Learning OFF):")
    print(f"   Samples: {baseline.get('count', 0)}")
    print(f"   Avg score: {baseline.get('avg_score', 0):.1f}/100")
    print(f"   Avg iterations: {baseline.get('avg_iter', 0):.1f}")
    
    print("\n🧠 LEARNING (Learning ON):")
    print(f"   Samples: {learning.get('count', 0)}")
    print(f"   Avg score: {learning.get('avg_score', 0):.1f}/100")
    print(f"   Avg iterations: {learning.get('avg_iter', 0):.1f}")
    
    score_delta = learning.get('avg_score', 0) - baseline.get('avg_score', 0)
    iter_delta = learning.get('avg_iter', 0) - baseline.get('avg_iter', 0)
    
    print("\n🎯 DELTA (Learning vs Baseline):")
    print(f"   Score delta: {score_delta:+.1f} points {'✅' if score_delta > 0 else '⚠️'}")
    print(f"   Iteration delta: {iter_delta:+.1f} {'(faster✅)' if iter_delta < 0 else '(slower⚠️)'}")
    
    # Analizar reglas aprendidas
    learned_rules_file = output_dir / "learning" / "learned_rules.json"
    if learned_rules_file.exists():
        print("\n📚 LEARNED RULES:")
        with open(learned_rules_file) as f:
            rules_data = json.load(f)
        
        active_rules = [r for r in rules_data.get("rules", []) if r.get("is_active")]
        print(f"   Total rules: {len(rules_data.get('rules', []))}")
        print(f"   Active rules: {len(active_rules)}")
        
        for rule in active_rules:
            print(f"     - {rule.get('type', 'unknown')}: sets_affected={rule.get('sets_affected', [])}")
    else:
        print(f"\n⚠️  learned_rules.json not found at {learned_rules_file}")
    
    # Detalle por set
    print("\n📋 RESULTADOS POR SET:")
    print("-" * 80)
    
    results = report.get("results", {})
    baseline_results = results.get("baseline", [])
    learning_results = results.get("learning", [])
    
    # Mapear learning results por sample_id para comparación
    learning_map = {r.get("sample_id"): r for r in learning_results}
    
    for br in baseline_results:
        sample_id = br.get("sample_id", "?")
        lr = learning_map.get(sample_id, {})
        
        b_score = br.get("best_score", 0)
        l_score = lr.get("best_score", 0)
        delta = l_score - b_score
        
        print(f"  {sample_id:15} | Baseline: {b_score:5.1f} → Learning: {l_score:5.1f} | {delta:+5.1f} {'✅' if delta > 0 else '⚠️'}")
    
    print("\n" + "="*80)
    print("✅ ANÁLISIS COMPLETADO")
    print("="*80 + "\n")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
