# Mikrom API

REST API moderna construida con **FastAPI**, **SQLModel**, **PostgreSQL** y gestionada con **uv**.

## Características

- **FastAPI**: Framework web moderno y rápido para construir APIs
- **SQLModel**: ORM con integración perfecta con Pydantic
- **PostgreSQL**: Base de datos relacional robusta
- **JWT Authentication**: Sistema de autenticación con tokens de acceso y refresh
- **Async/Await**: API completamente asíncrona
- **Rate Limiting**: Protección contra abuso con SlowAPI
- **CORS**: Configurado para desarrollo frontend
- **Logging**: Sistema de logs estructurado con niveles configurables
- **Docker**: Desarrollo con Docker Compose
- **Migraciones**: Alembic para versionado de base de datos
- **Tests**: Suite de tests con pytest
- **Type Hints**: Código completamente tipado
- **Validación**: Validación automática con Pydantic
- **Documentación**: Swagger UI y ReDoc integrados

## Estructura del Proyecto

```
mikrom-py/
├── .env                        # Variables de entorno (no en git)
├── .env.example                # Plantilla de variables de entorno
├── .gitignore                  # Archivos ignorados por git
├── pyproject.toml              # Configuración del proyecto uv
├── docker-compose.yml          # Servicios Docker
├── Dockerfile                  # Imagen Docker de la aplicación
├── README.md                   # Esta documentación
├── alembic.ini                 # Configuración de Alembic
├── alembic/                    # Directorio de migraciones
│   ├── env.py                  # Configuración de entorno de migraciones
│   ├── script.py.mako          # Template de migraciones
│   └── versions/               # Archivos de migración
├── mikrom/                     # Paquete principal
│   ├── __init__.py
│   ├── main.py                 # Aplicación FastAPI
│   ├── config.py               # Configuración con Pydantic Settings
│   ├── database.py             # Configuración de base de datos
│   ├── dependencies.py         # Dependencias globales
│   ├── core/                   # Núcleo de la aplicación
│   │   ├── __init__.py
│   │   ├── security.py         # JWT, hashing de passwords
│   │   └── exceptions.py       # Excepciones personalizadas
│   ├── models/                 # Modelos SQLModel
│   │   ├── __init__.py
│   │   ├── base.py             # Modelo base con timestamps
│   │   └── user.py             # Modelo de usuario
│   ├── schemas/                # Schemas Pydantic
│   │   ├── __init__.py
│   │   ├── common.py           # Schemas comunes
│   │   ├── token.py            # Schemas de tokens
│   │   └── user.py             # Schemas de usuario
│   ├── api/                    # Endpoints de la API
│   │   ├── __init__.py
│   │   ├── deps.py             # Dependencias de endpoints
│   │   └── v1/                 # API versión 1
│   │       ├── __init__.py
│   │       ├── router.py       # Router principal v1
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── auth.py     # Autenticación
│   │           ├── users.py    # CRUD de usuarios
│   │           └── health.py   # Health check
│   ├── middleware/             # Middleware personalizado
│   │   ├── __init__.py
│   │   ├── rate_limit.py       # Rate limiting
│   │   └── logging.py          # Logging de requests
│   └── utils/                  # Utilidades
│       ├── __init__.py
│       └── logger.py           # Configuración de logging
└── tests/                      # Tests
    ├── __init__.py
    ├── conftest.py             # Fixtures de pytest
    └── test_api/
        ├── __init__.py
        └── test_auth.py        # Tests de autenticación
```

## Requisitos Previos

