#!/bin/bash

################################################################################
# Mikrom VM Lifecycle Test Script
# 
# Este script prueba el ciclo de vida completo de una VM en mikrom-py:
# 1. Autenticación
# 2. Creación de VM
# 3. Monitoreo de provisioning
# 4. Verificación de VM running
# 5. Actualización de metadata
# 6. Eliminación de VM
#
# Autor: Mikrom Platform Team
# Fecha: $(date +%Y-%m-%d)
################################################################################

set -euo pipefail  # Exit on error, undefined vars, pipe failures

################################################################################
# CONFIGURACIÓN - Editar estas variables según tu entorno
################################################################################

# API Configuration
API_URL="${API_URL:-http://localhost:8000}"
API_USERNAME="${API_USERNAME:-admin}"
API_PASSWORD="${API_PASSWORD:-admin123}"

# VM Configuration
VM_NAME_PREFIX="${VM_NAME_PREFIX:-test-vm}"
VM_NAME="${VM_NAME:-${VM_NAME_PREFIX}-$(date +%s)}"
VM_VCPU_COUNT="${VM_VCPU_COUNT:-1}"
VM_MEMORY_MB="${VM_MEMORY_MB:-256}"
VM_DESCRIPTION="${VM_DESCRIPTION:-Test VM created by lifecycle script at $(date '+%Y-%m-%d %H:%M:%S')}"

# Timing Configuration
MAX_WAIT_TIME="${MAX_WAIT_TIME:-120}"  # Max seconds to wait for VM to be running
POLL_INTERVAL="${POLL_INTERVAL:-3}"     # Seconds between status checks
DELETE_WAIT_TIME="${DELETE_WAIT_TIME:-60}"  # Max seconds to wait for VM deletion

# Test Configuration
VERBOSE="${VERBOSE:-false}"  # Set to 'true' for detailed output

################################################################################
# COLORES PARA OUTPUT
################################################################################

# Check if terminal supports colors
if [[ -t 1 ]] && command -v tput &> /dev/null && tput colors &> /dev/null; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4)
    MAGENTA=$(tput setaf 5)
    CYAN=$(tput setaf 6)
    BOLD=$(tput bold)
    RESET=$(tput sgr0)
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    MAGENTA=''
    CYAN=''
    BOLD=''
    RESET=''
fi

################################################################################
# VARIABLES GLOBALES
################################################################################

ACCESS_TOKEN=""
VM_ID=""
VM_DB_ID=""
START_TIME=$(date +%s)
CLEANUP_NEEDED=false
STATES_VISITED=()

# Test results tracking
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0

