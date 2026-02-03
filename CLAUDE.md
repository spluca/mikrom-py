# Mikrom-py - Documentación para Claude AI

## 📋 Resumen del Proyecto

**Mikrom-py** es una API REST moderna construida con FastAPI para la gestión de microVMs Firecracker. El proyecto permite aprovisionar, gestionar y eliminar máquinas virtuales ligeras a través de una API REST con autenticación JWT.

### Tecnologías Principales
- **FastAPI** - Framework web moderno y rápido
- **SQLModel** - ORM con integración Pydantic perfecta
- **PostgreSQL** - Base de datos relacional
- **Redis** - Broker de mensajes para tareas en background
- **Celery** - Sistema de tareas asíncronas
- **Firecracker** - MicroVMs ligeras vía Ansible
- **Docker** - Contenedorización completa
- **Alembic** - Migraciones de base de datos
- **uv** - Gestor de paquetes Python moderno

---

## 🏗️ Arquitectura del Proyecto

### Estructura de Directorios

```
mikrom-py/
├── mikrom/                     # Paquete principal
│   ├── main.py                 # Aplicación FastAPI
│   ├── config.py               # Configuración con Pydantic Settings
│   ├── database.py             # Configuración de base de datos
│   ├── dependencies.py         # Dependencias globales
│   ├── celery_app.py          # Aplicación Celery
│   │
│   ├── core/                   # Núcleo de la aplicación
│   │   ├── security.py         # JWT, hashing de contraseñas
│   │   └── exceptions.py       # Excepciones personalizadas
│   │
│   ├── models/                 # Modelos SQLModel
│   │   ├── base.py             # Modelo base con timestamps
│   │   ├── user.py             # Modelo de usuario
│   │   ├── vm.py               # Modelo de VM
│   │   ├── ip_pool.py          # Pool de IPs
│   │   └── ip_allocation.py    # Asignación de IPs
│   │
│   ├── schemas/                # Schemas Pydantic
│   │   ├── common.py           # Schemas comunes
│   │   ├── token.py            # Schemas de tokens
│   │   ├── user.py             # Schemas de usuario
│   │   └── vm.py               # Schemas de VM
│   │
│   ├── api/                    # Endpoints API
│   │   ├── deps.py             # Dependencias de endpoints
│   │   └── v1/                 # API versión 1
│   │       ├── router.py       # Router principal v1
│   │       └── endpoints/
│   │           ├── auth.py     # Autenticación
│   │           ├── users.py    # CRUD de usuarios
│   │           ├── vms.py      # Gestión de VMs
│   │           ├── events.py   # Server-Sent Events (SSE)
│   │           └── health.py   # Health check
│   │
│   ├── clients/                # Clientes de servicios externos
│   │   └── firecracker.py      # Cliente de Firecracker (Ansible)
│   │
│   ├── services/               # Lógica de negocio
│   │   ├── vm_service.py       # Servicio de VMs
│   │   └── ippool_service.py   # Gestión de pool de IPs
│   │
│   ├── worker/                 # Tareas en background
│   │   └── tasks.py            # Definiciones de tareas Celery
│   │
│   ├── events/                 # Sistema de eventos
│   │   ├── publisher.py        # Publicador de eventos
│   │   └── sse.py              # Server-Sent Events
│   │
│   ├── middleware/             # Middleware personalizado
│   │   ├── rate_limit.py       # Rate limiting
│   │   └── logging.py          # Logging de requests
│   │
│   └── utils/                  # Utilidades
│       ├── logger.py           # Configuración de logging
│       ├── telemetry.py        # OpenTelemetry
│       └── context.py          # Contexto de logging
│
├── tests/                      # Tests
│   ├── conftest.py             # Fixtures de pytest
│   ├── test_api/               # Tests de endpoints
│   ├── test_models/            # Tests de modelos
│   ├── test_services/          # Tests de servicios
│   ├── test_worker/            # Tests de tareas
│   └── test_clients/           # Tests de clientes
│
├── alembic/                    # Migraciones de BD
│   ├── env.py
│   └── versions/
│
├── scripts/                    # Scripts de utilidad
│   ├── create_superuser.py
│   ├── delete_orphan_vm.py
│   ├── check_firecracker_status.py
│   └── cleanup_firecracker_dirs.py
│
├── docs/                       # Documentación
│   ├── STATUS.md
│   ├── VM_GUIDE.md
│   ├── DEPLOYMENT_GUIDE.md
│   ├── CELERY_*.md
│   └── CI_CD.md
│
├── k8s/                        # Manifiestos Kubernetes
├── docker-compose.yml          # Servicios Docker
├── Dockerfile                  # Imagen de la app
├── pyproject.toml              # Configuración uv
├── Makefile                    # Comandos útiles
├── .env.example                # Variables de entorno
├── .gitlab-ci.yml              # Pipeline CI/CD
└── README.md                   # Documentación principal
```

