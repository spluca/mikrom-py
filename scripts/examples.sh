#!/bin/bash
#
# Ejemplo de uso del script test-vm-lifecycle.sh
# Este archivo muestra diferentes formas de ejecutar el script
#

# ============================================================================
# Ejemplo 1: Uso básico con configuración por defecto
# ============================================================================
echo "=== Ejemplo 1: Uso básico ==="
./scripts/test-vm-lifecycle.sh


# ============================================================================
# Ejemplo 2: Con variables de entorno personalizadas
# ============================================================================
echo ""
echo "=== Ejemplo 2: Configuración personalizada ==="
API_URL="http://localhost:8000" \
API_USERNAME="admin" \
API_PASSWORD="admin123" \
VM_NAME="my-custom-vm" \
VM_VCPU_COUNT=2 \
VM_MEMORY_MB=512 \
./scripts/test-vm-lifecycle.sh


# ============================================================================
# Ejemplo 3: Prueba rápida (sin esperar infraestructura real)
# ============================================================================
echo ""
echo "=== Ejemplo 3: Prueba rápida ==="
MAX_WAIT_TIME=10 ./scripts/test-vm-lifecycle.sh


# ============================================================================
# Ejemplo 4: Modo verbose para debugging
# ============================================================================
echo ""
echo "=== Ejemplo 4: Modo verbose ==="
VERBOSE=true ./scripts/test-vm-lifecycle.sh


# ============================================================================
# Ejemplo 5: VM con más recursos y timeout extendido
# ============================================================================
echo ""
echo "=== Ejemplo 5: VM grande con timeout largo ==="
VM_VCPU_COUNT=4 \
VM_MEMORY_MB=2048 \
MAX_WAIT_TIME=180 \
POLL_INTERVAL=5 \
./scripts/test-vm-lifecycle.sh


# ============================================================================
# Ejemplo 6: Usando el Makefile
# ============================================================================
echo ""
echo "=== Ejemplo 6: Via Makefile ==="

# Test completo
make test-vm-lifecycle

# Test rápido
make test-vm-quick

# Test con verbose
make test-vm-verbose


# ============================================================================
# Ejemplo 7: Contra API remota
# ============================================================================
echo ""
echo "=== Ejemplo 7: API remota ==="
API_URL="http://192.168.1.100:8000" \
API_USERNAME="testuser" \
API_PASSWORD="testpass123" \
./scripts/test-vm-lifecycle.sh


# ============================================================================
# Ejemplo 8: Export de variables para múltiples ejecuciones
# ============================================================================
echo ""
echo "=== Ejemplo 8: Variables exportadas ==="

# Exportar variables
export API_URL="http://localhost:8000"
export API_USERNAME="admin"
export API_PASSWORD="admin123"
export VM_VCPU_COUNT=1
export VM_MEMORY_MB=256

# Ahora se pueden hacer múltiples ejecuciones con la misma configuración
./scripts/test-vm-lifecycle.sh
./scripts/test-vm-lifecycle.sh
./scripts/test-vm-lifecycle.sh
