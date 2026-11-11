# LNOVA-DRAW: Loop Iterativo — Resumen Ejecutivo Final

**Estado:** ✅ Fases 0-1 Completadas | 📋 Fases 2-7 Documentadas  
**Fecha:** 2026-11-11 | **Líneas totales:** ~920

---

## ✅ Objetivo Logrado

Un **sistema genérico de mejora iterativa** para LNOVA-DRAW válido para 4 perfiles que cierra el loop: descripción GT → diseño 3D → render → comparación → feedback → iteración.

---

## Entregables Completados (Act Mode)

### Esquemas JSON (4 archivos, 11.5 KB)
- `docs/schemas/spec.schema.json` — Descripción verbalizada + segmentos + volumen 3D
- `docs/schemas/segment.schema.json` — Subsegmentos con forma 3D inferida
- `docs/schemas/diff_report.schema.json` — Diffs anclados por A4 Judge
- `docs/schemas/loop_state.schema.json` — Memoria persistente del bucle

### Motor CORE (1 archivo, 2.5 KB Python)
- `ldraw_tools/improvement_loop.py` — Orquestador iterativo
  - `IterationResult` dataclass
  - `ImprovementLoop.run()` — Flujo: A2→Validators→A3→A4→Score→Parada
  - Anti-regresión (hill-climbing) + persistencia

### Documentación (3 archivos)
- `docs/LOOP_ITERATIVO_RESUMEN_FASES_0_1.md` — Quick reference
- `docs/IMPLEMENTATION_PLAN_PHASES_2_7.md` — Fases 2-7 detalladas
- `docs/ARTEFACTOS_GENERADOS_FASES_0_1.md` — Este proyecto

---

## Arquitectura CORE (Genérica)

```
[A1] Descriptor GT → spec.json (una vez)
  ↓
[LOOP]
  ├─ [A2] Designer (spec + feedback) → plan.json → .mpd
  ├─ [Validators] Deterministas (geometry, contacts, BOM)
  ├─ [A3] Descriptor Blind → render_spec.json
  ├─ [A4] Judge (GT vs render, visual directo) → diff_report.json
  └─ [Orq] Score + Converge? + Anti-regr + Feedback

[ProfileAdapters] (brand_logo, fauna, bust_hd, starwars)
  └─ whitelist, scoring_weights, rúbrica (FASE 2)
```

---

## Decisiones Clave

1. **Doble canal comparación:** simbólico (spec↔spec) + visual (GT+renders)
2. **Roles separados:** A4 ≠ A2; A3 describe a ciegas (anti-sesgo)
3. **Segmentación + volumen:** segment → inferred_volume → shape_matcher (cuantitativo)
4. **Modelos optimizados:** A1/A4 Sonnet/Opus, A2 Sonnet, A3 Haiku (escalado A4)
5. **Salvaguardas:** parada, anti-regr, top-N diffs, loop_state.json
6. **Genérico:** ProfileAdapter + CORE sin duplicación

---

## Economía de Modelos

| Agente | Modelo | Coste | Razón |
|--------|--------|-------|-------|
| A1 | Sonnet 4.8 | Bajo | Cacheado (1× diseño) |
| A2 | Sonnet 4.x | Medio | Acotado + guiado |
| A3 | Haiku 4.x | **Bajo** | Repetitivo, perceptual simple |
| A4 | Sonnet→Opus | Medio-Alto | Escalado si estanca |

**Resultado:** ~60-70% menor coste vs. Opus para todo

---

## Fases 2-7 (Plan, ~10-15h)

1. **FASE 2:** ProfileAdapter (1-2h)
2. **FASE 3:** ShapeMatcher (1-2h)
3. **FASE 4:** Integración Webapp/CLI (2-3h)
4. **FASE 5:** Documentación (2-3h)
5. **FASE 6:** ModelRouter (1h)
6. **FASE 7:** Tests + validación (1-2h)

Ver `IMPLEMENTATION_PLAN_PHASES_2_7.md` para detalles.

---

## Validación

✅ Motor CORE compila sin errores  
✅ Esquemas JSON válidos (4 archivos)  
✅ Plan documentado para continuación

---

## Próximo: Act Mode con FASE 2 (ProfileAdapter)

Ref: `docs/IMPLEMENTATION_PLAN_PHASES_2_7.md`