---

## 🔑 Componentes Clave

### 1. Modelos de Datos (SQLModel)

#### User
- **Campos**: id, email, username, hashed_password, full_name, is_active, is_superuser
- **Relaciones**: vms (one-to-many con VM)
- **Ubicación**: `mikrom/models/user.py`

#### VM
- **Identificación**: id (DB), vm_id (único, ej: srv-a1b2c3d4), name, description
- **Recursos**: vcpu_count, memory_mb
- **Red**: ip_address
- **Estado**: status (pending, provisioning, starting, running, stopped, error, deleting)
- **Infraestructura**: host, kernel_path, rootfs_path
- **Relaciones**: user (many-to-one con User)
- **Ubicación**: `mikrom/models/vm.py`

#### IpPool
- **Gestión de IPs**: name, network, cidr, gateway, start_ip, end_ip, is_active
- **Ubicación**: `mikrom/models/ip_pool.py`

#### IpAllocation
- **Asignación de IPs**: ip_address, vm_id, pool_id, is_active
- **Ubicación**: `mikrom/models/ip_allocation.py`

### 2. Servicios de Negocio

#### VMService (`mikrom/services/vm_service.py`)
- `create_vm()`: Crea registro de VM y encola tarea de background
- `get_user_vms()`: Lista VMs con paginación
- `get_vm_by_id()`: Obtiene VM por vm_id
- `delete_vm()`: Marca VM para eliminación y encola tarea
- `stop_vm()`: Detiene VM
- `start_vm()`: Inicia VM
- `restart_vm()`: Reinicia VM

#### IPPoolService (`mikrom/services/ippool_service.py`)
- `allocate_ip()`: Asigna IP de un pool
- `release_ip()`: Libera IP asignada
- Gestión interna en PostgreSQL con transacciones

### 3. Tareas en Background (Celery)

**Ubicación**: `mikrom/worker/tasks.py`

#### create_vm_task
1. Asigna IP del pool
2. Ejecuta playbook Ansible para provisionar VM
3. Actualiza estado de VM en BD
4. Publica eventos SSE

#### delete_vm_task
1. Ejecuta playbook Ansible para eliminar VM
2. Libera IP
3. Elimina registro de BD
4. Publica eventos SSE

#### start_vm_task, stop_vm_task, restart_vm_task
- Operaciones de ciclo de vida de VMs

### 4. Cliente Firecracker

**Ubicación**: `mikrom/clients/firecracker.py`

- **FirecrackerClient**: Wrapper sobre Ansible Runner
- Ejecuta playbooks del repo `firecracker-deploy`
- Operaciones: create, delete, start, stop
- Timeout configurable vía `ANSIBLE_PLAYBOOK_TIMEOUT`

### 5. API REST Endpoints

**Prefix**: `/api/v1`

#### Auth (`/auth`)
- `POST /register` - Registrar usuario
- `POST /login` - Login (OAuth2 form)
- `POST /login/json` - Login (JSON)
- `POST /refresh` - Refresh token
- `GET /me` - Usuario actual

