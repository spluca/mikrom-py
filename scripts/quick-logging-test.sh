#!/bin/bash

################################################################################
# Quick Logging Validation Test
# Tests the logging system with real API calls
################################################################################

set -euo pipefail

API_LOG="/tmp/mikrom_api_logs.log"
TEST_LOG="/tmp/mikrom_test_output.log"

# Clean up old logs
rm -f "$API_LOG" "$TEST_LOG"

echo "=========================================="
echo "Mikrom Logging Validation Test"
echo "=========================================="
echo ""

# Start API server in background with JSON logging
echo "Starting API server..."
cd /home/apardo/Work/mikrom/new/mikrom-py

export LOG_FORMAT=json
export LOG_LEVEL=INFO  
export OTEL_SERVICE_NAME=mikrom-api
export OTEL_TRACE_SAMPLE_RATE=1.0
export OTEL_EXPORT_CONSOLE=false  # Don't export spans to reduce noise

# Start API and capture logs
uv run uvicorn mikrom.main:app --host 0.0.0.0 --port 8000 --log-level error > "$API_LOG" 2>&1 &
API_PID=$!

echo "  API PID: $API_PID"
echo "  Waiting for API to start..."

# Wait for API to be ready
for i in {1..30}; do
    if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
        echo "  ✅ API is ready!"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "  ❌ API failed to start"
        kill $API_PID 2>/dev/null || true
        exit 1
    fi
done

sleep 2  # Let it stabilize

echo ""
echo "Running test requests..."
echo "=========================================="

# Test 1: Root endpoint
echo ""
echo "1. GET /"
curl -s http://localhost:8000/ > /dev/null
sleep 0.5

# Test 2: List VMs
echo "2. GET /api/v1/vms"
curl -s http://localhost:8000/api/v1/vms > /dev/null
sleep 0.5

# Test 3: Get non-existent VM (error case)
echo "3. GET /api/v1/vms/99999 (error test)"
curl -s http://localhost:8000/api/v1/vms/99999 > /dev/null
sleep 0.5

# Test 4: Create VM (will trigger full workflow if possible)
echo "4. POST /api/v1/vms (VM creation)"
VM_NAME="test-logging-$(date +%s)"
curl -s -X POST http://localhost:8000/api/v1/vms \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$VM_NAME\", \"vcpu_count\": 1, \"memory_mb\": 256}" > /dev/null
sleep 2  # Give worker time to process

echo ""
echo "✅ Tests complete!"
echo ""

# Stop API
echo "Stopping API server..."
kill $API_PID 2>/dev/null || true
wait $API_PID 2>/dev/null || true
sleep 1

echo ""
echo "=========================================="
echo "ANALYZING LOGS"
echo "=========================================="
echo ""

# Extract only JSON logs
JSON_LOGS=$(grep '^{' "$API_LOG" || echo "")

if [ -z "$JSON_LOGS" ]; then
    echo "❌ No JSON logs found!"
    echo ""
    echo "Raw log file content:"
    cat "$API_LOG"
    exit 1
fi

# Count logs
TOTAL_JSON=$(echo "$JSON_LOGS" | wc -l)
echo "📊 Total JSON log entries: $TOTAL_JSON"
echo ""

# Analyze by logger
echo "📋 Logs by Component:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$JSON_LOGS" | jq -r '.logger' | sort | uniq -c | sort -rn | while read count logger; do
    printf "  %-50s %5d\n" "$logger" "$count"
done
echo ""

# Count logs with trace IDs
LOGS_WITH_TRACE=$(echo "$JSON_LOGS" | jq -r 'select(.trace_id) | .trace_id' | wc -l)
TRACE_PCT=$(awk "BEGIN {printf \"%.1f\", ($LOGS_WITH_TRACE / $TOTAL_JSON) * 100}")
echo "🔗 Trace Coverage: $LOGS_WITH_TRACE / $TOTAL_JSON ($TRACE_PCT%)"
echo ""

# Count by log level
echo "📊 Logs by Level:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$JSON_LOGS" | jq -r '.level' | sort | uniq -c | sort -rn | while read count level; do
    printf "  %-10s %5d\n" "$level" "$count"
done
echo ""

# Show sample logs from each component
echo "📝 Sample Logs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "▸ Middleware (HTTP requests):"
echo "$JSON_LOGS" | jq -C 'select(.logger == "mikrom.middleware.logging")' | head -2
echo ""

echo "▸ VM Endpoints:"
echo "$JSON_LOGS" | jq -C 'select(.logger == "mikrom.api.v1.endpoints.vms")' | head -2 || echo "  (no logs)"
echo ""

echo "▸ VM Service:"
echo "$JSON_LOGS" | jq -C 'select(.logger == "mikrom.services.vm_service")' | head -2 || echo "  (no logs)"
echo ""

echo "▸ Background Tasks:"
echo "$JSON_LOGS" | jq -C 'select(.logger == "mikrom.worker.tasks")' | head -2 || echo "  (no logs)"
echo ""

# Check for errors
ERROR_COUNT=$(echo "$JSON_LOGS" | jq -r 'select(.level == "ERROR")' | wc -l)
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "⚠️  Errors Found ($ERROR_COUNT):"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$JSON_LOGS" | jq -C 'select(.level == "ERROR")' | head -3
    echo ""
fi

echo "=========================================="
echo "✅ TEST COMPLETE"
echo "=========================================="
echo ""
echo "Full logs available at: $API_LOG"
echo ""
echo "To explore logs further:"
echo "  grep '^{' $API_LOG | jq ."
echo "  grep '^{' $API_LOG | jq 'select(.logger == \"mikrom.worker.tasks\")'"
echo ""
