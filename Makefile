.PHONY: help install dev-install update clean test test-cov lint format check run docker-build docker-up docker-down docker-logs migrate migrate-create migrate-upgrade migrate-downgrade db-reset superuser shell

# Variables
PYTHON := uv run python
PYTEST := uv run pytest
ALEMBIC := uv run alembic
UVICORN := uv run uvicorn
DOCKER_COMPOSE := docker compose
APP_MODULE := mikrom.main:app

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

help: ## Mostrar esta ayuda
	@echo "$(GREEN)Mikrom API - Comandos disponibles:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# Instalación y Dependencias
# ============================================================================

install: ## Instalar dependencias de producción
	@echo "$(GREEN)Instalando dependencias de producción...$(NC)"
	uv sync --no-dev

dev-install: ## Instalar dependencias de desarrollo
	@echo "$(GREEN)Instalando dependencias de desarrollo...$(NC)"
	uv sync

update: ## Actualizar dependencias
	@echo "$(GREEN)Actualizando dependencias...$(NC)"
	uv lock --upgrade

clean: ## Limpiar archivos temporales y caché
	@echo "$(YELLOW)Limpiando archivos temporales...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf build/ dist/ htmlcov/ .eggs/
	@echo "$(GREEN)✓ Limpieza completada$(NC)"

# ============================================================================
# Testing
# ============================================================================

test: ## Ejecutar todos los tests
	@echo "$(GREEN)Ejecutando tests...$(NC)"
	$(PYTEST) -v

test-cov: ## Ejecutar tests con cobertura
	@echo "$(GREEN)Ejecutando tests con cobertura...$(NC)"
	$(PYTEST) -v --cov=mikrom --cov-report=html --cov-report=term-missing

test-watch: ## Ejecutar tests en modo watch
	@echo "$(GREEN)Ejecutando tests en modo watch...$(NC)"
	$(PYTEST) -v --looponfail

test-fast: ## Ejecutar solo tests rápidos (sin integración)
	@echo "$(GREEN)Ejecutando tests rápidos...$(NC)"
	$(PYTEST) -v -m "not integration"

test-failed: ## Re-ejecutar solo los tests fallidos
	@echo "$(GREEN)Re-ejecutando tests fallidos...$(NC)"
	$(PYTEST) -v --lf

# ============================================================================
# Code Quality
# ============================================================================

lint: ## Ejecutar linter (ruff)
	@echo "$(GREEN)Ejecutando linter...$(NC)"
	uv run ruff check mikrom tests

lint-fix: ## Ejecutar linter y auto-corregir
	@echo "$(GREEN)Ejecutando linter con auto-corrección...$(NC)"
	uv run ruff check --fix mikrom tests

format: ## Formatear código
	@echo "$(GREEN)Formateando código...$(NC)"
	uv run ruff format mikrom tests

format-check: ## Verificar formato sin modificar
	@echo "$(GREEN)Verificando formato...$(NC)"
	uv run ruff format --check mikrom tests

check: lint format-check test ## Ejecutar todas las verificaciones (lint + format + test)

# ============================================================================
# Desarrollo Local
# ============================================================================

run: ## Ejecutar servidor de desarrollo
	@echo "$(GREEN)Iniciando servidor de desarrollo...$(NC)"
	$(UVICORN) $(APP_MODULE) --reload --host 0.0.0.0 --port 8000

run-prod: ## Ejecutar servidor en modo producción
	@echo "$(GREEN)Iniciando servidor en modo producción...$(NC)"
	$(UVICORN) $(APP_MODULE) --host 0.0.0.0 --port 8000 --workers 4

worker: ## Ejecutar background task worker
	@echo "$(GREEN)Iniciando worker de background tasks...$(NC)"
	$(PYTHON) run_worker.py

shell: ## Abrir shell de Python con el proyecto cargado
	@echo "$(GREEN)Abriendo shell de Python...$(NC)"
	$(PYTHON) -i -c "from mikrom.main import app; from mikrom.database import engine; from mikrom.models import *"