#### Users (`/users`)
- `GET /` - Listar usuarios (paginado)
- `GET /{id}` - Obtener usuario
- `PUT /{id}` - Actualizar usuario
- `DELETE /{id}` - Eliminar usuario (superuser)

#### VMs (`/vms`)
- `POST /` - Crear VM
- `GET /` - Listar VMs (paginado)
- `GET /{vm_id}` - Obtener VM
- `PATCH /{vm_id}` - Actualizar VM
- `DELETE /{vm_id}` - Eliminar VM
- `POST /{vm_id}/start` - Iniciar VM
- `POST /{vm_id}/stop` - Detener VM
- `POST /{vm_id}/restart` - Reiniciar VM

#### Events (`/events`)
- `GET /sse` - Server-Sent Events stream

---

## ⚙️ Configuración

### Variables de Entorno (.env)

**Base de Datos**
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/mikrom_db
DATABASE_ECHO=False
```

**Seguridad**
```bash
SECRET_KEY=your-secret-key-here  # openssl rand -hex 32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Celery & Redis**
```bash
REDIS_URL=redis://localhost:6379
CELERY_QUEUE_NAME=mikrom:queue
CELERY_WORKER_POOL=prefork  # prefork, threads, gevent, solo
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_SOFT_TIME_LIMIT=180
CELERY_TASK_HARD_TIME_LIMIT=240
```

**Firecracker**
```bash
FIRECRACKER_DEPLOY_PATH=/path/to/firecracker-deploy
FIRECRACKER_DEFAULT_HOST=  # Opcional
```

**Ansible**
```bash
ANSIBLE_PLAYBOOK_TIMEOUT=120
ANSIBLE_SSH_TIMEOUT=30
```

**Logging & Telemetry**
```bash
LOG_LEVEL=INFO
LOG_FORMAT=json  # json o console
OTEL_SERVICE_NAME=mikrom-api
OTEL_TRACE_SAMPLE_RATE=1.0
OTEL_EXPORT_CONSOLE=True
```

---

## 🚀 Flujo de Operaciones

### Creación de VM

1. **API Request**: `POST /api/v1/vms/`
   ```json
   {
     "name": "my-vm",
     "vcpu_count": 2,
     "memory_mb": 1024
   }
   ```

2. **VMService.create_vm()**:
   - Genera vm_id único (srv-xxxxxxxx)
   - Crea registro en BD con status=PENDING
   - Encola tarea `create_vm_task`
   - Retorna VM inmediatamente

3. **Background Task (create_vm_task)**:
   - Asigna IP del pool
   - Ejecuta playbook Ansible:
     ```
     ansible-playbook create.yml -e vm_id=srv-xxx -e vcpu=2 -e mem=1024
     ```
   - Actualiza VM: status=RUNNING, ip_address, host
   - Publica evento SSE: `vm.created`

4. **Cliente consulta estado**: `GET /api/v1/vms/srv-xxx`

### Eliminación de VM

1. **API Request**: `DELETE /api/v1/vms/srv-xxx`
2. **VMService.delete_vm()**:
   - Actualiza status=DELETING
   - Encola tarea `delete_vm_task`
3. **Background Task**:
   - Ejecuta playbook Ansible delete
   - Libera IP
   - Elimina registro de BD
   - Publica evento SSE: `vm.deleted`

---

## 🧪 Testing

### Setup de Tests

**Ubicación**: `tests/conftest.py`

Fixtures principales:
- `engine`: Motor SQLModel de prueba
- `session`: Sesión de base de datos
- `client`: Cliente TestClient de FastAPI
- `test_user`: Usuario de prueba
- `test_superuser`: Superusuario de prueba
- `auth_headers`: Headers con token JWT

### Ejecutar Tests

```bash
# Todos los tests
make test

# Con coverage
make test-cov

# Tests específicos
uv run pytest tests/test_api/test_vms.py -v

# Solo tests rápidos
uv run pytest -m "not slow"
```

**Requisitos**: PostgreSQL y Redis deben estar corriendo
```bash
docker compose up -d db redis
```

