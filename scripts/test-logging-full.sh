#!/bin/bash

################################################################################
# Mikrom Full Logging Test - Tests all instrumented components
################################################################################

set -euo pipefail

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
LOG_FILE="/tmp/mikrom_full_logging_test.log"
WORKER_LOG_FILE="/tmp/mikrom_worker_logging_test.log"
ANALYSIS_SCRIPT="/tmp/analyze_logs.py"

# Colors
RED=$(tput setaf 1 2>/dev/null || echo '')
GREEN=$(tput setaf 2 2>/dev/null || echo '')
YELLOW=$(tput setaf 3 2>/dev/null || echo '')
BLUE=$(tput setaf 4 2>/dev/null || echo '')
RESET=$(tput sgr0 2>/dev/null || echo '')

# Cleanup old logs
rm -f "$LOG_FILE" "$WORKER_LOG_FILE"

echo "${BLUE}╔════════════════════════════════════════════════════════════════╗${RESET}"
echo "${BLUE}║        Mikrom Full Logging Test - All Components              ║${RESET}"
echo "${BLUE}╚════════════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo "📋 Test Configuration:"
echo "  • API URL: $API_URL"
echo "  • API Log: $LOG_FILE"
echo "  • Worker Log: $WORKER_LOG_FILE"
echo ""

# Function to check service health
check_service() {
    local name=$1
    local url=$2
    
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "  ✅ $name is running"
        return 0
    else
        echo "  ❌ $name is NOT running"
        return 1
    fi
}

# Check prerequisites
echo "🔍 Checking prerequisites..."
check_service "PostgreSQL" "localhost:5432" 2>/dev/null || echo "  ⚠️  PostgreSQL check skipped"
check_service "Redis" "localhost:6379" 2>/dev/null || echo "  ⚠️  Redis check skipped"

# Check if API is already running
if check_service "API Server" "$API_URL/health" 2>/dev/null; then
    echo ""
    echo "⚠️  API server is already running. Using existing instance."
    echo "   Make sure it's logging to: $LOG_FILE"
    NEED_START_API=false
else
    echo "  ℹ️  API server needs to be started"
    NEED_START_API=true
fi

echo ""

# Start API server if needed
if [ "$NEED_START_API" = true ]; then
    echo "🚀 Starting API server with full logging..."
    cd /home/apardo/Work/mikrom/new/mikrom-py
    
    # Set environment to ensure JSON logging
    export LOG_FORMAT=json
    export LOG_LEVEL=INFO
    export OTEL_SERVICE_NAME=mikrom-api
    export OTEL_TRACE_SAMPLE_RATE=1.0
    
    # Start API in background, redirecting output to log file
    nohup uv run uvicorn mikrom.main:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
    API_PID=$!
    
    echo "  • Started API (PID: $API_PID)"
    echo "  • Waiting for API to be ready..."
    
    # Wait for API to be ready (max 30 seconds)
    for i in {1..30}; do
        if curl -sf "$API_URL/health" > /dev/null 2>&1; then
            echo "  ✅ API is ready!"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo "  ❌ API failed to start within 30 seconds"
            cat "$LOG_FILE"
            exit 1
        fi
    done
    echo ""
fi

# Give it a moment to initialize telemetry
sleep 2

echo "📊 Running API endpoint tests..."
echo ""

# Test 1: Health check
echo "1️⃣  Testing health endpoint..."
curl -s "$API_URL/health" | jq . || echo "Failed"
sleep 1

# Test 2: Root endpoint
echo ""
echo "2️⃣  Testing root endpoint..."
curl -s "$API_URL/" | jq . || echo "Failed"
sleep 1

# Test 3: List VMs (triggers DB query)
echo ""
echo "3️⃣  Testing VM list endpoint (triggers DB query)..."
curl -s -X GET "$API_URL/api/v1/vms?skip=0&limit=10" \
    -H "Content-Type: application/json" | jq . || echo "Failed"
sleep 1

# Test 4: Create VM (triggers full workflow: endpoint → service → worker → clients)
echo ""
echo "4️⃣  Testing VM creation (full workflow)..."
echo "   This will trigger: API → Service → Background Task → Firecracker Client → IPPool Client"

VM_NAME="logging-test-vm-$(date +%s)"
CREATE_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/vms" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"$VM_NAME\",
        \"vcpu_count\": 1,
        \"memory_mb\": 256,
        \"description\": \"Test VM for logging validation\"
    }")

echo "$CREATE_RESPONSE" | jq .

# Extract VM ID if created
VM_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id // empty')
if [ -n "$VM_ID" ]; then
    echo ""
    echo "   ✅ VM created with ID: $VM_ID"
    echo "   📝 Background task should be running now..."
    echo "   ⏳ Waiting 5 seconds for worker to process..."
    sleep 5
    
    # Test 5: Get VM details
    echo ""
    echo "5️⃣  Testing VM details endpoint..."
    curl -s "$API_URL/api/v1/vms/$VM_ID" | jq . || echo "Failed"
    sleep 1
else
    echo "   ⚠️  VM creation returned unexpected response (might be expected if Firecracker not configured)"
fi

# Test 6: Trigger an error for error logging
echo ""
echo "6️⃣  Testing error logging (accessing non-existent VM)..."
curl -s "$API_URL/api/v1/vms/99999" | jq . || echo "Expected 404 error"
sleep 1

