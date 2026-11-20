#!/usr/bin/env python3
"""Genera docs/AGENTIC_ARCHITECTURE.md: documento único de arquitectura agéntica.

Fuentes: agents.yaml (registro curado) + código (AST/regex) + skills/perfiles.
El script contrasta lo curado con el código (drift) y lo vuelca en el informe.

Uso: .venv/bin/python scripts/generate_agent_report.py [--out PATH] [--check]
  --check: exit 1 si hay hallazgos (CI / cron / pre-commit).
"""
import argparse
import ast
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "ldraw_tools"
SECRET_RE = re.compile(r"(LLM_SECRET|API_KEY|SECRET)\S*\s*=\s*[\"']?[0-9a-fA-F\-]{16,}")


def read(p: Path) -> str:
    try:
        return p.read_text(errors="ignore")
    except OSError:
        return ""


def load_registry() -> dict:
    return yaml.safe_load(read(ROOT / "agents.yaml")) or {}


def func_source(path: Path, name: str) -> str:
    src = read(path)
    try:
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.FunctionDef) and n.name == name:
                return ast.get_source_segment(src, n) or ""
    except SyntaxError:
        pass
    return ""


def code_facts(agents: dict) -> dict:
    """Extrae del código lo que el registro afirma, para contrastarlo."""
    facts = {}
    router_src = read(T / "model_router.py")
    router = dict(re.findall(r'"(A\d)":\s*os\.getenv\("[A-Z0-9_]+",\s*"([^"]+)"\)', router_src))
    for k, a in agents.items():
        src = func_source(ROOT / a["module"], a["function"])
        facts[k] = dict(
            found=bool(src),
            line=next((i for i, l in enumerate(read(ROOT / a["module"]).splitlines(), 1)
                       if re.match(rf"def {a['function']}\b", l)), None),
            models=sorted(set(re.findall(r'"model":\s*"([^"]+)"|model="([^"]+)"', src) and
                              [x for t in re.findall(r'"model":\s*"([^"]+)"|model="([^"]+)"', src) for x in t if x])),
            timeout=(re.findall(r"timeout=(\d+)", src) or [None])[0],
            temperature=(re.findall(r'"temperature":\s*([\d.]+)', src) or [None])[0],
            max_tokens=(re.findall(r'"max_tokens":\s*(\d+)', src) or [None])[0],
            stub="placeholder" in src and "vlm_chat(" not in src and "design_3d_with_llm(" not in src,
            router_default=router.get(k),
        )
    return facts


def loop_facts() -> dict:
    src = read(T / "improvement_loop_v2.py")
    pol = read(T / "loop_policy.py")
    g = lambda pat, s=src: (re.search(pat, s) or [None, "?"])[1]
    return dict(
        max_iter=g(r"max_iter: int = (\d+)"),
        threshold=g(r"threshold: float = ([\d.]+)"),
        uses_router="ModelRouter" in src,
        uses_policy="loop_policy" in src,
        revert="should_revert" in src,
        stop_sev=g(r"SEVERITY_STOP_THRESHOLD = (\d+)", pol),
        revert_margin=g(r"REVERT_MARGIN = ([\d.]+)", pol),
        stagnation_window="2",
    )


def parse_skills():
    res = []
    for p in sorted((ROOT / ".agents" / "skills").glob("*/SKILL.md")):
        txt = read(p)
        fm = re.match(r"---\n(.*?)\n---", txt, re.S)
        meta = {}
        if fm:
            try:
                meta = yaml.safe_load(fm.group(1)) or {}
            except yaml.YAMLError:
                pass
        res.append((meta.get("name", p.parent.name), " ".join(str(meta.get("description", "")).split()),
                    p.relative_to(ROOT)))
    return res


def parse_profiles():
    out = []
    pdir = ROOT / "profiles"
    if pdir.exists():
        for d in sorted(x for x in pdir.iterdir() if x.is_dir() and not x.name.startswith(("_", "."))):
            files = sorted(f.name for f in d.rglob("*")
                           if f.is_file() and f.suffix in (".md", ".json", ".py") and "__pycache__" not in str(f))
            out.append((d.name, files[:8]))
    return out


def find_secrets():
    skip = {".venv", ".git", "output", "data", "node_modules"}
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in (".md", ".txt", ".yaml", ".yml") or skip & set(p.parts):
            continue
        if SECRET_RE.search(read(p)):
            hits.append(str(p.relative_to(ROOT)))
    return hits