- **Python 3.12+**
- **uv** (gestor de paquetes): [Instalación](https://github.com/astral-sh/uv)
- **Docker y Docker Compose** (opcional, para desarrollo)
- **PostgreSQL** (si no usas Docker)

## Instalación

### 1. Clonar el repositorio (si aplica)

```bash
git clone <repository-url>
cd mikrom-py
```

### 2. Configurar variables de entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env con tus valores
# IMPORTANTE: Cambia el SECRET_KEY en producción
```

### 3. Instalar dependencias con uv

```bash
# Instalar todas las dependencias
uv sync

# O instalar con dependencias de desarrollo
uv sync --all-groups
```

## Uso

### Opción 1: Con Docker (Recomendado)

```bash
# Levantar servicios (PostgreSQL + Adminer + App)
docker-compose up -d

# Ver logs
docker-compose logs -f app

# La API estará disponible en:
# - API: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
# - Adminer: http://localhost:8080 (admin BD)
```

### Opción 2: Local (sin Docker)

```bash
# 1. Asegúrate de tener PostgreSQL corriendo
# 2. Actualiza DATABASE_URL en .env

# 3. Ejecutar migraciones
uv run alembic upgrade head

# 4. Ejecutar la aplicación
uv run uvicorn mikrom.main:app --reload --host 0.0.0.0 --port 8000

# La API estará en http://localhost:8000
```

### Opción 3: Ejecutar directamente

```bash
# Ejecutar con Python
uv run python -m mikrom.main
```

## Migraciones de Base de Datos

```bash
# Crear una nueva migración automáticamente
uv run alembic revision --autogenerate -m "Descripción del cambio"

# Aplicar migraciones
uv run alembic upgrade head

# Revertir última migración
uv run alembic downgrade -1

# Ver historial de migraciones
uv run alembic history

# Ver estado actual
uv run alembic current
```

## Tests

```bash
# Ejecutar todos los tests
uv run pytest

# Con coverage
uv run pytest --cov=mikrom --cov-report=html

# Ejecutar tests específicos
uv run pytest tests/test_api/test_auth.py

# Con output verbose
uv run pytest -v
```

## Desarrollo

### Linting y Formateo

```bash
# Ejecutar ruff para linting
uv run ruff check .

# Formatear código con ruff
uv run ruff format .

# Fix automático de issues
uv run ruff check --fix .
```

### Crear un Superusuario

Puedes crear un superusuario ejecutando un script Python:

```bash
uv run python -c "
from mikrom.database import sync_engine
from mikrom.models import User
from mikrom.core.security import get_password_hash
from sqlmodel import Session

with Session(sync_engine) as session:
    user = User(
        email='admin@example.com',
        username='admin',
        hashed_password=get_password_hash('admin123'),
        full_name='Administrator',
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    print(f'Superuser created: {user.username}')
"
```

## API Endpoints

### Autenticación

- `POST /api/v1/auth/register` - Registrar nuevo usuario
- `POST /api/v1/auth/login` - Login (OAuth2 form)
- `POST /api/v1/auth/login/json` - Login (JSON body)
- `POST /api/v1/auth/refresh` - Refrescar access token
- `GET /api/v1/auth/me` - Obtener usuario actual

### Usuarios

- `GET /api/v1/users` - Listar usuarios (paginado)
- `GET /api/v1/users/{id}` - Obtener usuario por ID
- `PUT /api/v1/users/{id}` - Actualizar usuario
- `DELETE /api/v1/users/{id}` - Eliminar usuario (solo superuser)

### Utilidades

- `GET /` - Información de la API
- `GET /api/v1/health` - Health check
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc

## Ejemplos de Uso

### Registrar un Usuario

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "johndoe",
    "password": "SecureP@ssw0rd",
    "full_name": "John Doe"
  }'
```

### Login

```bash
# OAuth2 form
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=johndoe&password=SecureP@ssw0rd"

# JSON body
curl -X POST "http://localhost:8000/api/v1/auth/login/json" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "password": "SecureP@ssw0rd"
  }'
```

### Acceder a Endpoint Protegido

```bash
# Obtener token del login
TOKEN="<tu-access-token>"

# Usar en request
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

### Listar Usuarios (con paginación)

```bash
curl -X GET "http://localhost:8000/api/v1/users?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

## Configuración

Todas las configuraciones se gestionan mediante variables de entorno en el archivo `.env`:

| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `DATABASE_URL` | URL de conexión a PostgreSQL | `postgresql://postgres:postgres@localhost:5432/mikrom_db` |
| `SECRET_KEY` | Clave secreta para JWT | *Requerido* |
| `ALGORITHM` | Algoritmo de JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración del access token | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Expiración del refresh token | `7` |
| `API_V1_PREFIX` | Prefijo de la API v1 | `/api/v1` |
| `PROJECT_NAME` | Nombre del proyecto | `Mikrom API` |
| `DEBUG` | Modo debug | `False` |
| `ENVIRONMENT` | Entorno (development/production) | `production` |
| `BACKEND_CORS_ORIGINS` | Orígenes CORS permitidos | `["http://localhost:3000"]` |
| `RATE_LIMIT_PER_MINUTE` | Límite de requests por minuto | `60` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

## Seguridad

### Generar SECRET_KEY

```bash
# Generar una clave secreta segura
openssl rand -hex 32
```

### Buenas Prácticas

- Cambiar `SECRET_KEY` en producción
- Usar HTTPS en producción
- Configurar CORS apropiadamente
- Revisar rate limiting según necesidades
- Mantener dependencias actualizadas
- No commitear `.env` a git

## Docker

### Servicios Disponibles

```bash
# Levantar todos los servicios
docker-compose up -d

# Solo la base de datos
docker-compose up -d db

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down

# Detener y eliminar volúmenes (¡cuidado, elimina datos!)
docker-compose down -v
```

### Acceder a Adminer

Adminer es una interfaz web para gestionar la base de datos:

- URL: http://localhost:8080
- Sistema: PostgreSQL
- Servidor: db
- Usuario: postgres
- Password: postgres
- Base de datos: mikrom_db

## Comandos Útiles

```bash
# Ver versión de uv
uv --version

# Actualizar dependencias
uv sync --upgrade

# Agregar nueva dependencia
uv add <paquete>

# Agregar dependencia de desarrollo
uv add --dev <paquete>

# Eliminar dependencia
uv remove <paquete>

# Ver dependencias instaladas
uv pip list

# Ejecutar comando en el entorno virtual
uv run <comando>

# Activar entorno virtual manualmente
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

## Troubleshooting

### Error: "Can't load plugin: sqlalchemy.dialects:driver"

Asegúrate de que:
1. El archivo `.env` existe y tiene `DATABASE_URL` correcta
2. PostgreSQL está corriendo (si usas Docker: `docker-compose up -d db`)
3. La URL incluye el driver: `postgresql://...` o `postgresql+asyncpg://...`

### Error: "ModuleNotFoundError"

```bash
# Reinstalar dependencias
uv sync

# O limpiar y reinstalar
rm -rf .venv uv.lock
uv sync
```

### Base de datos no conecta

```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps

# Ver logs de PostgreSQL
docker-compose logs db

# Reiniciar servicios
docker-compose restart
```

### Tests fallan

```bash
# Crear base de datos de test
# Conectarse a PostgreSQL y ejecutar:
# CREATE DATABASE mikrom_test_db;

# O modificar conftest.py para usar SQLite en tests
```

## Próximos Pasos

### Funcionalidades a Implementar

- [ ] Sistema de roles y permisos más granular
- [ ] Recuperación de contraseña por email
- [ ] Verificación de email
- [ ] Soporte para upload de archivos
- [ ] Búsqueda y filtrado avanzado
- [ ] Paginación con cursor
- [ ] WebSockets para notificaciones en tiempo real
- [ ] Cache con Redis
- [ ] Background tasks con Celery
- [ ] Monitoring con Prometheus/Grafana

### Mejoras de Seguridad

- [ ] Implementar 2FA (autenticación de dos factores)
- [ ] Rate limiting por usuario (no solo IP)
- [ ] Blacklist de tokens
- [ ] Audit logging
- [ ] Password strength validation
- [ ] Account lockout después de intentos fallidos

### DevOps

- [ ] CI/CD con GitHub Actions
- [ ] Deployment a producción (AWS/GCP/Azure)
- [ ] Kubernetes manifests
- [ ] Monitoring y alertas
- [ ] Backup automático de base de datos

## Recursos

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [uv Documentation](https://github.com/astral-sh/uv)

## Licencia

MIT License - Siéntete libre de usar este proyecto como base para tus aplicaciones.

## Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork del repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit de cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Soporte

Si encuentras algún problema o tienes preguntas, por favor abre un issue en el repositorio.

---

**Desarrollado con FastAPI, SQLModel, y mucho café.**