echo ""
echo "✅ API tests complete!"
echo ""
echo "⏳ Waiting a few more seconds for async operations to complete..."
sleep 3

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "📊 ANALYZING LOGS"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Check if log file has content
if [ ! -s "$LOG_FILE" ]; then
    echo "❌ Log file is empty or doesn't exist: $LOG_FILE"
    if [ "$NEED_START_API" = true ] && [ -n "${API_PID:-}" ]; then
        echo "Stopping API server (PID: $API_PID)..."
        kill $API_PID 2>/dev/null || true
    fi
    exit 1
fi

# Show log statistics
echo "📈 Log File Statistics:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL_LINES=$(wc -l < "$LOG_FILE")
JSON_LINES=$(grep -c '^{' "$LOG_FILE" || true)
echo "  • Total lines: $TOTAL_LINES"
echo "  • JSON log lines: $JSON_LINES"
echo "  • Log file size: $(du -h "$LOG_FILE" | cut -f1)"
echo ""

# Extract and count JSON logs by logger
echo "📊 Logs by Component:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
grep '^{' "$LOG_FILE" | jq -r '.logger' | sort | uniq -c | while read count logger; do
    printf "  • %-40s %5d logs\n" "$logger" "$count"
done
echo ""

# Count logs with trace context
echo "🔗 Trace Context Coverage:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
LOGS_WITH_TRACE=$(grep '^{' "$LOG_FILE" | grep -c '"trace_id"' || true)
TRACE_PERCENTAGE=$(awk "BEGIN {printf \"%.1f\", ($LOGS_WITH_TRACE / $JSON_LINES) * 100}")
echo "  • Logs with trace_id: $LOGS_WITH_TRACE / $JSON_LINES ($TRACE_PERCENTAGE%)"
echo ""

# Count logs by level
echo "📊 Logs by Level:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
grep '^{' "$LOG_FILE" | jq -r '.level' | sort | uniq -c | while read count level; do
    case $level in
        ERROR) color=$RED ;;
        WARNING) color=$YELLOW ;;
        INFO) color=$GREEN ;;
        *) color=$RESET ;;
    esac
    printf "  • ${color}%-10s${RESET} %5d logs\n" "$level" "$count"
done
echo ""

# Show sample logs from each component
echo "📝 Sample Logs by Component:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Middleware logs
echo "${BLUE}▸ Middleware Logs (HTTP requests):${RESET}"
grep '^{' "$LOG_FILE" | jq 'select(.logger == "mikrom.middleware.logging")' | head -2 | jq -C .
echo ""

# Endpoint logs
echo "${BLUE}▸ VM Endpoint Logs:${RESET}"
grep '^{' "$LOG_FILE" | jq 'select(.logger == "mikrom.api.v1.endpoints.vms")' | head -2 | jq -C .
echo ""

# Service logs
echo "${BLUE}▸ VM Service Logs:${RESET}"
grep '^{' "$LOG_FILE" | jq 'select(.logger == "mikrom.services.vm_service")' | head -2 | jq -C .
echo ""

# Worker logs
echo "${BLUE}▸ Worker Task Logs:${RESET}"
grep '^{' "$LOG_FILE" | jq 'select(.logger == "mikrom.worker.tasks")' | head -2 | jq -C .
echo ""

# Client logs
echo "${BLUE}▸ Firecracker Client Logs:${RESET}"
grep '^{' "$LOG_FILE" | jq 'select(.logger == "mikrom.clients.firecracker")' | head -2 | jq -C .
echo ""

echo "${BLUE}▸ IPPool Client Logs:${RESET}"
grep '^{' "$LOG_FILE" | jq 'select(.logger == "mikrom.clients.ippool")' | head -2 | jq -C .
echo ""

# Check for errors
ERROR_COUNT=$(grep '^{' "$LOG_FILE" | jq -r 'select(.level == "ERROR")' | wc -l)
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "${RED}⚠️  Error Logs Found ($ERROR_COUNT):${RESET}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    grep '^{' "$LOG_FILE" | jq -C 'select(.level == "ERROR")' | head -5
    echo ""
fi

# Context propagation check
echo "🔗 Context Propagation Check:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -n "${VM_ID:-}" ]; then
    VM_LOGS=$(grep '^{' "$LOG_FILE" | jq -r "select(.vm_id == \"$VM_ID\")" | wc -l)
    if [ "$VM_LOGS" -gt 0 ]; then
        echo "  ✅ Found $VM_LOGS logs with vm_id=$VM_ID (context propagated!)"
        echo ""
        echo "  Sample log with context:"
        grep '^{' "$LOG_FILE" | jq -C "select(.vm_id == \"$VM_ID\")" | head -1
    else
        echo "  ⚠️  No logs found with vm_id=$VM_ID"
    fi
else
    echo "  ℹ️  No VM created, skipping context propagation check"
fi
echo ""

echo "═══════════════════════════════════════════════════════════════════"
echo "✅ LOGGING TEST COMPLETE"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "📁 Full logs available at:"
echo "   $LOG_FILE"
echo ""
echo "💡 To analyze further:"
echo "   cat $LOG_FILE | grep '^{' | jq ."
echo "   grep '^{' $LOG_FILE | jq 'select(.logger == \"mikrom.worker.tasks\")'"
echo ""

# Cleanup if we started the API
if [ "$NEED_START_API" = true ] && [ -n "${API_PID:-}" ]; then
    echo "🛑 Stopping API server (PID: $API_PID)..."
    kill $API_PID 2>/dev/null || true
    sleep 1
    echo "   ✅ API server stopped"
fi

echo ""
echo "🎉 Test completed successfully!"
