#!/bin/bash
# Check progress of scale test at any time
# Usage: ./check_scale_test_progress.sh

cd /Users/I764690/Code_personal/LdrawNova

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Scale Test Progress Check                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "⏱️  Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "📊 Progress:"
TOTAL=$(find output/bench/scale_test_real -name 'e2e_result.json' 2>/dev/null | wc -l)
echo "   Completed: $TOTAL/10 e2e_result.json files"

echo ""
echo "🔍 Active processes:"
PROC_COUNT=$(pgrep -f 'harness_e2e_real|scale_test_intermediate' | wc -l)
echo "   Running: $PROC_COUNT processes"

if [ $PROC_COUNT -gt 0 ]; then
    echo "   Status: ⏳ Still in progress"
else
    echo "   Status: ✅ Complete or idle"
fi

echo ""
echo "📂 Directory structure:"
ls -1d output/bench/scale_test_real/*/ 2>/dev/null | head -10 | sed 's/^/   /'

echo ""
echo "📄 Check for results:"
if [ -f "output/bench/scale_test_real/SCALE_TEST_REPORT.json" ]; then
    echo "   ✅ SCALE_TEST_REPORT.json found!"
    echo ""
    echo "   Analysis output (first 30 lines):"
    if [ -f "/tmp/analysis_output.txt" ]; then
        head -30 /tmp/analysis_output.txt | sed 's/^/   /'
    else
        echo "   (Analysis may still be running...)"
    fi
else
    echo "   ⏳ SCALE_TEST_REPORT.json not yet available"
    echo "   (Scale test still in progress)"
fi

echo ""
echo "📋 Monitor logs:"
if [ -f "/tmp/monitor_output.txt" ]; then
    echo "   Last 3 lines of monitor:"
    tail -3 /tmp/monitor_output.txt | sed 's/^/   /'
fi

echo ""
echo "💡 Tip: Run this script periodically to check progress"
echo "   Or check /tmp/analysis_output.txt when results are ready"