def detect_drift(reg, facts, loop, secrets):
    f = []
    for k, a in reg["agents"].items():
        c = facts[k]
        if not c["found"]:
            f.append(f"`{k}`: función `{a['function']}` no encontrada en `{a['module']}`.")
            continue
        if c["stub"]:
            f.append(f"`{k}` es un STUB (no llama a ningún LLM).")
        if c["router_default"] and c["router_default"] != a["default_model"]:
            f.append(f"`{k}`: default del router `{c['router_default']}` ≠ registro `{a['default_model']}`.")
        p = a.get("params", {})
        for key, val in (("timeout", p.get("timeout_s")), ("temperature", p.get("temperature")),
                         ("max_tokens", p.get("max_tokens"))):
            if c[key] is not None and val is not None and str(val) != str(c[key]):
                f.append(f"`{k}`: {key} en código `{c[key]}` ≠ registro `{val}`.")
    if not loop["uses_router"]:
        f.append("El loop V2 no usa ModelRouter (modelos fijos).")
    if not loop["uses_policy"]:
        f.append("El loop V2 no usa loop_policy (severidad/convergencia sin normalizar).")
    if not loop["revert"]:
        f.append("Hill-climbing documentado pero no implementado en el loop V2.")
    if secrets:
        f.append("Posible secreto en claro en: " + ", ".join(secrets))
    return f


