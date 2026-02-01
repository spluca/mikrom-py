#!/bin/bash
#
# Script de pruebas completas de logging para mikrom-py
# Verifica que todos los logs se generen correctamente con estructura JSON
#

set -e

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Archivos de logs
API_LOG="/tmp/mikrom_api_test.log"
WORKER_LOG="/tmp/mikrom_worker_test.log"
TEST_RESULTS="/tmp/mikrom_test_results.txt"

# Limpiar logs anteriores
rm -f "$API_LOG" "$WORKER_LOG" "$TEST_RESULTS"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Mikrom-py Logging System - Comprehensive Test Suite          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Función para verificar logs JSON
check_json_logs() {
    local log_file=$1
    local description=$2
    local filter=$3
    
    echo -e "${YELLOW}➜ Verificando: $description${NC}"
    
    if [ ! -f "$log_file" ]; then
        echo -e "${RED}  ✗ Archivo de log no existe: $log_file${NC}"
        return 1
    fi
    
    # Contar líneas JSON
    local json_lines=$(grep -E "^\{" "$log_file" | wc -l)
    echo -e "  ${GREEN}✓${NC} Encontradas $json_lines líneas JSON"
    
    # Verificar estructura JSON válida
    local invalid_json=$(grep -E "^\{" "$log_file" | while read line; do
        echo "$line" | python3 -m json.tool > /dev/null 2>&1 || echo "invalid"
    done | grep -c "invalid" || true)
    
    if [ "$invalid_json" -gt 0 ]; then
        echo -e "  ${RED}✗ Encontrados $invalid_json JSON inválidos${NC}"
        return 1
    else
        echo -e "  ${GREEN}✓${NC} Todos los JSON son válidos"
    fi
    
    # Verificar campos requeridos
    local fields=("timestamp" "level" "logger" "message")
    for field in "${fields[@]}"; do
        local count=$(grep -E "^\{" "$log_file" | grep -c "\"$field\":" || true)
        if [ "$count" -eq 0 ]; then
            echo -e "  ${RED}✗ Campo '$field' no encontrado en logs${NC}"
        else
            echo -e "  ${GREEN}✓${NC} Campo '$field' presente ($count veces)"
        fi
    done
    
    # Verificar trace_id y span_id
    local trace_count=$(grep -E "^\{" "$log_file" | grep -c "\"trace_id\":" || true)
    if [ "$trace_count" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} trace_id presente ($trace_count logs con trace)"
    fi
    
    local span_count=$(grep -E "^\{" "$log_file" | grep -c "\"span_id\":" || true)
    if [ "$span_count" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} span_id presente ($span_count logs con span)"
    fi
    
    echo ""
}

# Función para buscar patrones específicos en logs
check_log_pattern() {
    local log_file=$1
    local pattern=$2
    local description=$3
    
    local count=$(grep -E "^\{" "$log_file" | grep -c "$pattern" || true)
    if [ "$count" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} $description ($count ocurrencias)"
        
        # Mostrar ejemplo
        local example=$(grep -E "^\{" "$log_file" | grep "$pattern" | head -1)
        echo "    Ejemplo: $(echo $example | python3 -m json.tool 2>/dev/null | head -5 | tail -4 || echo $example | cut -c1-80)"
    else
        echo -e "  ${YELLOW}⚠${NC} $description (0 ocurrencias)"
    fi
}

# Iniciar API en background
echo -e "${BLUE}[1/7] Iniciando API servidor...${NC}"
cd /home/apardo/Work/mikrom/new/mikrom-py
nohup make run > "$API_LOG" 2>&1 &
API_PID=$!
sleep 5

# Verificar que el API esté respondiendo
if ! curl -s http://localhost:8000/ > /dev/null; then
    echo -e "${RED}✗ API no está respondiendo${NC}"
    kill $API_PID 2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✓ API servidor iniciado (PID: $API_PID)${NC}"
echo ""

# Test 1: Logs de inicio
echo -e "${BLUE}[2/7] Test 1: Logs de Inicio del Sistema${NC}"
sleep 2
check_json_logs "$API_LOG" "Logs de inicio del sistema" ""
check_log_pattern "$API_LOG" "OpenTelemetry initialized" "Inicialización de OpenTelemetry"
check_log_pattern "$API_LOG" "Starting Mikrom API" "Inicio de API"
check_log_pattern "$API_LOG" "FastAPI instrumented" "Instrumentación de FastAPI"
echo ""

# Test 2: HTTP Request Logging
echo -e "${BLUE}[3/7] Test 2: Logs de HTTP Requests${NC}"
echo "Realizando request HTTP GET /"
curl -s -H "X-Request-ID: test-req-001" http://localhost:8000/ > /dev/null
sleep 1

echo "Realizando request HTTP GET /api/v1/health"
curl -s http://localhost:8000/api/v1/health > /dev/null
sleep 1

