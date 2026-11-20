#!/usr/bin/env python3
"""Guard anti-secretos (sin dependencias externas).

Comprueba:
  1. `.env` está ignorado por git y NO está trackeado.
  2. Ningún valor secreto de `.env` (claves *SECRET*, *KEY*, *TOKEN*, *PASSWORD*) aparece
     literalmente en ficheros trackeados o no ignorados (working tree).
  3. Patrones genéricos de credenciales hardcodeadas en esos ficheros.
  4. `--history`: ningún valor secreto aparece en el historial de git.

Uso: .venv/bin/python scripts/check_secrets.py [--history]   (exit 1 si hay hallazgos)
Se ejecuta como pre-commit (scripts/install_hooks.sh) y en tests.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY_RE = re.compile(r"(SECRET|KEY|TOKEN|PASSWORD)", re.I)
GENERIC = [
    re.compile(r"""(?i)(secret|api_?key|token|password)["']?\s*[:=]\s*["'][A-Za-z0-9_\-\.]{20,}["']"""),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{24,}"),
]
TEXT_EXT = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".sh", ".toml", ".cfg", ".ini", ".envrc", ".example", ""}


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def env_secrets():
    p = ROOT / ".env"
    out = {}
    if p.exists():
        for line in p.read_text(errors="ignore").splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=\s*[\"']?([^\"'#\n]+)[\"']?", line)
            if m and KEY_RE.search(m.group(1)) and len(m.group(2).strip()) >= 12:
                out[m.group(1)] = m.group(2).strip()
    return out


def candidate_files():
    names = git("ls-files", "-co", "--exclude-standard").splitlines()
    for n in names:
        p = ROOT / n
        if p.is_file() and p.suffix in TEXT_EXT and p.stat().st_size < 2_000_000 \
                and not n.startswith(("data/", "output/", ".cache/", ".venv/")) \
                and n != "scripts/check_secrets.py":
            yield n, p


def run(history=False):
    f = []
    if not subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT).returncode == 0 and (ROOT / ".env").exists():
        f.append(".env NO está en .gitignore")
    if ".env" in git("ls-files").split():
        f.append(".env está trackeado por git")
    secrets = env_secrets()
    for n, p in candidate_files():
        txt = p.read_text(errors="ignore")
        for k, v in secrets.items():
            if v in txt:
                f.append(f"{n}: contiene el valor de {k} (literal)")
        if n.endswith((".example",)):
            continue
        for rx in GENERIC:
            m = rx.search(txt)
            if m and re.search(r"(?i)your|xxx|example|changeme|placeholder|<|\.\.\.", m.group(0)):
                m = None
            if m:
                f.append(f"{n}: patrón de credencial hardcodeada ({m.group(0)[:12]}…)")
                break
    if history:
        for k, v in secrets.items():
            hit = git("log", "--all", "--oneline", "-S" + v).strip()
            if hit:
                f.append(f"historial git contiene {k} en: " + hit.replace("\n", " | "))
    return f


if __name__ == "__main__":
    res = run("--history" in sys.argv)
    for x in res:
        print("✗", x)
    print("✓ sin secretos detectados" if not res else f"{len(res)} hallazgo(s)")
    sys.exit(1 if res else 0)