# ============================================================================
# Docker
# ============================================================================

docker-build: ## Construir imagen Docker
	@echo "$(GREEN)Construyendo imagen Docker...$(NC)"
	$(DOCKER_COMPOSE) build

docker-build-no-cache: ## Construir imagen Docker sin caché
	@echo "$(GREEN)Construyendo imagen Docker sin caché...$(NC)"
	$(DOCKER_COMPOSE) build --no-cache

docker-up: ## Levantar contenedores
	@echo "$(GREEN)Levantando contenedores...$(NC)"
	$(DOCKER_COMPOSE) up -d

docker-down: ## Detener contenedores
	@echo "$(YELLOW)Deteniendo contenedores...$(NC)"
	$(DOCKER_COMPOSE) down

docker-restart: ## Reiniciar contenedores
	@echo "$(YELLOW)Reiniciando contenedores...$(NC)"
	$(DOCKER_COMPOSE) restart

docker-logs: ## Ver logs de contenedores
	$(DOCKER_COMPOSE) logs -f

docker-logs-app: ## Ver logs solo del contenedor app
	$(DOCKER_COMPOSE) logs -f app

docker-logs-db: ## Ver logs solo del contenedor db
	$(DOCKER_COMPOSE) logs -f db

docker-ps: ## Ver estado de contenedores
	$(DOCKER_COMPOSE) ps

docker-clean: ## Limpiar contenedores, volúmenes e imágenes
	@echo "$(RED)⚠ Esto eliminará todos los contenedores, volúmenes e imágenes$(NC)"
	@read -p "¿Continuar? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DOCKER_COMPOSE) down -v --rmi all; \
		echo "$(GREEN)✓ Limpieza Docker completada$(NC)"; \
	fi

docker-shell: ## Abrir shell en el contenedor app
	$(DOCKER_COMPOSE) exec app /bin/sh

# ============================================================================
# Base de Datos y Migraciones
# ============================================================================

migrate-create: ## Crear nueva migración (usar: make migrate-create MSG="mensaje")
	@if [ -z "$(MSG)" ]; then \
		echo "$(RED)Error: Debes proporcionar un mensaje$(NC)"; \
		echo "Uso: make migrate-create MSG=\"descripcion de la migracion\""; \
		exit 1; \
	fi
	@echo "$(GREEN)Creando migración: $(MSG)$(NC)"
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-upgrade: ## Aplicar migraciones pendientes
	@echo "$(GREEN)Aplicando migraciones...$(NC)"
	$(ALEMBIC) upgrade head

migrate-downgrade: ## Revertir última migración
	@echo "$(YELLOW)Revirtiendo última migración...$(NC)"
	$(ALEMBIC) downgrade -1

migrate-history: ## Ver historial de migraciones
	$(ALEMBIC) history

migrate-current: ## Ver migración actual
	$(ALEMBIC) current

migrate-heads: ## Ver heads de migraciones
	$(ALEMBIC) heads

db-reset: ## Resetear base de datos (CUIDADO: elimina todos los datos)
	@echo "$(RED)⚠ ADVERTENCIA: Esto eliminará TODOS los datos de la base de datos$(NC)"
	@read -p "¿Estás seguro? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(ALEMBIC) downgrade base; \
		$(ALEMBIC) upgrade head; \
		echo "$(GREEN)✓ Base de datos reseteada$(NC)"; \
	fi

superuser: ## Crear superusuario
	@echo "$(GREEN)Creando superusuario...$(NC)"
	@$(PYTHON) -c "\
from mikrom.database import sync_engine; \
from mikrom.models import User; \
from mikrom.core.security import get_password_hash; \
from sqlmodel import Session; \
import sys; \
print('Email:', end=' '); \
email = input(); \
print('Username:', end=' '); \
username = input(); \
print('Password:', end=' '); \
password = input(); \
print('Full Name (opcional):', end=' '); \
full_name = input() or None; \
with Session(sync_engine) as session: \
    existing = session.query(User).filter((User.email == email) | (User.username == username)).first(); \
    if existing: \
        print('❌ Error: Usuario con ese email o username ya existe'); \
        sys.exit(1); \
    user = User( \
        email=email, \
        username=username, \
        hashed_password=get_password_hash(password), \
        full_name=full_name, \
        is_active=True, \
        is_superuser=True \
    ); \
    session.add(user); \
    session.commit(); \
    print(f'✓ Superusuario {username} creado exitosamente'); \
"

