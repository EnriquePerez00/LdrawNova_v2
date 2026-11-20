#!/bin/bash
# Progressive Scale Test Launcher
# Usage: ./run_progressive_scale_test.sh [escalon_num] [output_dir]

set -e

LDRAW_NOVA_ROOT="/Users/I764690/Code_personal/LdrawNova"
SPLITS_FILE="$LDRAW_NOVA_ROOT/output/bench/dataset/splits.json"
IO_DIR="/Users/I764690/Code_personal/LegoGPT/data/normalized_io"
OUTPUT_DIR="${2:-/tmp/scale_test_progressive}"
START_ESCALON="${1:-1}"

# Validate inputs
if [ ! -f "$SPLITS_FILE" ]; then
    echo "❌ splits.json not found: $SPLITS_FILE"
    exit 1
fi

if [ ! -d "$IO_DIR" ]; then
    echo "❌ IO dir not found: $IO_DIR"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo ""
echo "=================================================================================="
echo "🚀 PROGRESSIVE SCALE TESTING"
echo "=================================================================================="
echo "Start escalón: $START_ESCALON"
echo "Output dir:    $OUTPUT_DIR"
echo "Splits:        $SPLITS_FILE"
echo "IO corpus:     $IO_DIR"
echo ""
echo "⏱️  Starting at: $(date)"
echo "⏱️  Escalón 1: ~45-90 min (MICRO/trivial)"
echo "⏱️  Escalón 2: ~90-180 min (MICRO/simple)"
echo "⏱️  Escalón 3: ~120-240 min (SMALL)"
echo "⏱️  Escalón 4: ~60-120 min (MEDIUM)"
echo "⏱️  Total:     ~11-17 hours"
echo ""
echo "📊 Gates check:"
echo "  1. Success rate ≥ 80%"
echo "  2. Baseline avg_score < 10.0"
echo "  3. Delta learning ≥ -1.0"
echo ""

# Run python script
cd "$LDRAW_NOVA_ROOT"

# Activate virtualenv
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
fi

python3 scripts/bench/scale_test_progressive.py \
  --splits "$SPLITS_FILE" \
  --io-dir "$IO_DIR" \
  --start-escalon "$START_ESCALON" \
  --output "$OUTPUT_DIR" 2>&1 | tee "$OUTPUT_DIR/run_$(date +%Y%m%d_%H%M%S).log"

echo ""
echo "✅ Done!"
echo "📊 Report: $OUTPUT_DIR/MASTER_REPORT.json"
echo "⏱️  Ended at: $(date)"