---

## 🐳 Docker

### Servicios en docker-compose.yml

1. **db** - PostgreSQL 16
2. **redis** - Redis 7 (broker Celery)
3. **app** - API FastAPI (puerto 8000)
4. **worker** - Celery worker (tareas background)
5. **beat** - Celery beat (tareas programadas)
6. **flower** - UI de monitoreo Celery (puerto 5555)
7. **adminer** - UI de PostgreSQL (puerto 8080)

### Comandos Docker

```bash
# Levantar todo
docker compose up -d

# Ver logs
docker compose logs -f app
docker compose logs -f worker

# Reiniciar worker
docker compose restart worker

# Ejecutar migraciones
docker compose exec app alembic upgrade head

# Shell en contenedor
docker compose exec app bash
```

---

## 🗃️ Base de Datos

### Migraciones (Alembic)

```bash
# Crear migración
make migrate-create MSG="add new field"
# o
uv run alembic revision --autogenerate -m "add new field"

# Aplicar migraciones
make migrate-upgrade
# o
uv run alembic upgrade head

# Revertir última
uv run alembic downgrade -1

# Ver historial
uv run alembic history
```

### Tablas Principales

- `users` - Usuarios
- `vms` - Máquinas virtuales
- `ip_pools` - Pools de IPs
- `ip_allocations` - Asignaciones de IPs a VMs

---

## 📊 Logging y Observabilidad

### Sistema de Logging

**Ubicación**: `mikrom/utils/logger.py`

- **Formato**: JSON estructurado (producción) o console (desarrollo)
- **Niveles**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Contexto**: request_id, vm_id, user_id se propagan automáticamente
- **Middleware**: LoggingMiddleware registra todas las requests

### OpenTelemetry

**Ubicación**: `mikrom/utils/telemetry.py`

- **Trazas**: Spans automáticos en requests, DB queries, tareas Celery
- **Atributos**: vm_id, user_id, celery.task_id, etc.
- **Export**: Console (desarrollo), OTLP (producción)

### Uso en Código

```python
from mikrom.utils.logger import get_logger, log_timer
from mikrom.utils.context import set_context
from mikrom.utils.telemetry import get_tracer, add_span_attributes

logger = get_logger(__name__)
tracer = get_tracer()

# Logging con contexto
set_context(vm_id="srv-xxx", action="create")
logger.info("Creating VM", extra={"vcpu_count": 2})

# Tracing
with tracer.start_as_current_span("operation") as span:
    add_span_attributes(**{"custom.attr": "value"})
    # ... operación ...

# Timer
with log_timer("expensive_operation", logger):
    # ... operación costosa ...
```

---

## 🔐 Seguridad

### Autenticación JWT

- **Access Token**: 30 minutos (configurable)
- **Refresh Token**: 7 días (configurable)
- **Algoritmo**: HS256
- **Hashing**: Argon2 para contraseñas

### Rate Limiting

- **Implementación**: SlowAPI
- **Límite**: 60 requests/minuto por IP (configurable)
- **Ubicación**: `mikrom/middleware/rate_limit.py`

### CORS

- **Orígenes**: Configurables vía `BACKEND_CORS_ORIGINS`
- **Desarrollo**: `http://localhost:3000`

---

## 🛠️ Makefile

Comandos principales:

```bash
make help           # Ver todos los comandos
make install        # Instalar dependencias
make dev-install    # Instalar con deps de desarrollo
make run            # Ejecutar servidor de desarrollo
make worker         # Ejecutar worker de Celery
make test           # Ejecutar tests
make test-cov       # Tests con coverage
make lint           # Linter
make lint-fix       # Linter con auto-fix
make format         # Formatear código
make migrate-create MSG="message"  # Nueva migración
make migrate-upgrade                # Aplicar migraciones
make superuser      # Crear superusuario
make db-reset       # Reset BD (⚠️ elimina datos)
make docker-up      # Levantar contenedores
make docker-down    # Detener contenedores
make health         # Health check de API
make docs           # Abrir docs
```

