#!/bin/sh
# Start the LdrawNova Generative Web Studio
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$REPO_DIR"

if [ ! -f .venv/bin/activate ]; then
  echo "Error: Virtual environment .venv not found. Run ./setup.sh first." >&2
  exit 1
fi

# Activate virtual environment
. .venv/bin/activate

# Configure LDraw library and system binaries
export LDRAW_DIR="${LDRAW_DIR:-$HOME/LDraw}"
export PATH="$HOME/.local/bin:$PATH"

echo "=========================================================="
echo "🧱 LdrawNova Generative Studio"
echo "=========================================================="
echo "Python: $(python --version)"
echo "LDraw Library: $LDRAW_DIR"
echo "LeoCAD: $(which leocad 2>/dev/null || echo 'not found')"
echo "Starting web server at http://localhost:8080"
echo "=========================================================="

exec uvicorn webapp.app:app --host 0.0.0.0 --port 8080 --reload
