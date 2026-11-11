---
title: "Loop Iterativo — Fases 2-7 (Plan)"
date: "2026-11-11"
---

# Fases 2-7: Ejecución Secuencial

## Estado Actual
✅ FASE 0: Esquemas JSON (spec, diff_report, loop_state)
✅ FASE 1: Motor CORE (improvement_loop.py)

## FASE 2: ProfileAdapter

**Archivos:**
- `ldraw_tools/profile_adapter.py` (clase base)
- `profiles/brand_logo/helpers/brand_logo_adapter.py`

**Contenido:**
- Carga whitelist+palette por perfil
- scoring_weights ponderados (brand_logo: color=0.35, proporción=0.30, estructura=0.20)
- evaluation_rubric: qué mira juez en este dominio
- volume_to_part_matcher: mapea volumen→candidatos

**Aceptación:** ProfileAdapter instanciable, carga recursos

---

## FASE 3: ShapeMatcher

**Archivo:** `ldraw_tools/shape_matcher.py`

**Contenido:**
- Indexa piezas por surface_type, dims, radius, slope
- match(inferred_volume) → [(part_id, fit_score)] ordenado

**Aceptación:** match() devuelve candidatos para test segment

---

## FASE 4: Integración Webapp/CLI

**Modificaciones:**
- `webapp/generator_service.py`: envolver en ImprovementLoop
- `ldraw_tools/cli.py`: nuevo cmd `improve`

**Artefactos:**
- `output/<slug>/iterations/iter_N/` (plan, mpd, renders, specs, diff_report)
- `output/<slug>/best/` (mejor mpd)
- `output/<slug>/loop_state.json` (memoria)

**Aceptación:** CLI ejecutable, directorios correctos

---

## FASE 5: Documentación

**Archivos nuevos:**
- `docs/agent/iterative-improvement-loop.md` (arquitectura CORE, esquemas, scoring, salvaguardas, economía modelos)

**Modificaciones:**
- GEMINI.md: añadir §7 "Loop de Mejora Iterativa"
- instructions.md: sección Pipeline Iterativo
- `.agents/skills/ldraw-nova-governance/SKILL.md`: fase 5
- `.agents/skills/ldraw-logo/SKILL.md`: rúbrica específica
- `docs/agent/specification-map.md`: registrar esquemas/módulos

**Aceptación:** Docs autodocumentadas, referencias cruzadas validan

---

## FASE 6: ModelRouter

**Archivo:** `ldraw_tools/model_router.py`

**Contenido:**
- Asignación de modelos por agente (A1..A4)
- Escalado adaptativo A4 si estanca

**Env vars:**
- LLM_A1_MODEL, LLM_A2_MODEL, LLM_A3_MODEL, LLM_A4_MODEL

**Aceptación:** Router resuelve modelos, A4 escalación funciona

---

## FASE 7: Validación

**Tests:** `tests/test_improvement_loop.py`
- Convergencia ≤ 4 iter
- Anti-regresión funciona
- JSON schemas validan

**Casos:** gmail_logo + fauna con REPORT.md

**Aceptación:** gmail_logo score ≥ 80 en ≤ 4 iter, fauna loop funciona

---

## Próximo: FASE 2 (ProfileAdapter) en Act Mode