---

## 📝 Patrones y Convenciones

### Estructura de Código

1. **Modelos**: Siempre heredan de `TimestampModel` (created_at, updated_at)
2. **Schemas**: Separados en Create, Update, Response
3. **Servicios**: Lógica de negocio separada de endpoints
4. **Tasks**: Tareas largas/bloqueantes van a Celery
5. **Endpoints**: Delgados, delegan a servicios

### Nomenclatura

- **VM ID**: `srv-{8 caracteres hex}` (ej: srv-a1b2c3d4)
- **Variables**: snake_case
- **Clases**: PascalCase
- **Constantes**: UPPER_SNAKE_CASE

### Error Handling

```python
from fastapi import HTTPException, status

# 404 Not Found
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="VM not found"
)

# 403 Forbidden
raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Not allowed to access this VM"
)
```

### Paginación

```python
from mikrom.schemas.common import PaginatedResponse

# En endpoints
def list_vms(page: int = 1, page_size: int = 10):
    items, total = await service.get_vms(
        offset=(page - 1) * page_size,
        limit=page_size
    )
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )
```

---

## 🚨 Troubleshooting

### VM se queda en "pending"

**Causa**: Worker no está corriendo o falló

**Solución**:
```bash
# Ver logs del worker
docker compose logs worker

# Verificar Redis
docker compose ps redis

# Verificar IP pool
docker compose exec db psql -U postgres -d mikrom_db \
  -c "SELECT * FROM ip_pools WHERE is_active = true;"
```

### Error: "Firecracker deploy path does not exist"

**Causa**: `FIRECRACKER_DEPLOY_PATH` incorrecto en `.env`

**Solución**:
```bash
# Verificar ruta
ls -la /path/to/firecracker-deploy

# Actualizar .env
FIRECRACKER_DEPLOY_PATH=/ruta/correcta
```

### Tests fallan

**Causa**: PostgreSQL o Redis no están corriendo

**Solución**:
```bash
docker compose up -d db redis
make test
```

### Worker consume mucha memoria

**Causa**: Pool type o concurrency incorrectos

**Solución**: En `.env`
```bash
CELERY_WORKER_POOL=prefork  # Más estable
CELERY_WORKER_CONCURRENCY=4  # Reducir si es necesario
```

---

## 📚 Documentación Adicional

- **README.md** - Documentación principal y guía de inicio
- **docs/VM_GUIDE.md** - Guía completa de gestión de VMs
- **docs/DEPLOYMENT_GUIDE.md** - Guía de despliegue a producción
- **docs/CELERY_*.md** - Documentación de Celery
- **docs/CI_CD.md** - Pipeline de integración continua
- **docs/LOGGING_IMPLEMENTATION.md** - Sistema de logging
- **docs/STATUS.md** - Estado del proyecto

---

## 🎯 Próximos Pasos / TODOs

### Features Planeadas

- [ ] Sistema de permisos más granular
- [ ] Recuperación de contraseña por email
- [ ] Verificación de email
- [ ] WebSockets para notificaciones en tiempo real
- [ ] Monitoring con Prometheus/Grafana
- [ ] 2FA (autenticación de dos factores)
- [ ] Rate limiting por usuario (no solo IP)
- [ ] Snapshots de VMs
- [ ] Métricas de CPU/memoria de VMs

### Mejoras de Seguridad

- [ ] Token blacklist
- [ ] Audit logging
- [ ] Validación de fuerza de contraseña
- [ ] Account lockout tras intentos fallidos

### DevOps

- [ ] Kubernetes manifiestos completados
- [ ] Monitoring y alertas
- [ ] Backup automático de BD

---

## 🧩 Integración con Firecracker-Deploy

El proyecto requiere el repositorio `firecracker-deploy` configurado:

### Estructura Esperada

