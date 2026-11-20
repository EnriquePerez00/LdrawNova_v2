#!/bin/bash
# Wait for scale test to complete and then analyze results
# This runs in background and doesn't block the tool

OUTPUT_DIR="output/bench/scale_test_real"
REPORT_FILE="$OUTPUT_DIR/SCALE_TEST_REPORT.json"
LOG_FILE="/tmp/wait_and_analyze.log"

{
    echo "[$(date)] Waiting for scale test to complete..."
    echo "[$(date)] Monitoring for SCALE_TEST_REPORT.json..."
    
    # Wait for report to appear (up to 2 hours with 30s polling)
    for i in {1..240}; do
        if [ -f "$REPORT_FILE" ]; then
            echo "[$(date)] ✅ Report found! Running analysis..."
            python3 analyze_scale_test.py > /tmp/analysis_output.txt 2>&1
            echo "[$(date)] ✅ Analysis complete. Results saved to /tmp/analysis_output.txt"
            cat /tmp/analysis_output.txt
            break
        fi
        
        COMPLETED=$(find "$OUTPUT_DIR" -name 'e2e_result.json' 2>/dev/null | wc -l)
        echo "[$(date)] Progress: $COMPLETED/10 e2e_result.json files"
        
        if [ $((i % 10)) -eq 0 ]; then
            echo "[$(date)] Still waiting... ($((i*30)) seconds elapsed)"
        fi
        
        sleep 30
    done
    
    if [ ! -f "$REPORT_FILE" ]; then
        echo "[$(date)] ❌ Timeout waiting for report"
        echo "[$(date)] Completed files so far:"
        find "$OUTPUT_DIR" -name 'e2e_result.json' | wc -l
    fi
} 2>&1 | tee -a "$LOG_FILE"

echo "[$(date)] Wait-and-analyze finished" >> "$LOG_FILE"
