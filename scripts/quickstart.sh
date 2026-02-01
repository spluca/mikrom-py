#!/bin/bash
# Quick Start - Ejecuta este script para hacer una prueba rápida del ciclo de vida de VMs

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║         QUICK START - Test de Ciclo de Vida de VMs            ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Check dependencies
echo -e "${BLUE}[1/5]${NC} Verificando dependencias..."
if ! command -v curl &> /dev/null; then
    echo -e "${RED}✗ curl no instalado${NC}"
    echo "   Instalar con: sudo apt-get install curl"
    exit 1
fi
if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ jq no instalado${NC}"
    echo "   Instalar con: sudo apt-get install jq"
    exit 1
fi
echo -e "${GREEN}✓ Dependencias OK${NC}"
echo ""

# Step 2: Check if API is running
echo -e "${BLUE}[2/5]${NC} Verificando que la API esté corriendo..."
if ! curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo -e "${RED}✗ API no está corriendo${NC}"
    echo ""
    echo "   Iniciar servicios:"
    echo -e "   ${YELLOW}docker compose up -d${NC}"
    echo ""
    echo "   O localmente:"
    echo -e "   ${YELLOW}docker compose up -d db redis${NC}"
    echo -e "   ${YELLOW}make worker  ${NC} # En una terminal"
    echo -e "   ${YELLOW}make run     ${NC} # En otra terminal"
    exit 1
fi
echo -e "${GREEN}✓ API accesible${NC}"
echo ""

# Step 3: Check if user exists
echo -e "${BLUE}[3/5]${NC} Verificando usuario..."
echo "   Si no tienes un usuario, créalo con:"
echo -e "   ${YELLOW}make superuser${NC}"
echo ""
echo "   Credenciales por defecto:"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
read -p "¿Continuar con el test? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Test cancelado."
    exit 0
fi
echo ""

# Step 4: Info about the test
echo -e "${BLUE}[4/5]${NC} Preparando test..."
echo "   El test ejecutará:"
echo "   • Autenticación con JWT"
echo "   • Creación de una VM de prueba"
echo "   • Monitoreo de provisioning"
echo "   • Verificación de datos"
echo "   • Actualización de metadata"
echo "   • Eliminación de la VM"
echo ""
echo "   Nota: Si no tienes ippool/firecracker configurado,"
echo "   la VM no llegará a 'running', pero las operaciones"
echo "   de API se probarán correctamente."
echo ""

# Step 5: Run the test
echo -e "${BLUE}[5/5]${NC} Ejecutando test..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run with reduced timeout for quick test
MAX_WAIT_TIME=30 ./scripts/test-vm-lifecycle.sh

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${GREEN}✓ Test completado exitosamente${NC}"
    echo ""
    echo "Próximos pasos:"
    echo "  • Ver documentación completa: less scripts/README.md"
    echo "  • Ver ejemplos de uso: cat scripts/examples.sh"
    echo "  • Ejecutar test completo: make test-vm-lifecycle"
    echo "  • Ejecutar con verbose: make test-vm-verbose"
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${RED}✗ Test falló${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  • Verificar que todos los servicios estén corriendo"
    echo "  • Verificar credenciales de usuario"
    echo "  • Ver logs: docker compose logs -f"
    echo "  • Ejecutar con verbose: VERBOSE=true ./scripts/test-vm-lifecycle.sh"
fi
