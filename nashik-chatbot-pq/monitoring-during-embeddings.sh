#!/bin/bash
# ============================================================================
# Real-time monitoring script for embedding creation
# Run this BEFORE starting the embedding process
# ============================================================================

echo "🔍 Starting real-time resource monitoring..."
echo "Press Ctrl+C to stop monitoring"
echo ""

# Create log directory
mkdir -p logs/monitoring

# Timestamp for logs
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/monitoring/resources_${TIMESTAMP}.log"

echo "📊 Logging to: $LOG_FILE"
echo ""

# Function to log with timestamp
log_stats() {
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG_FILE"

    # Docker stats (no stream, one snapshot)
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    # VM memory
    echo "VM Memory:" >> "$LOG_FILE"
    free -h >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    # Check for OOM in last 10 seconds
    echo "Checking for OOM kills..." >> "$LOG_FILE"
    docker logs --since 10s traceability-app 2>&1 | grep -i "oom\|killed\|memory" >> "$LOG_FILE" 2>&1
    docker logs --since 10s traceability-opensearch 2>&1 | grep -i "oom\|killed\|memory" >> "$LOG_FILE" 2>&1
    echo "" >> "$LOG_FILE"
    echo "----------------------------------------" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
}

# Monitor in a loop (every 10 seconds)
while true; do
    clear

    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           REAL-TIME RESOURCE MONITORING (Embedding)             ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""

    # Current time
    echo "⏰ Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Docker container stats
    echo "🐳 Container Resources:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
    echo ""

    # VM memory
    echo "💻 VM Memory:"
    free -h | grep -E "^Mem|^Swap"
    echo ""

    # Check if any container is near limit
    echo "⚠️  Alert Status:"

    # App memory check (> 90% = warning)
    APP_MEM=$(docker stats --no-stream --format "{{.MemPerc}}" traceability-app | sed 's/%//')
    if (( $(echo "$APP_MEM > 90" | bc -l) )); then
        echo "  🔴 App memory HIGH: ${APP_MEM}% (>90%)"
    elif (( $(echo "$APP_MEM > 75" | bc -l) )); then
        echo "  🟡 App memory elevated: ${APP_MEM}% (>75%)"
    else
        echo "  🟢 App memory OK: ${APP_MEM}%"
    fi

    # OpenSearch memory check
    OS_MEM=$(docker stats --no-stream --format "{{.MemPerc}}" traceability-opensearch | sed 's/%//')
    if (( $(echo "$OS_MEM > 90" | bc -l) )); then
        echo "  🔴 OpenSearch memory HIGH: ${OS_MEM}% (>90%)"
    elif (( $(echo "$OS_MEM > 75" | bc -l) )); then
        echo "  🟡 OpenSearch memory elevated: ${OS_MEM}% (>75%)"
    else
        echo "  🟢 OpenSearch memory OK: ${OS_MEM}%"
    fi

    # Recent OOM errors
    OOM_APP=$(docker logs --since 10s traceability-app 2>&1 | grep -i "oom\|killed" | wc -l)
    OOM_OS=$(docker logs --since 10s traceability-opensearch 2>&1 | grep -i "oom\|killed" | wc -l)

    if [ "$OOM_APP" -gt 0 ] || [ "$OOM_OS" -gt 0 ]; then
        echo "  🔴 OOM DETECTED! Check logs immediately"
    else
        echo "  🟢 No OOM errors detected"
    fi

    echo ""
    echo "📝 Logging to: $LOG_FILE"
    echo "🔄 Refreshing every 10 seconds... (Ctrl+C to stop)"
    echo ""

    # Log to file
    log_stats

    # Wait 10 seconds
    sleep 10
done
