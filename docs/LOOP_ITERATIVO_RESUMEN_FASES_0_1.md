# Loop Iterativo — Resumen Fases 0-1 Completadas

**Fecha:** 2026-11-11 | **Estado:** Base lista (FASES 0-1 Act, 2-7 Plan)

---

## ✅ Completado (Act)

### FASE 0: Esquemas JSON
- ✅ `docs/schemas/spec.schema.json` — descripción verbalizada + segmentos + volumen inferido
- ✅ `docs/schemas/segment.schema.json` — subsegmento con forma 3D y candidatos
- ✅ `docs/schemas/diff_report.schema.json` — diffs anclados por A4 Judge
- ✅ `docs/schemas/loop_state.schema.json` — estado persistente del bucle

### FASE 1: Motor CORE
- ✅ `ldraw_tools/improvement_loop.py` — Orquestador del bucle
  - `IterationResult` dataclass
  - `ImprovementLoop.run()` — ejecuta: A2→Validators→A3→A4→Scoring→Parada
  - Anti-regresión: hill-climbing, rastrea best_iteration
  - Persistencia: loop_state.json

---

## 📋 Documentado para Continuación

### Fases 2-7 (Plan)
- **FASE 2:** ProfileAdapter (base + brand_logo especializado)
- **FASE 3:** ShapeMatcher (volumen→pieza cuantitativo)
- **FASE 4:** Integración Webapp/CLI
- **FASE 5:** Documentación CORE + perfiles
- **FASE 6:** ModelRouter (escalado adaptativo Claude)
- **FASE 7:** Tests + validación (gmail_logo + fauna)

Ubicación: `docs/IMPLEMENTATION_PLAN_PHASES_2_7.md`

---

## 🎯 Arquitectura CORE (Genérico)

```
[A1] Descriptor GT → spec.json (una vez)
  ↓
[Loop 0..N]
  ├─ [A2] Designer (spec + feedback previo) → plan.json
  ├─ [Validators] Deterministas (geometry, contacts, BOM)
  ├─ [A3] Descriptor Blind → render_spec.json
  ├─ [A4] Judge (GT vs render, visual directo) → diff_report.json
  └─ [Orq] Score + Converge? + Anti-regr + Feedback

[Profile Adapters] (especializados por dominio)
├─ brand_logo: whitelist, scoring_weights, rúbrica
├─ fauna, bust_hd, starwars: (próximas FASE 2)
```

---

## 🔑 Decisiones Incorporadas

1. **Doble canal comparación:** simbólico (spec↔spec) + visual (GT+renders→A4)
2. **Roles separados:** A4 ≠ A2, A3 describe a ciegas (anti-sesgo)
3. **Segmentación + volumen:** cada segment → inferred_volume → shape_matcher (cuantitativo)
4. **Modelos Claude:** A1/A4 Sonnet/Opus, A2 Sonnet, A3 Haiku (escalado A4 si estanca)
5. **Salvaguardas:** parada, anti-regr, top-N diffs, loop_state.json
6. **Genérico + especializable:** ProfileAdapter por dominio sin tocar CORE

---

## 🚀 Próximo: FASE 2 (ProfileAdapter) en Act Mode

Preguntas antes de empezar:
1. Nombres exactos de modelos Claude en tu proxy?
2. ¿A2 usa LLM o reutiliza BrandLogoBuilder?
3. ¿A3 describe 4 vistas en batch o separadas?

---

Ver `docs/IMPLEMENTATION_PLAN_PHASES_2_7.md` para detalles de Fases 2-7.
