# Índice: Loop Iterativo LNOVA-DRAW (Fases 0-1 Completadas)

## Comienza aquí

**Lee en este orden:**
1. `docs/RESUMEN_EJECUTIVO_FINAL.md` ← Start here (5 min)
2. `docs/LOOP_ITERATIVO_RESUMEN_FASES_0_1.md` ← Arquitectura CORE (10 min)
3. `docs/IMPLEMENTATION_PLAN_PHASES_2_7.md` ← Plan para continuar (15 min)

---

## Estructura de Archivos Generados

### Esquemas (Fases 0)
```
docs/schemas/
├── spec.schema.json              Descripción verbalizada del diseño
├── segment.schema.json            Subsegmento con volumen 3D
├── diff_report.schema.json        Diffs anclados + priorizados
└── loop_state.schema.json         Memoria del bucle
```

### Código (Fase 1)
```
ldraw_tools/
└── improvement_loop.py             Motor del bucle iterativo
```

### Documentación (Plan)
```
docs/
├── RESUMEN_EJECUTIVO_FINAL.md              ← Empieza aquí
├── LOOP_ITERATIVO_RESUMEN_FASES_0_1.md    ← Arquitectura
├── IMPLEMENTATION_PLAN_PHASES_2_7.md       ← Próximas fases
├── ARTEFACTOS_GENERADOS_FASES_0_1.md       ← Listado completo
└── INDEX_LOOP_ITERATIVO.md                 ← Este archivo
```

---

## Decisiones Técnicas Principales

**Comparación GT↔Render:**
- Doble canal: simbólico (spec↔spec) + visual directo (imágenes en A4)
- Diffs anclados a ubicación en imagen (location_norm)
- Priorizados por severidad (1-5), top-N enfoque

**Modelos Claude Asignados:**
- A1 (Descriptor GT): Sonnet 4.8 (fuente de verdad, cacheado)
- A2 (Designer): Sonnet 4.x (acotado + guiado por spec)
- A3 (Descriptor Blind): Haiku 4.x (repetitivo, perceptual simple) ← AHORRO MÁXIMO
- A4 (Judge): Sonnet 4.8 → Opus 4.x (escalado si estanca 2 iter)

**Anti-Regresión:**
- Hill-climbing: rastrea `best_iteration` por score
- Si new_score < best - margin → revert + retry

**Persistencia:**
- `loop_state.json` guarda historial completo
- Permite resumir loop interrumpido

---

## Validación de Entregables

```bash
cd /Users/I764690/Code_personal/LdrawNova

# Motor CORE compila ✅
.venv/bin/python -m py_compile ldraw_tools/improvement_loop.py

# Esquemas JSON válidos ✅
ls docs/schemas/*.schema.json | wc -l  # → 4 archivos
```

---

## Próximas Fases (Act Mode Continuo)

### Orden Estricto Recomendado
1. ✅ FASE 0: Esquemas JSON
2. ✅ FASE 1: Motor CORE
3. → **FASE 2:** ProfileAdapter (base + brand_logo)
4. → **FASE 3:** ShapeMatcher
5. → **FASE 4:** Integración webapp/CLI
6. → **FASE 6:** ModelRouter
7. → **FASE 5:** Documentación
8. → **FASE 7:** Tests + validación

### Estimado de Tiempo
- **FASE 2:** 1-2 horas
- **FASE 3:** 1-2 horas
- **FASE 4:** 2-3 horas
- **FASE 5:** 2-3 horas
- **FASE 6:** 1 hora
- **FASE 7:** 1-2 horas
- **Total:** 10-15 horas para cierre completo

---

## Preguntas Antes de FASE 2

1. **Nombres exactos de modelos Claude en tu proxy?**
   - Asumo: `claude-sonnet-4.8`, `claude-opus-4.x`, `claude-haiku-4.x`
   
2. **¿A2 (Designer) usa LLM o reutiliza BrandLogoBuilder?**
   - Asumo: LLM con prompt guiado por spec + feedback
   
3. **¿A3 (Descriptor Blind) describe 4 vistas en batch o separadas?**
   - Asumo: batch (1 llamada, 4 imágenes)

---

## Contacto/Referencia

Para más detalle sobre:
- **Arquitectura CORE:** `docs/LOOP_ITERATIVO_RESUMEN_FASES_0_1.md`
- **Próximas fases:** `docs/IMPLEMENTATION_PLAN_PHASES_2_7.md`
- **Ejemplo de spec.json:** Ver comentarios en `docs/schemas/spec.schema.json`
- **Asignación de modelos:** Tabla en `docs/RESUMEN_EJECUTIVO_FINAL.md`

---

*Generado en Act Mode — 2026-11-11*  
*Sistema listo para FASE 2 en Act Mode*
