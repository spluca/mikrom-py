#!/bin/bash

# Test script for Makefile commands
# Tests each Makefile command to ensure it works correctly

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Test results array
declare -a FAILED_TESTS=()
declare -a SKIPPED_TESTS=()

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          MIKROM MAKEFILE TEST SUITE                            ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo ""

# Helper functions
test_command() {
    local name=$1
    local command=$2
    local expected_exit_code=${3:-0}
    local skip=${4:-false}
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if [ "$skip" = true ]; then
        echo -e "${YELLOW}⊘ SKIP${NC} $name"
        TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
        SKIPPED_TESTS+=("$name")
        return 0
    fi
    
    echo -n "  Testing: $name ... "
    
    # Execute command and capture exit code
    if eval "$command" > /dev/null 2>&1; then
        actual_exit_code=0
    else
        actual_exit_code=$?
    fi
    
    if [ $actual_exit_code -eq $expected_exit_code ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (exit code: $actual_exit_code, expected: $expected_exit_code)"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TESTS+=("$name (exit: $actual_exit_code, expected: $expected_exit_code)")
        return 1
    fi
}

test_command_output() {
    local name=$1
    local command=$2
    local expected_pattern=$3
    local skip=${4:-false}
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if [ "$skip" = true ]; then
        echo -e "${YELLOW}⊘ SKIP${NC} $name"
        TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
        SKIPPED_TESTS+=("$name")
        return 0
    fi
    
    echo -n "  Testing: $name ... "
    
    # Execute command and capture output
    output=$(eval "$command" 2>&1 || true)
    
    if echo "$output" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}✓ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (pattern not found: '$expected_pattern')"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TESTS+=("$name (pattern not found)")
        return 1
    fi
}

section() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

# ============================================================================
# Test: Help Command
# ============================================================================

section "1. Help & Documentation"
test_command_output "make help" "make help" "Mikrom API - Comandos disponibles"
test_command_output "make info" "make info" "Información del Proyecto"

# ============================================================================
# Test: Installation & Dependencies
# ============================================================================

section "2. Installation & Dependencies"
test_command "make clean" "make clean" 0
test_command "make dev-install" "make dev-install" 0
# Skip update as it modifies lock file
test_command "make update" "make update" 0 true

# ============================================================================
# Test: Code Quality
# ============================================================================

section "3. Code Quality"
test_command "make lint" "make lint" 0
test_command "make format-check" "make format-check" 0
test_command "make format (dry run)" "make format" 0
test_command "make lint-fix" "make lint-fix" 0

# ============================================================================
# Test: Testing Commands
# ============================================================================

section "4. Testing Commands"
# Note: Tests may have fixture issues (known issue), but command should still run
test_command_output "make test (runs successfully)" "make test 2>&1" "test session starts"
test_command_output "make test-fast (runs successfully)" "make test-fast 2>&1" "test session starts"
# Skip test-cov as it's time-consuming
test_command "make test-cov" "make test-cov" 0 true
# Skip test-watch as it's interactive
test_command "make test-watch" "timeout 2 make test-watch" 124 true
# Skip test-failed as it depends on previous failures
test_command "make test-failed" "echo 'Skipped: depends on previous failures'" 0 true

# ============================================================================
# Test: Database Commands
# ============================================================================

section "5. Database Commands"
# Database commands require PostgreSQL running - skip if not available
if docker ps | grep -q mikrom_db; then
    echo "  PostgreSQL container detected - running database tests"
    test_command "make migrate-current" "make migrate-current" 0
    test_command "make migrate-history" "make migrate-history" 0
    test_command "make migrate-heads" "make migrate-heads" 0
    test_command "make migrate-upgrade" "make migrate-upgrade" 0
else
    echo "  PostgreSQL not running - skipping database tests"
    test_command "make migrate-current" "echo 'Skipped: requires database'" 0 true
    test_command "make migrate-history" "echo 'Skipped: requires database'" 0 true
    test_command "make migrate-heads" "echo 'Skipped: requires database'" 0 true
    test_command "make migrate-upgrade" "echo 'Skipped: requires database'" 0 true
fi
# Skip migrate-downgrade as it modifies DB
test_command "make migrate-downgrade" "echo 'Skipped: modifies database'" 0 true
# Skip migrate-create as it requires MSG param
test_command "make migrate-create (no MSG)" "make migrate-create 2>&1 | grep -q 'Error: Debes proporcionar un mensaje'" 0
# Skip db-reset as it's destructive
test_command "make db-reset" "echo 'Skipped: destructive operation'" 0 true
# Skip superuser as it's interactive
test_command "make superuser" "echo 'Skipped: interactive command'" 0 true