```
firecracker-deploy/
├── ansible/
│   ├── create.yml      # Playbook de creación
│   ├── delete.yml      # Playbook de eliminación
│   ├── start.yml       # Playbook de inicio
│   ├── stop.yml        # Playbook de parada
│   └── inventory/      # Inventario de hosts
└── README.md
```

### Variables Ansible

El cliente pasa estas variables a los playbooks:

```yaml
vm_id: srv-xxxxxxxx
vcpu_count: 2
memory_mb: 1024
ip_address: 172.16.0.2
host: kvm-host-01  # Si se especifica
```

---

## 💡 Tips para Desarrollo

### Desarrollo Local Rápido

```bash
# Terminal 1: BD y Redis
docker compose up -d db redis

# Terminal 2: API
make run

# Terminal 3: Worker
make worker

# Terminal 4: Tests
make test
```

### Debugging

```python
# Activar debug en .env
DEBUG=True
LOG_LEVEL=DEBUG

# Ver SQL queries
DATABASE_ECHO=True
```

### Hot Reload

El servidor se recarga automáticamente con cambios cuando:
- `DEBUG=True` en `.env`
- Ejecutas con `make run` o `uvicorn ... --reload`

### Crear Superusuario

```bash
make superuser
# o
uv run python scripts/create_superuser.py
```

---

## 📞 Endpoints de Utilidad

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### API Info
```bash
curl http://localhost:8000/
```

### Docs Interactivos
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Flower (Celery Monitor)
- URL: http://localhost:5555
- Auth: admin:changeme (cambiar en producción)

### Adminer (PostgreSQL UI)
- URL: http://localhost:8080
- Server: db
- User: postgres
- Password: postgres
- Database: mikrom_db

---

## 🔄 Workflow Típico

### Agregar Nueva Feature

1. **Crear rama**
   ```bash
   git checkout -b feature/nueva-feature
   ```

2. **Desarrollo**
   - Modificar código
   - Agregar tests
   - Actualizar docs si es necesario

3. **Tests y Linting**
   ```bash
   make format
   make lint
   make test
   ```

4. **Migración de BD (si aplica)**
   ```bash
   make migrate-create MSG="add new field"
   make migrate-upgrade
   ```

5. **Commit y Push**
   ```bash
   git add .
   git commit -m "feat: descripción de la feature"
   git push origin feature/nueva-feature
   ```

6. **Pull Request**
   - Crear PR en GitLab/GitHub
   - CI/CD se ejecuta automáticamente
   - Esperar aprobación

---

## 🎓 Conceptos Importantes

### Modelo de Ejecución

- **API**: FastAPI async (asyncio)
- **Worker**: Celery sync (prefork/threads/gevent)
- **Database**: SQLModel con soporte async (asyncpg) y sync (psycopg2)

### Estados de VM

1. **PENDING**: Creado en BD, esperando worker
2. **PROVISIONING**: Worker procesando creación
3. **STARTING**: Iniciando VM
4. **RUNNING**: VM activa y accesible
5. **STOPPING**: Deteniendo VM
6. **STOPPED**: VM detenida
7. **RESTARTING**: Reiniciando VM
8. **ERROR**: Error en operación (ver error_message)
9. **DELETING**: Eliminando VM

### Pool de IPs

- Gestión interna en PostgreSQL
- Asignación automática de IPs disponibles
- Liberación al eliminar VM
- Soporte para múltiples pools

### Server-Sent Events (SSE)

- Stream de eventos en tiempo real
- Útil para UI que muestra cambios de estado
- Endpoint: `GET /api/v1/events/sse`

---

## 🔗 Recursos Externos

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLModel Docs](https://sqlmodel.tiangolo.com/)
- [Celery Docs](https://docs.celeryq.dev/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [uv Docs](https://github.com/astral-sh/uv)
- [Firecracker Docs](https://firecracker-microvm.github.io/)

---

## 📄 Licencia

MIT License - Libre para usar como base de tus aplicaciones.

---

**Última actualización**: Febrero 2024  
**Versión del Proyecto**: 0.1.0  
**Python**: 3.12+
