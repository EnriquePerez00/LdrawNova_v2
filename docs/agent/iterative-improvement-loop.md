---
title: "Iterative Improvement Loop — CORE Architecture"
date: "2026-11-11"
status: "Implemented (FASES 0-6)"
---

# Improvement Loop: LNOVA-DRAW CORE

## 5-Agent Orchestration Pattern

```
[A1] DESCRIPTOR GT → spec.json (once per design)

[LOOP 0..N-1]
  ├─ [A2] DESIGNER 3D (spec + feedback) → plan.json
  ├─ [VALIDATORS] Geometry checks (deterministic, no LLM)
  ├─ [A3] DESCRIPTOR-INVERSO (blind to GT) → render_spec.json
  ├─ [A4] JUDGE/DIFFER (GT vs render + visual) → diff_report.json
  └─ [ORQUESTADOR] Score + Converge? + Anti-regr + Feedback
```

## Scoring (0-100)

**Per-Axis Scores** (configurable per profile):
- `color_fidelity` (weight: 0.30 default, 0.35 for logos)
- `geometry_accuracy` (0.25)
- `proportion_accuracy` (0.25)
- `completeness` (0.10)
- `structure_integrity` (0.10)

**Global Score** = Σ(axis × weight)

## Convergence (3-way OR)

```python
converged = (
    global_score >= 85.0 OR
    max_severity < 4 OR
    iteration >= 3
)
```

## Diffs (Actionable Feedback)

Each diff anchored to location + severity + suggested fix:

```json
{
  "segment_id": "seg_blue_pillar",
  "type": "proportion",
  "severity": 2,
  "location_norm": [0.08, 0.30, 0.22, 0.95],
  "suggested_fix": "Reduce width by 2 studs"
}
```

**Top-N Selection:** Only top 1-3 diffs per iteration → prevents oscillation

## Anti-Regression: Hill-Climbing

```python
if new_score > best_score:
    best = current
    save_mpd()
elif new_score < best - margin:
    revert()  # Skip this fix
```

**Persistence:** `loop_state.json` tracks best_iteration, reverts, full history

## ShapeMatcher: Volume → Parts

```
inferred_volume{radius: 2}
    → ShapeMatcher.match()
    → [("27925.dat", 95.0, "macaroni R=2"), ...]
```

Enables **quantitative geometry feedback** in diffs.

## ProfileAdapter Pattern (Specialization)

Each domain (brand_logo, fauna, bust_hd, starwars) customizes via ProfileAdapter:
- scoring_weights
- evaluation_rubric
- volume_to_part_matcher()

No CORE loop changes needed.

## Model Routing (Gemini 2.5 Flash VLM + Claude Haiku Code)

| Agent | Model | Type | Cost | Why |
|-------|-------|------|------|-----|
| A1 (Descriptor GT) | **gemini-2.5-flash** | VLM | Medium | Multi-image analysis (once per design) |
| A2 (Designer 3D) | **claude-haiku-5** | Code | **Low** | Text/code generation, no images |
| A3 (Descriptor Blind) | **gemini-2.5-flash** | VLM | Low-Med | Repetitive task (4 views × N iterations) |
| A4 (Judge/Differ) | gemini-2.5-flash→pro | VLM | Med-High | Escalates to gemini-2.5-pro if stagnant |

**Infrastructure:** Proxy Cline LiteLLM (`http://localhost:6655/litellm`) with OpenAI-compatible `/v1/chat/completions`  
**Fallback VLM:** `llama3.2-vision:11b` (Ollama :11434) if proxy fails  
**Cost Savings:** ~50% vs. using gemini-2.5-pro for all agents; ~40% vs. baseline

## Environment

```bash
export LLM_PROVIDER="llmproxy"
export LLM_BASE_URL="http://localhost:6655/litellm"
export LLM_SECRET="<REDACTED-set-in-env>"

export LLM_A1_MODEL="gemini-2.5-flash"      # VLM: GT descriptor
export LLM_A2_MODEL="claude-haiku-5"        # Code: designer
export LLM_A3_MODEL="gemini-2.5-flash"      # VLM: render blind
export LLM_A4_MODEL="gemini-2.5-flash"      # VLM: judge (escalates to -pro on stagnation)

export LLM_VLM_FALLBACK_MODEL="llama3.2-vision:11b"
export LLM_VLM_FALLBACK_BASE_URL="http://127.0.0.1:11434"
```


## Data Schemas

- `spec.schema.json` (GT description + volumes)
- `render_spec.schema.json` (rendered description)
- `diff_report.schema.json` (diffs + severity)
- `loop_state.schema.json` (history + best + anti-regr)

---

See `docs/IMPLEMENTATION_PLAN_PHASES_2_7.md` for full integration details.