check_log_pattern "$API_LOG" "Request started" "Inicio de request HTTP"
check_log_pattern "$API_LOG" "Request completed" "Completado de request HTTP"
check_log_pattern "$API_LOG" "request_id" "Context: request_id"
check_log_pattern "$API_LOG" "duration_ms" "Métricas de duración"
check_log_pattern "$API_LOG" "method.*GET" "HTTP Method GET"
check_log_pattern "$API_LOG" "status_code.*200" "HTTP Status 200"
echo ""

# Test 3: Authentication & User Context
echo -e "${BLUE}[4/7] Test 3: Autenticación y Contexto de Usuario${NC}"
echo "Obteniendo token de autenticación..."

# Login para obtener token
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin&password=admin123")

TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
    echo -e "${YELLOW}⚠ No se pudo obtener token (probablemente no hay usuarios)${NC}"
    echo "Intentando crear usuario admin..."
    
    # Crear usuario admin si no existe
    curl -s -X POST http://localhost:8000/api/v1/users/ \
        -H "Content-Type: application/json" \
        -d '{
            "username": "admin",
            "email": "admin@example.com",
            "password": "admin123",
            "is_superuser": true
        }' > /dev/null 2>&1 || true
    
    sleep 1
    
    # Intentar login nuevamente
    LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=admin&password=admin123")
    
    TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || echo "")
fi

if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✓ Token obtenido${NC}"
    
    # Hacer request autenticado
    curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/vms/ > /dev/null
    sleep 1
    
    check_log_pattern "$API_LOG" "user_id" "Context: user_id en logs"
    check_log_pattern "$API_LOG" "user_name" "Context: user_name en logs"
else
    echo -e "${YELLOW}⚠ No se pudo obtener token - saltando test de contexto de usuario${NC}"
fi
echo ""

# Test 4: VM Operations Logging
echo -e "${BLUE}[5/7] Test 4: Logs de Operaciones de VM${NC}"

if [ -n "$TOKEN" ]; then
    echo "Intentando crear VM..."
    
    VM_CREATE_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/vms/ \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "test-logging-vm",
            "vcpu_count": 1,
            "memory_mb": 256,
            "description": "VM for logging tests"
        }')
    
    VM_ID=$(echo $VM_CREATE_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('vm_id', ''))" 2>/dev/null || echo "")
    
    if [ -n "$VM_ID" ]; then
        echo -e "${GREEN}✓ VM creada: $VM_ID${NC}"
        sleep 2
        
        # Verificar logs de VM
        check_log_pattern "$API_LOG" "Creating VM" "Logs de creación de VM"
        check_log_pattern "$API_LOG" "api.vm.create" "Span de API VM create"
        check_log_pattern "$API_LOG" "VM created successfully" "VM creada exitosamente"
        check_log_pattern "$API_LOG" "vm_id.*$VM_ID" "Context: vm_id en logs"
        check_log_pattern "$API_LOG" "service.vm.create" "Span de servicio VM create"
        check_log_pattern "$API_LOG" "Inserting VM record" "Log de inserción en DB"
        check_log_pattern "$API_LOG" "Queueing VM creation" "Log de encolado de tarea"
        
        # Listar VMs
        echo ""
        echo "Listando VMs..."
        curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/vms/ > /dev/null
        sleep 1
        
        # Obtener VM específica
        echo "Obteniendo detalles de VM..."
        curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/vms/$VM_ID > /dev/null
        sleep 1
        
    else
        echo -e "${YELLOW}⚠ No se pudo crear VM (error esperado si no hay infraestructura)${NC}"
        echo "Response: $VM_CREATE_RESPONSE"
    fi
else
    echo -e "${YELLOW}⚠ Sin token - saltando test de operaciones de VM${NC}"
fi
echo ""

# Test 5: Worker Logs (si está corriendo)
echo -e "${BLUE}[6/7] Test 5: Logs del Worker (Background Tasks)${NC}"

# Iniciar worker temporalmente para capturar logs
echo "Iniciando worker temporalmente..."
timeout 10 make worker > "$WORKER_LOG" 2>&1 &
WORKER_PID=$!
sleep 5

if [ -f "$WORKER_LOG" ]; then
    check_json_logs "$WORKER_LOG" "Logs del worker" ""
    check_log_pattern "$WORKER_LOG" "Starting VM creation background task" "Inicio de tarea de creación"
    check_log_pattern "$WORKER_LOG" "Allocating IP" "Logs de asignación de IP"
    check_log_pattern "$WORKER_LOG" "Starting Firecracker VM" "Logs de inicio de Firecracker"
    check_log_pattern "$WORKER_LOG" "background.create_vm" "Span de background task"
    check_log_pattern "$WORKER_LOG" "vm.allocate_ip" "Span de asignación de IP"
else
    echo -e "${YELLOW}⚠ No hay logs del worker disponibles${NC}"