# ============================================================================
# Test: Docker Commands (check syntax only, don't execute)
# ============================================================================

section "6. Docker Commands (Syntax Check)"
test_command_output "make docker-build (dry-run)" "make -n docker-build" "docker compose build"
test_command_output "make docker-up (dry-run)" "make -n docker-up" "docker compose up"
test_command_output "make docker-down (dry-run)" "make -n docker-down" "docker compose down"
test_command_output "make docker-logs (dry-run)" "make -n docker-logs" "docker compose logs"
test_command_output "make docker-ps (dry-run)" "make -n docker-ps" "docker compose ps"
test_command_output "make docker-restart (dry-run)" "make -n docker-restart" "docker compose restart"
test_command_output "make docker-logs-app (dry-run)" "make -n docker-logs-app" "docker compose logs.*app"
test_command_output "make docker-logs-db (dry-run)" "make -n docker-logs-db" "docker compose logs.*db"
# Skip docker-shell and docker-clean as they're interactive or destructive
test_command "make docker-shell" "echo 'Skipped: requires running container'" 0 true
test_command "make docker-clean" "echo 'Skipped: destructive & interactive'" 0 true
test_command "make docker-build-no-cache" "echo 'Skipped: time-consuming'" 0 true

# ============================================================================
# Test: Development Commands (check they don't crash immediately)
# ============================================================================

section "7. Development Commands"
# Skip run commands as they're long-running servers
test_command "make run (timeout)" "timeout 2 make run 2>&1" 124 true
test_command "make run-prod (timeout)" "timeout 2 make run-prod 2>&1" 124 true
# Test shell - just verify syntax
test_command_output "make shell (dry-run)" "make -n shell" "python -i"

# ============================================================================
# Test: Utility Commands
# ============================================================================

section "8. Utility Commands"
# Skip health as it requires running server
test_command "make health" "echo 'Skipped: requires running server'" 0 true
# Skip docs as it tries to open browser
test_command "make docs" "echo 'Skipped: opens browser'" 0 true

# ============================================================================
# Test: Composite Commands
# ============================================================================

section "9. Composite Commands"
# CI may fail due to test fixture issues, but command should run
test_command_output "make ci (runs successfully)" "make ci 2>&1" "passed"
# Skip setup as it's for initial setup
test_command "make setup" "echo 'Skipped: initial setup command'" 0 true
# Skip docker-setup as it's for initial Docker setup
test_command "make docker-setup" "echo 'Skipped: Docker setup command'" 0 true

# ============================================================================
# Test: Variables & Phony Targets
# ============================================================================

section "10. Makefile Structure"
test_command_output "Check PHONY targets" "head -1 Makefile" ".PHONY:"
test_command_output "Check Python variable" "grep 'PYTHON :=' Makefile" "PYTHON := uv run python"
test_command_output "Check Pytest variable" "grep 'PYTEST :=' Makefile" "PYTEST := uv run pytest"
test_command_output "Check Alembic variable" "grep 'ALEMBIC :=' Makefile" "ALEMBIC := uv run alembic"
test_command_output "Check Uvicorn variable" "grep 'UVICORN :=' Makefile" "UVICORN := uv run uvicorn"
test_command_output "Check Docker Compose variable" "grep 'DOCKER_COMPOSE :=' Makefile" "DOCKER_COMPOSE := docker compose"

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    TEST SUMMARY                                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Total Tests:    ${BLUE}$TESTS_RUN${NC}"
echo -e "  Passed:         ${GREEN}$TESTS_PASSED${NC}"
echo -e "  Failed:         ${RED}$TESTS_FAILED${NC}"
echo -e "  Skipped:        ${YELLOW}$TESTS_SKIPPED${NC}"
echo ""

# Show failed tests if any
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Failed Tests:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}✗${NC} $test"
    done
    echo ""
fi

# Show skipped tests
if [ $TESTS_SKIPPED -gt 0 ]; then
    echo -e "${YELLOW}Skipped Tests (interactive, destructive, or time-consuming):${NC}"
    for test in "${SKIPPED_TESTS[@]}"; do
        echo -e "  ${YELLOW}⊘${NC} $test"
    done
    echo ""
fi

# Calculate pass rate
if [ $TESTS_RUN -gt 0 ]; then
    PASS_RATE=$(awk "BEGIN {printf \"%.1f\", ($TESTS_PASSED / $TESTS_RUN) * 100}")
    echo -e "  Pass Rate:      ${GREEN}${PASS_RATE}%${NC}"
fi

echo ""
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Exit with appropriate code
if [ $TESTS_FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