################################################################################
# FUNCIONES DE OUTPUT
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}╔════════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BLUE}${BOLD}║$(printf '%64s' '' | tr ' ' ' ')║${RESET}"
    local text="$1"
    local padding=$(( (64 - ${#text}) / 2 ))
    printf "${BLUE}${BOLD}║%*s%s%*s║${RESET}\n" $padding "" "$text" $((64 - ${#text} - padding)) ""
    echo -e "${BLUE}${BOLD}║$(printf '%64s' '' | tr ' ' ' ')║${RESET}"
    echo -e "${BLUE}${BOLD}╚════════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${CYAN}${BOLD}[${1}]${RESET} ${2}"
}

print_success() {
    echo -e "  ${GREEN}✓${RESET} $1"
}

print_error() {
    echo -e "  ${RED}✗${RESET} $1"
}

print_info() {
    echo -e "  ${BLUE}→${RESET} $1"
}

print_warning() {
    echo -e "  ${YELLOW}⚠${RESET} $1"
}

print_progress() {
    echo -e "  ${YELLOW}⏳${RESET} $1"
}

print_verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${MAGENTA}[VERBOSE]${RESET} $1"
    fi
}

################################################################################
# FUNCIONES DE UTILIDAD
################################################################################

# Increment test counter
test_count() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

# Record test pass
test_pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

# Record test fail and exit
test_fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    print_error "$1"
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Get elapsed time since start
get_elapsed_time() {
    local current=$(date +%s)
    echo $((current - START_TIME))
}

# Format seconds to human readable
format_time() {
    local seconds=$1
    if [[ $seconds -lt 60 ]]; then
        echo "${seconds}s"
    else
        local minutes=$((seconds / 60))
        local secs=$((seconds % 60))
        echo "${minutes}m ${secs}s"
    fi
}

# Add state to visited states if not already there
track_state() {
    local state="$1"
    if [[ ! " ${STATES_VISITED[@]} " =~ " ${state} " ]]; then
        STATES_VISITED+=("$state")
    fi
}

################################################################################
# FUNCIONES HTTP
################################################################################

# Make HTTP GET request
http_get() {
    local url="$1"
    
    print_verbose "GET $url"
    
    local response
    local http_code
    
    if [[ -n "${ACCESS_TOKEN}" ]]; then
        response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer ${ACCESS_TOKEN}" "$url")
    else
        response=$(curl -s -w "\n%{http_code}" "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    print_verbose "HTTP $http_code"
    print_verbose "Response: $body"
    
    if [[ ! "$http_code" =~ ^2[0-9]{2}$ ]]; then
        echo "ERROR: HTTP $http_code - $body" >&2
        return 1
    fi
    
    echo "$body"
}

# Make HTTP POST request
http_post() {
    local url="$1"
    local data="$2"
    local content_type="${3:-application/json}"
    
    print_verbose "POST $url"
    print_verbose "Data: $data"
    
    local response
    local http_code
    
    if [[ -n "${ACCESS_TOKEN}" ]]; then
        response=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Content-Type: $content_type" \
            -H "Authorization: Bearer ${ACCESS_TOKEN}" \
            -d "$data" \
            "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Content-Type: $content_type" \
            -d "$data" \
            "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    print_verbose "HTTP $http_code"
    print_verbose "Response: $body"
    
    if [[ ! "$http_code" =~ ^2[0-9]{2}$ ]]; then
        echo "ERROR: HTTP $http_code - $body" >&2
        return 1
    fi
    
    echo "$body"
}

# Make HTTP PATCH request
http_patch() {
    local url="$1"
    local data="$2"
    
    print_verbose "PATCH $url"
    print_verbose "Data: $data"
    
    local response
    local http_code
    
    if [[ -n "${ACCESS_TOKEN}" ]]; then
        response=$(curl -s -w "\n%{http_code}" -X PATCH \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer ${ACCESS_TOKEN}" \
            -d "$data" \
            "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X PATCH \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    print_verbose "HTTP $http_code"
    print_verbose "Response: $body"
    
    if [[ ! "$http_code" =~ ^2[0-9]{2}$ ]]; then
        echo "ERROR: HTTP $http_code - $body" >&2
        return 1
    fi
    
    echo "$body"
}

# Make HTTP DELETE request
http_delete() {
    local url="$1"
    
    print_verbose "DELETE $url"
    
    local response
    local http_code
    
    if [[ -n "${ACCESS_TOKEN}" ]]; then
        response=$(curl -s -w "\n%{http_code}" -X DELETE \
            -H "Authorization: Bearer ${ACCESS_TOKEN}" \
            "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X DELETE \
            "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    print_verbose "HTTP $http_code"
    print_verbose "Response: $body"
    
    if [[ ! "$http_code" =~ ^2[0-9]{2}$ ]]; then
        echo "ERROR: HTTP $http_code - $body" >&2
        return 1
    fi
    
    echo "$body"
}

################################################################################
# FUNCIONES DE CLEANUP
################################################################################

cleanup() {
    if [[ "$CLEANUP_NEEDED" == "true" ]] && [[ -n "$VM_ID" ]] && [[ -n "$ACCESS_TOKEN" ]]; then
        echo ""
        print_warning "Limpiando recursos creados durante el test..."
        
        # Try to delete the VM
        if http_delete "${API_URL}/api/v1/vms/${VM_ID}" &> /dev/null; then
            print_success "VM eliminada: ${VM_ID}"
        else
            print_warning "No se pudo eliminar la VM ${VM_ID} (puede que ya esté eliminada)"
        fi
    fi
}

# Register cleanup on exit
trap cleanup EXIT

################################################################################
# FASE 1: VALIDACIÓN INICIAL
################################################################################

phase_validation() {
    print_section "INIT" "Verificando prerequisitos..."
    
    test_count
    if ! command_exists curl; then
        test_fail "curl no está instalado. Instálalo con: apt-get install curl"
    fi
    print_success "curl instalado"
    test_pass
    
    test_count
    if ! command_exists jq; then
        test_fail "jq no está instalado. Instálalo con: apt-get install jq"
    fi
    print_success "jq instalado"
    test_pass
    
    test_count
    print_progress "Verificando acceso a la API..."
    if ! http_get "${API_URL}/api/v1/health" &> /dev/null; then
        test_fail "La API no está accesible en ${API_URL}. Verifica que esté corriendo."
    fi
    print_success "API accesible en ${API_URL}"
    test_pass
    
    # Show configuration
    print_info "Configuración del test:"
    print_info "  API: ${API_URL}"
    print_info "  Usuario: ${API_USERNAME}"
    print_info "  VM: ${VM_NAME}"
    print_info "  Recursos: ${VM_VCPU_COUNT} vCPU, ${VM_MEMORY_MB} MB RAM"
    print_info "  Timeout: ${MAX_WAIT_TIME}s (polling cada ${POLL_INTERVAL}s)"
}

################################################################################
# FASE 2: AUTENTICACIÓN
################################################################################

phase_authentication() {
    print_section "AUTH" "Autenticando usuario..."
    
    test_count
    local login_data="username=${API_USERNAME}&password=${API_PASSWORD}"
    local response
    
    if ! response=$(http_post "${API_URL}/api/v1/auth/login" "$login_data" "application/x-www-form-urlencoded"); then
        test_fail "Login falló. Verifica las credenciales."
    fi
    
    ACCESS_TOKEN=$(echo "$response" | jq -r '.access_token')
    
    if [[ -z "$ACCESS_TOKEN" ]] || [[ "$ACCESS_TOKEN" == "null" ]]; then
        test_fail "No se pudo obtener el access token de la respuesta"
    fi
    
    print_success "Login exitoso"
    print_success "Token obtenido"
    test_pass
    
    # Verify token with /me endpoint
    test_count
    local user_info
    if ! user_info=$(http_get "${API_URL}/api/v1/auth/me"); then
        test_fail "No se pudo verificar el token"
    fi
    
    local user_username=$(echo "$user_info" | jq -r '.username')
    local user_email=$(echo "$user_info" | jq -r '.email')
    
    print_success "Usuario autenticado: ${user_username} (${user_email})"
    test_pass
}

################################################################################
# FASE 3: CREACIÓN DE VM
################################################################################

phase_create_vm() {
    print_section "CREATE" "Creando VM..."
    
    test_count
    local vm_data=$(jq -n \
        --arg name "$VM_NAME" \
        --arg desc "$VM_DESCRIPTION" \
        --argjson vcpu "$VM_VCPU_COUNT" \
        --argjson mem "$VM_MEMORY_MB" \
        '{name: $name, description: $desc, vcpu_count: $vcpu, memory_mb: $mem}')
    
    local response
    if ! response=$(http_post "${API_URL}/api/v1/vms/" "$vm_data"); then
        test_fail "No se pudo crear la VM"
    fi
    
    VM_ID=$(echo "$response" | jq -r '.vm_id')
    VM_DB_ID=$(echo "$response" | jq -r '.id')
    local status=$(echo "$response" | jq -r '.status')
    
    if [[ -z "$VM_ID" ]] || [[ "$VM_ID" == "null" ]]; then
        test_fail "No se obtuvo vm_id en la respuesta"
    fi
    
    track_state "$status"
    CLEANUP_NEEDED=true
    
    print_success "VM creada: ${VM_ID}"
    print_info "Estado inicial: ${status}"
    print_info "ID en BD: ${VM_DB_ID}"
    print_info "Recursos: ${VM_VCPU_COUNT} vCPU, ${VM_MEMORY_MB} MB RAM"
    test_pass
}

################################################################################
# FASE 4: MONITOREO DE PROVISIONING
################################################################################

phase_wait_for_running() {
    print_section "PROVISION" "Esperando provisioning..."
    
    test_count
    local elapsed=0
    local last_status=""
    
    while [[ $elapsed -lt $MAX_WAIT_TIME ]]; do
        local response
        if ! response=$(http_get "${API_URL}/api/v1/vms/${VM_ID}"); then
            test_fail "Error al consultar estado de la VM"
        fi
        
        local status=$(echo "$response" | jq -r '.status')
        local ip_address=$(echo "$response" | jq -r '.ip_address')
        local error_msg=$(echo "$response" | jq -r '.error_message')
        
        track_state "$status"
        
        # Show status change
        if [[ "$status" != "$last_status" ]]; then
            print_progress "Estado: ${status} ... (${elapsed}s)"
            last_status="$status"
        fi
        
        # Check for error state
        if [[ "$status" == "error" ]]; then
            test_fail "VM entró en estado de error: ${error_msg}"
        fi
        
        # Check if running
        if [[ "$status" == "running" ]]; then
            print_success "VM en estado 'running' ($(format_time $elapsed))"
            
            if [[ -n "$ip_address" ]] && [[ "$ip_address" != "null" ]]; then
                print_info "IP asignada: ${ip_address}"
            else
                print_warning "VM running pero sin IP asignada"
            fi
            
            test_pass
            return 0
        fi
        
        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
    done
    
    test_fail "Timeout esperando que la VM esté running (>${MAX_WAIT_TIME}s)"
}

################################################################################
# FASE 5: VERIFICACIÓN DE VM RUNNING
################################################################################

phase_verify_vm() {
    print_section "VERIFY" "Verificando VM..."
    
    # Verify VM appears in list
    test_count
    local list_response
    if ! list_response=$(http_get "${API_URL}/api/v1/vms/?page=1&page_size=100"); then
        test_fail "Error al listar VMs"
    fi
    
    local found=$(echo "$list_response" | jq --arg vm_id "$VM_ID" '.items[] | select(.vm_id == $vm_id) | .vm_id')
    
    if [[ -z "$found" ]]; then
        test_fail "La VM ${VM_ID} no aparece en la lista de VMs"
    fi
    
    print_success "VM aparece en la lista"
    test_pass
    
    # Get VM details and verify all fields
    test_count
    local vm_details
    if ! vm_details=$(http_get "${API_URL}/api/v1/vms/${VM_ID}"); then
        test_fail "Error al obtener detalles de la VM"
    fi
    
    local actual_name=$(echo "$vm_details" | jq -r '.name')
    local actual_vcpu=$(echo "$vm_details" | jq -r '.vcpu_count')
    local actual_memory=$(echo "$vm_details" | jq -r '.memory_mb')
    local actual_status=$(echo "$vm_details" | jq -r '.status')
    local actual_ip=$(echo "$vm_details" | jq -r '.ip_address')
    
    if [[ "$actual_name" != "$VM_NAME" ]]; then
        test_fail "Nombre de VM no coincide. Esperado: ${VM_NAME}, Actual: ${actual_name}"
    fi
    
    if [[ "$actual_vcpu" != "$VM_VCPU_COUNT" ]]; then
        test_fail "vCPU count no coincide. Esperado: ${VM_VCPU_COUNT}, Actual: ${actual_vcpu}"
    fi
    
    if [[ "$actual_memory" != "$VM_MEMORY_MB" ]]; then
        test_fail "Memory no coincide. Esperado: ${VM_MEMORY_MB}, Actual: ${actual_memory}"
    fi
    
    print_success "Detalles de VM correctos"
    print_info "Nombre: ${actual_name}"
    print_info "Estado: ${actual_status}"
    print_info "Recursos: ${actual_vcpu} vCPU, ${actual_memory} MB"
    if [[ -n "$actual_ip" ]] && [[ "$actual_ip" != "null" ]]; then
        print_info "IP: ${actual_ip}"
    fi
    test_pass
}

################################################################################
# FASE 6: ACTUALIZACIÓN DE METADATA
################################################################################

phase_update_vm() {
    print_section "UPDATE" "Actualizando metadata de VM..."
    
    test_count
    local new_name="${VM_NAME}-updated"
    local new_desc="Updated description at $(date '+%Y-%m-%d %H:%M:%S')"
    
    local update_data=$(jq -n \
        --arg name "$new_name" \
        --arg desc "$new_desc" \
        '{name: $name, description: $desc}')
    
    local response
    if ! response=$(http_patch "${API_URL}/api/v1/vms/${VM_ID}" "$update_data"); then
        test_fail "Error al actualizar la VM"
    fi
    
    local updated_name=$(echo "$response" | jq -r '.name')
    local updated_desc=$(echo "$response" | jq -r '.description')
    
    if [[ "$updated_name" != "$new_name" ]]; then
        test_fail "El nombre no se actualizó correctamente"
    fi
    
    if [[ "$updated_desc" != "$new_desc" ]]; then
        test_fail "La descripción no se actualizó correctamente"
    fi
    
    print_success "Nombre actualizado: ${new_name}"
    print_success "Descripción actualizada"
    test_pass
}

################################################################################
# FASE 7: ELIMINACIÓN DE VM
################################################################################

phase_delete_vm() {
    print_section "DELETE" "Eliminando VM..."
    
    test_count
    local response
    if ! response=$(http_delete "${API_URL}/api/v1/vms/${VM_ID}"); then
        test_fail "Error al solicitar eliminación de la VM"
    fi
    
    local delete_status=$(echo "$response" | jq -r '.status')
    
    if [[ "$delete_status" != "deleting" ]]; then
        print_warning "Estado esperado 'deleting', recibido: ${delete_status}"
    else
        print_success "Eliminación solicitada"
        print_info "Estado: deleting"
    fi
    
    track_state "deleting"
    test_pass
    
    # Wait for VM to be fully deleted
    test_count
    print_progress "Esperando eliminación completa..."
    
    local elapsed=0
    while [[ $elapsed -lt $DELETE_WAIT_TIME ]]; do
        # Try to get VM - should return 404 when deleted
        if ! http_get "${API_URL}/api/v1/vms/${VM_ID}" &> /dev/null; then
            print_success "VM eliminada completamente ($(format_time $elapsed))"
            CLEANUP_NEEDED=false  # No need for cleanup anymore
            track_state "deleted"
            test_pass
            return 0
        fi
        
        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
    done
    
    print_warning "Timeout esperando eliminación completa (la VM puede estar siendo eliminada en background)"
    test_pass
}

################################################################################
# FASE 8: RESUMEN FINAL
################################################################################

phase_summary() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    
    echo ""
    echo -e "${BLUE}${BOLD}╔════════════════════════════════════════════════════════════════╗${RESET}"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${BLUE}${BOLD}║                                                                ║${RESET}"
        echo -e "${BLUE}${BOLD}║${RESET}                    ${GREEN}${BOLD}✓ TEST EXITOSO${RESET}                         ${BLUE}${BOLD}║${RESET}"
        echo -e "${BLUE}${BOLD}║                                                                ║${RESET}"
    else
        echo -e "${BLUE}${BOLD}║                                                                ║${RESET}"
        echo -e "${BLUE}${BOLD}║${RESET}                    ${RED}${BOLD}✗ TEST FALLIDO${RESET}                         ${BLUE}${BOLD}║${RESET}"
        echo -e "${BLUE}${BOLD}║                                                                ║${RESET}"
    fi
    
    echo -e "${BLUE}${BOLD}╚════════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    
    print_info "Duración total: $(format_time $total_duration)"
    print_info "VM ID: ${VM_ID}"
    
    # Show state transitions
    if [[ ${#STATES_VISITED[@]} -gt 0 ]]; then
        local states_str=$(IFS=' → '; echo "${STATES_VISITED[*]}")
        print_info "Estados: ${states_str}"
    fi
    
    # Test statistics
    echo ""
    print_info "Estadísticas de tests:"
    print_info "  Total: ${TESTS_TOTAL}"
    print_info "  ${GREEN}Exitosos: ${TESTS_PASSED}${RESET}"
    if [[ $TESTS_FAILED -gt 0 ]]; then
        print_info "  ${RED}Fallidos: ${TESTS_FAILED}${RESET}"
    fi
    
    if [[ $TESTS_TOTAL -gt 0 ]]; then
        local pass_rate=$((TESTS_PASSED * 100 / TESTS_TOTAL))
        print_info "  Tasa de éxito: ${pass_rate}%"
    fi
    
    echo ""
}

################################################################################
# FUNCIÓN PRINCIPAL
################################################################################

main() {
    # Print header
    print_header "MIKROM VM LIFECYCLE TEST"
    
    # Run test phases
    phase_validation
    phase_authentication
    phase_create_vm
    phase_wait_for_running
    phase_verify_vm
    phase_update_vm
    phase_delete_vm
    
    # Print summary
    phase_summary
    
    # Exit with appropriate code
    if [[ $TESTS_FAILED -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"