fi

kill $WORKER_PID 2>/dev/null || true
echo ""

# Test 6: Análisis de Campos Contextuales
echo -e "${BLUE}[7/7] Test 6: Análisis de Campos Contextuales${NC}"

echo "Verificando campos contextuales en logs de API..."

# Extraer todos los logs JSON y analizar campos
python3 << 'PYTHON_SCRIPT'
import json
import sys
from collections import Counter

log_file = "/tmp/mikrom_api_test.log"

# Leer todos los logs JSON
logs = []
with open(log_file, 'r') as f:
    for line in f:
        line = line.strip()
        if line.startswith('{'):
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                pass

if not logs:
    print("  ⚠ No se encontraron logs JSON")
    sys.exit(0)

print(f"  Total de logs JSON analizados: {len(logs)}")
print()

# Análisis de campos
all_fields = Counter()
for log in logs:
    all_fields.update(log.keys())

print("  Campos más comunes:")
for field, count in all_fields.most_common(20):
    percentage = (count / len(logs)) * 100
    print(f"    • {field}: {count} ({percentage:.1f}%)")

print()

# Análisis de trace_id
logs_with_trace = [log for log in logs if 'trace_id' in log]
print(f"  Logs con trace_id: {len(logs_with_trace)} ({len(logs_with_trace)/len(logs)*100:.1f}%)")

# Análisis de context fields
context_fields = ['request_id', 'user_id', 'user_name', 'vm_id', 'action']
print()
print("  Campos de contexto:")
for field in context_fields:
    count = sum(1 for log in logs if field in log)
    if count > 0:
        print(f"    • {field}: {count} logs ({count/len(logs)*100:.1f}%)")

# Análisis de niveles de log
levels = Counter(log.get('level', 'UNKNOWN') for log in logs)
print()
print("  Niveles de log:")
for level, count in levels.most_common():
    print(f"    • {level}: {count}")

# Análisis de loggers
loggers = Counter(log.get('logger', 'UNKNOWN') for log in logs)
print()
print("  Top 10 loggers:")
for logger, count in loggers.most_common(10):
    print(f"    • {logger}: {count}")

# Análisis de acciones
actions = Counter(log.get('action', 'N/A') for log in logs if 'action' in log)
if actions:
    print()
    print("  Acciones registradas:")
    for action, count in actions.most_common():
        print(f"    • {action}: {count}")

# Análisis de duración
logs_with_duration = [log for log in logs if 'duration_ms' in log]
if logs_with_duration:
    durations = [log['duration_ms'] for log in logs_with_duration]
    avg_duration = sum(durations) / len(durations)
    max_duration = max(durations)
    min_duration = min(durations)
    print()
    print(f"  Métricas de duración ({len(logs_with_duration)} logs):")
    print(f"    • Promedio: {avg_duration:.2f} ms")
    print(f"    • Mínimo: {min_duration:.2f} ms")
    print(f"    • Máximo: {max_duration:.2f} ms")

PYTHON_SCRIPT

echo ""

# Mostrar ejemplos de logs por categoría
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Ejemplos de Logs por Categoría${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}➜ Ejemplo: Log de inicio${NC}"
grep -E "^\{" "$API_LOG" | grep "Starting Mikrom API" | head -1 | python3 -m json.tool 2>/dev/null || echo "No encontrado"
echo ""

echo -e "${YELLOW}➜ Ejemplo: Log de HTTP request${NC}"
grep -E "^\{" "$API_LOG" | grep "Request started" | head -1 | python3 -m json.tool 2>/dev/null || echo "No encontrado"
echo ""

echo -e "${YELLOW}➜ Ejemplo: Log con trace_id y span_id${NC}"
grep -E "^\{" "$API_LOG" | grep "trace_id" | head -1 | python3 -m json.tool 2>/dev/null || echo "No encontrado"
echo ""

echo -e "${YELLOW}➜ Ejemplo: Log con contexto de usuario${NC}"
grep -E "^\{" "$API_LOG" | grep "user_id" | head -1 | python3 -m json.tool 2>/dev/null || echo "No encontrado"
echo ""

echo -e "${YELLOW}➜ Ejemplo: Log con duración${NC}"
grep -E "^\{" "$API_LOG" | grep "duration_ms" | head -1 | python3 -m json.tool 2>/dev/null || echo "No encontrado"
echo ""

# Limpiar
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Limpiando...${NC}"
kill $API_PID 2>/dev/null || true
pkill -f "uvicorn mikrom.main" 2>/dev/null || true
sleep 2

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Test Suite Completado                                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Logs guardados en:"
echo "  • API: $API_LOG"
echo "  • Worker: $WORKER_LOG"
echo ""
echo "Para revisar logs completos:"
echo "  cat $API_LOG | grep '^\{' | python3 -m json.tool | less"
echo ""
