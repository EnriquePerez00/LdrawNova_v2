#!/usr/bin/env python3
"""
Audit de piezas con MISSING_CONNECTIVITY_PORT.

Lee el scale report, extrae todas las piezas sin puertos,
las rankea por frecuencia (Pareto 80/20).

Entregable: missing_ports_pareto.json con diagnóstico por pieza.
"""

import sys
import json
from collections import Counter
from pathlib import Path

def audit_missing_ports():
    """Audita piezas faltantes."""
    
    # Cargar el scale_report más reciente
    report_dir = Path("outputs/tier_validation")
    scale_reports = sorted(report_dir.glob("scale_report_*.json"))
    if not scale_reports:
        print("❌ No scale_report encontrado.")
        return
    
    report_path = scale_reports[-1]
    print(f"📖 Analizando: {report_path.name}")
    
    with open(report_path) as f:
        report = json.load(f)
    
    # Extraer todas las piezas con MISSING_CONNECTIVITY_PORT
    missing_parts = Counter()
    for result in report.get("results", []):
        for inc in result.get("incidents", []):
            if inc.get("root_cause_category") == "MISSING_CONNECTIVITY_PORT":
                child_pid = inc.get("child_part_id", "").lower().replace(".dat", "")
                if child_pid:
                    missing_parts[child_pid] += 1
    
    print(f"\n📊 Piezas unicas con MISSING_CONNECTIVITY: {len(missing_parts)}")
    print(f"   Total incidentes MISSING: {sum(missing_parts.values())}")
    
    if not missing_parts:
        print("✅ Ninguna pieza faltante. Excelente.")
        return
    
    # Pareto: top 30 (80/20 rule)
    top_30 = missing_parts.most_common(30)
    print(f"\n🔝 Top 30 piezas (Pareto 80/20):")
    print(f"   {'#':<3} {'Part ID':<12} {'Incidents':<10} {'% of Total':<10}")
    print(f"   {'-'*40}")
    
    total_incidents = sum(missing_parts.values())
    cumulative = 0
    for idx, (pid, count) in enumerate(top_30, 1):
        cumulative += count
        pct = (cumulative / total_incidents * 100) if total_incidents > 0 else 0
        print(f"   {idx:<3} {pid:<12} {count:<10} {pct:>6.1f}%")
    
    # Guardar reporte
    output = {
        "timestamp": report.get("timestamp"),
        "report_used": report_path.name,
        "total_unique_missing": len(missing_parts),
        "total_missing_incidents": sum(missing_parts.values()),
        "pareto_top_30": [
            {"rank": idx, "pid": pid, "incidents": count}
            for idx, (pid, count) in enumerate(top_30, 1)
        ],
        "pareto_80_20": {
            "top_30_incidents": cumulative,
            "top_30_coverage_percent": round(cumulative / total_incidents * 100, 1) if total_incidents > 0 else 0,
        }
    }
    
    out_path = report_dir / "missing_ports_pareto.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Guardado: {out_path.name}")
    print(f"   Cobertura 80/20: Top 30 piezas cubre {output['pareto_80_20']['top_30_coverage_percent']:.1f}% de incidentes")

if __name__ == "__main__":
    audit_missing_ports()