def build():
    reg = load_registry()
    agents = reg["agents"]
    facts = code_facts(agents)
    loop = loop_facts()
    skills, profiles, secrets = parse_skills(), parse_profiles(), find_secrets()
    findings = detect_drift(reg, facts, loop, secrets)
    tools = reg.get("tools", {})
    L, a = [], None
    a = L.append

    a("# Arquitectura agéntica de LdrawNova")
    a(f"\n> Generado por `scripts/generate_agent_report.py` · {datetime.now():%Y-%m-%d %H:%M} · "
      "fuente curada: `agents.yaml` (no editar este fichero a mano)\n")

    a("## 1. Resumen ejecutivo\n")
    a(f"- **Agentes LLM del loop:** {len(agents)} — " + ", ".join(f"{k} {v['name']}" for k, v in agents.items()))
    a(f"- **Actores adicionales:** {len(reg['actors'])} — " + ", ".join(x['name'] for x in reg['actors']))
    a(f"- **Skills:** {len(skills)} · **Perfiles:** {len(profiles)} · **Tools registradas:** {len(tools)}")
    a(f"- **Hallazgos abiertos:** {len(findings)}\n")

    a("## 2. Paradigmas y relación\n")
    for p in reg["paradigms"]:
        a(f"- **{p['name']}** — {' '.join(p['description'].split())}")
    a("")

    a("## 3. Flujo y orden de actuación\n")
    a("```mermaid\nflowchart TD\n  U[Usuario: imagen/prompt] --> AG[Antigravity: Step 0 + 6-Question Gate]\n"
      "  AG --> GEN[generate.py → ldraw-agent build/validate/inspect/render]\n"
      "  U -. GT .-> A1[A1 Descriptor GT]\n  A1 -->|spec.json| LOOP\n"
      "  GEN -. candidato .-> LOOP\n"
      "  subgraph LOOP[ImprovementLoopV2 - iter 0..N-1]\n"
      "    A2[A2 Designer 3D] --> V[Validadores: geometría, BOM]\n    V --> R[LeoCAD: 4 vistas]\n"
      "    R --> C[Color + Overlap]\n    C --> A3[A3 Blind]\n    A3 --> A4[A4 Judge]\n"
      "    A4 --> POL{loop_policy}\n    POL -- revert si peor que best --> A2\n    POL -- top-3 diffs --> A2\n  end\n"
      "  POL -- converge --> OUT[best/design.mpd + loop_state.json + telemetría]\n```\n")
    a("Orden: **A1** (1 vez) → por iteración **A2 → validadores → render → color/overlap → A3 → A4 → loop_policy** → salida `best/`.\n")

    a("## 4. Parámetros del loop (leídos del código)\n")
    a("| Parámetro | Valor | Origen |\n|---|---|---|")
    a(f"| `max_iter` | {loop['max_iter']} | `improvement_loop_v2.py` |")
    a(f"| `threshold` (score) | {loop['threshold']} | `improvement_loop_v2.py` |")
    a(f"| Parada por severidad | `max_severity < {loop['stop_sev']}` (solo si A4 juzgó con éxito) | `loop_policy.py` |")
    a(f"| Margen de revert | {loop['revert_margin']} puntos bajo el mejor | `loop_policy.py` |")
    a(f"| Estancamiento A4 | {loop['stagnation_window']} iteraciones sin mejora → gemini-2.5-pro | `model_router.py` |")
    a("| Severidad | `critical=5, high=4, medium=2, low=1`; acepta enteros | `loop_policy.normalize_severity` |")
    a("| Feedback | top-3 diffs por severidad | `loop_policy.top_diffs` |\n")
    a("**Convergencia (OR):** `score ≥ threshold` · `max_severity < 4` (con A4 válido) · `iter = max_iter-1`.\n")

    a("## 5. Fichas de agentes\n")
    for k, ag in agents.items():
        c = facts[k]
        a(f"### {k} — {ag['name']} ({ag['kind']})")
        a(f"- **Misión:** {ag['mission']}\n- **Objetivos:** {ag['objectives']}\n- **Tareas:** {ag['tasks']}")
        a(f"- **Condicionantes:** {ag['constraints']}")
        a(f"- **Modelo:** `{ag['default_model']}` (override `{ag['env_model']}`; inyectado vía `llm_config['models']['{k}']` por ModelRouter)")
        a(f"- **Parámetros:** " + ", ".join(f"`{x}={y}`" for x, y in ag.get("params", {}).items()))
        a(f"- **Entradas:** {ag['inputs']} · **Salidas:** {ag['outputs']}")
        a(f"- **Recibe de:** {ag['upstream']} · **Entrega a:** {ag['downstream']}")
        a(f"- **Implementación:** [{ag['module']}](file://{ROOT}/{ag['module']}#L{c['line'] or 1}) (`{ag['function']}`)")
        a("- **Tools:** " + "; ".join(f"`{t}` → {tools.get(t, '?')}" for t in ag["tools"]) + "\n")
    for ac in reg["actors"]:
        a(f"### {ac['name']} ({ac['kind']})\n- **Rol:** {ac['role']}\n- **Tools:** " +
          "; ".join(f"`{t}`" + (f" → {tools[t]}" if t in tools else "") for t in ac["tools"]) + "\n")

    a("## 6. Mapa de modelos y LLM\n")
    a("| Agente | Tipo | Modelo por defecto | Variable | Router (código) |\n|---|---|---|---|---|")
    for k, ag in agents.items():
        a(f"| {k} | {ag['kind']} | `{ag['default_model']}` | `{ag['env_model']}` | `{facts[k]['router_default'] or '—'}` |")
    a("\nInfra: proxy LiteLLM (OpenAI-compatible `/v1/chat/completions`) · fallback VLM local Ollama · escalada A4 flash→pro.\n")

    a("## 7. Variables de entorno\n")
    a("| Variable | Default | Descripción |\n|---|---|---|")
    for k, v in reg["env"].items():
        a(f"| `{k}` | `{v['default']}` | {v['desc']} |")
    a("")

    a("## 8. Catálogo de tools\n")
    a("| Tool | Qué habilita |\n|---|---|")
    for k, v in tools.items():
        a(f"| `{k}` | {v} |")
    a("")

    a("## 9. Skills y perfiles (capa Antigravity)\n")
    a("| Skill | Descripción | Fichero |\n|---|---|---|")
    for n, d, p in skills:
        a(f"| {n} | {d[:170]} | `{p}` |")
    a("\n| Perfil | Artefactos |\n|---|---|")
    for n, fl in profiles:
        a(f"| {n} | {', '.join(fl)} |")
    a("\nRuteo (GEMINI.md Step 0): imagen+texto → `bust_hd` / `starwars_scifi` / `fauna` / `brand_logo`; ambigüedad → preguntar.\n")

    a("## 10. Limitaciones y condiciones de contorno\n")
    a("\n".join(f"- {x}" for x in reg["limitations"]) + "\n")

    a("## 11. Hallazgos automáticos (drift / riesgo)\n")
    a("\n".join(f"- ⚠️ {x}" for x in findings) if findings else "✅ Sin hallazgos.")
    a("")
    return "\n".join(L), findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "AGENTIC_ARCHITECTURE.md"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    md, findings = build()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"✓ {out} ({len(findings)} hallazgos)")
    for x in findings:
        print(" -", x)
    if args.check and findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