# ============================================================================
# Utilidades
# ============================================================================

health: ## Verificar salud de la API
	@echo "$(GREEN)Verificando salud de la API...$(NC)"
	@curl -s http://localhost:8000/api/v1/health | python -m json.tool || echo "$(RED)Error: API no disponible$(NC)"

docs: ## Abrir documentación de la API
	@echo "$(GREEN)Abriendo documentación...$(NC)"
	@echo "Swagger UI: http://localhost:8000/docs"
	@echo "ReDoc: http://localhost:8000/redoc"
	@xdg-open http://localhost:8000/docs 2>/dev/null || open http://localhost:8000/docs 2>/dev/null || echo "Abre manualmente: http://localhost:8000/docs"

info: ## Mostrar información del proyecto
	@echo "$(GREEN)Información del Proyecto$(NC)"
	@echo ""
	@echo "Nombre:        Mikrom API"
	@echo "Versión:       1.0.0"
	@echo "Python:        $$(python --version)"
	@echo "Directorio:    $$(pwd)"
	@echo ""
	@echo "$(GREEN)Servicios:$(NC)"
	@echo "API:           http://localhost:8000"
	@echo "Documentación: http://localhost:8000/docs"
	@echo "Adminer:       http://localhost:8080"
	@echo ""

# ============================================================================
# Tests de Integración - VMs
# ============================================================================

test-vm-lifecycle: ## Probar ciclo de vida completo de VM
	@echo "$(GREEN)Ejecutando test de ciclo de vida de VM...$(NC)"
	@./scripts/test-vm-lifecycle.sh

test-vm-quick: ## Prueba rápida de VM (sin esperar running)
	@echo "$(GREEN)Ejecutando prueba rápida de VM (timeout reducido)...$(NC)"
	@MAX_WAIT_TIME=10 ./scripts/test-vm-lifecycle.sh

test-vm-verbose: ## Prueba de VM con output detallado
	@echo "$(GREEN)Ejecutando prueba de VM en modo verbose...$(NC)"
	@VERBOSE=true ./scripts/test-vm-lifecycle.sh

# ============================================================================
# CI/CD
# ============================================================================

ci: clean lint format-check test ## Ejecutar pipeline de CI completo

# ============================================================================
# Desarrollo Completo (Setup inicial)
# ============================================================================

setup: dev-install migrate-upgrade ## Setup inicial del proyecto
	@echo "$(GREEN)============================================$(NC)"
	@echo "$(GREEN)✓ Setup completado exitosamente$(NC)"
	@echo "$(GREEN)============================================$(NC)"
	@echo ""
	@echo "Próximos pasos:"
	@echo "  1. Crear superusuario: $(YELLOW)make superuser$(NC)"
	@echo "  2. Iniciar servidor:   $(YELLOW)make run$(NC)"
	@echo "  3. Ver documentación:  $(YELLOW)make docs$(NC)"
	@echo ""

docker-setup: docker-build docker-up migrate-upgrade ## Setup con Docker
	@echo "$(GREEN)============================================$(NC)"
	@echo "$(GREEN)✓ Docker setup completado$(NC)"
	@echo "$(GREEN)============================================$(NC)"
	@echo ""
	@echo "Servicios disponibles:"
	@echo "  - API:     http://localhost:8000"
	@echo "  - Docs:    http://localhost:8000/docs"
	@echo "  - Adminer: http://localhost:8080"
	@echo ""
	@echo "Ver logs: $(YELLOW)make docker-logs$(NC)"
	@echo ""
