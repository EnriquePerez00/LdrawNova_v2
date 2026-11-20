#!/bin/bash
# Monitor scale_test_intermediate.py progress without blocking

OUTPUT_DIR="output/bench/scale_test_real"
EXPECTED=10  # 5 sets × 2 modes (baseline + learning)
LOG_FILE="/tmp/scale_test_monitor.log"

echo "[$(date)] Starting monitor..." > "$LOG_FILE"

while true; do
    COMPLETED=$(find "$OUTPUT_DIR" -name 'e2e_result.json' 2>/dev/null | wc -l)
    RUNNING=$(pgrep -f 'harness_e2e_real|scale_test_intermediate' | wc -l)
    
    echo "[$(date)] Progress: $COMPLETED/$EXPECTED completed, $RUNNING processes active" | tee -a "$LOG_FILE"
    
    if [ "$COMPLETED" -ge "$EXPECTED" ] || [ "$RUNNING" -eq 0 ]; then
        echo "[$(date)] Done! Completed: $COMPLETED/$EXPECTED" | tee -a "$LOG_FILE"
        break
    fi
    
    sleep 30
done

echo "[$(date)] Monitor finished" >> "$LOG_FILE"
