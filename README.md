# Mikrom API

Modern REST API built with **FastAPI**, **SQLModel**, **PostgreSQL**, and managed with **uv**.

## Features

- **FastAPI**: Modern and fast web framework for building APIs
- **SQLModel**: ORM with perfect Pydantic integration
- **PostgreSQL**: Robust relational database
- **JWT Authentication**: Authentication system with access and refresh tokens
- **Async/Await**: Fully asynchronous API
- **Rate Limiting**: Abuse protection with SlowAPI
- **CORS**: Configured for frontend development
- **Logging**: Structured logging system with configurable levels
- **Docker**: Development with Docker Compose
- **Migrations**: Alembic for database versioning
- **Tests**: Test suite with pytest
- **Type Hints**: Fully typed code
- **Validation**: Automatic validation with Pydantic
- **Documentation**: Integrated Swagger UI and ReDoc
- **VM Management**: Firecracker microVM provisioning and management

## Project Structure

```
mikrom-py/
├── .env                        # Environment variables (not in git)
├── .env.example                # Environment variables template
├── .gitignore                  # Files ignored by git
├── pyproject.toml              # uv project configuration
├── docker-compose.yml          # Docker services
├── Dockerfile                  # Application Docker image
├── README.md                   # This documentation
├── alembic.ini                 # Alembic configuration
├── alembic/                    # Migrations directory
│   ├── env.py                  # Migration environment configuration
│   ├── script.py.mako          # Migration template
│   └── versions/               # Migration files
├── mikrom/                     # Main package
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration with Pydantic Settings
│   ├── database.py             # Database configuration
│   ├── dependencies.py         # Global dependencies
│   ├── core/                   # Application core
│   │   ├── __init__.py
│   │   ├── security.py         # JWT, password hashing
│   │   └── exceptions.py       # Custom exceptions
│   ├── models/                 # SQLModel models
│   │   ├── __init__.py
│   │   ├── base.py             # Base model with timestamps
│   │   ├── user.py             # User model
│   │   └── vm.py               # VM model
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── common.py           # Common schemas
│   │   ├── token.py            # Token schemas
│   │   ├── user.py             # User schemas
│   │   └── vm.py               # VM schemas
│   ├── api/                    # API endpoints
│   │   ├── __init__.py
│   │   ├── deps.py             # Endpoint dependencies
│   │   └── v1/                 # API version 1
│   │       ├── __init__.py
│   │       ├── router.py       # Main v1 router
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── auth.py     # Authentication
│   │           ├── users.py    # User CRUD
│   │           ├── vms.py      # VM management
│   │           └── health.py   # Health check
│   ├── clients/                # External service clients
│   │   ├── __init__.py
│   │   └── firecracker.py      # Firecracker deployment client
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── vm_service.py       # VM service
│   │   └── ippool_service.py   # IP Pool management (internal)
│   ├── worker/                 # Background tasks
│   │   ├── __init__.py
│   │   ├── settings.py         # Worker configuration
│   │   └── tasks.py            # Task definitions
│   ├── middleware/             # Custom middleware
│   │   ├── __init__.py
│   │   ├── rate_limit.py       # Rate limiting
│   │   └── logging.py          # Request logging
│   └── utils/                  # Utilities
│       ├── __init__.py
│       └── logger.py           # Logging configuration
└── tests/                      # Tests
    ├── __init__.py
    ├── conftest.py             # Pytest fixtures
    ├── test_api/
    │   ├── __init__.py
    │   ├── test_auth.py        # Authentication tests
    │   ├── test_users.py       # User tests
    │   └── test_vms.py         # VM tests
    ├── test_models/
    │   ├── test_user.py        # User model tests
    │   └── test_vm.py          # VM model tests
    └── test_schemas/
        ├── test_schemas.py     # Schema tests
        └── test_vm_schemas.py  # VM schema tests
```

## Prerequisites

- **Python 3.12+**
- **uv** (package manager): [Installation](https://github.com/astral-sh/uv)
- **Docker and Docker Compose** (optional, for development)
- **PostgreSQL** (if not using Docker)
- **Redis** (if not using Docker, required for VM management)

## Installation

### 1. Clone the repository (if applicable)

```bash
git clone <repository-url>
cd mikrom-py
```

### 2. Configure environment variables

```bash
# Copy example file
cp .env.example .env

# Edit .env with your values
# IMPORTANT: Change SECRET_KEY in production
```

### 3. Install dependencies with uv

```bash
# Install all dependencies
uv sync

# Or install with development dependencies
uv sync --all-groups
```

## Usage

### Option 1: With Docker (Recommended)

```bash
# Start services (PostgreSQL + Redis + Adminer + App + Worker)
docker-compose up -d

# View logs
docker-compose logs -f app

# The API will be available at:
# - API: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
# - Adminer: http://localhost:8080 (DB admin)
```

### Option 2: Local (without Docker)

```bash
# 1. Make sure PostgreSQL is running
# 2. Make sure Redis is running (for VM management)
# 3. Update DATABASE_URL and REDIS_URL in .env

# 4. Run migrations
uv run alembic upgrade head

# 5. Run the application
uv run uvicorn mikrom.main:app --reload --host 0.0.0.0 --port 8000

# 6. Run the worker (in another terminal, for VM management)
uv run python run_worker.py

# The API will be at http://localhost:8000
```

### Option 3: Run directly

```bash
# Run with Python
uv run python -m mikrom.main
```

## Database Migrations

```bash
# Create a new migration automatically
uv run alembic revision --autogenerate -m "Change description"

# Apply migrations
uv run alembic upgrade head

# Revert last migration
uv run alembic downgrade -1

# View migration history
uv run alembic history

# View current state
uv run alembic current
```

## Tests

```bash
# Run all tests (requires PostgreSQL to be running)
make test

# Or with uv directly
uv run pytest

# With coverage
uv run pytest --cov=mikrom --cov-report=html

# Run specific tests
uv run pytest tests/test_api/test_auth.py

# With verbose output
uv run pytest -v
```

**Note:** Tests require PostgreSQL to be running. Start it with:
```bash
docker compose up -d db redis
```

## Development

### Linting and Formatting

```bash
# Run ruff for linting
uv run ruff check .

# Format code with ruff
uv run ruff format .

# Auto-fix issues
uv run ruff check --fix .
```

### Create a Superuser

You can create a superuser by running a Python script:

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

Or use the Makefile:
```bash
make superuser
```

## API Endpoints

### Authentication

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login (OAuth2 form)
- `POST /api/v1/auth/login/json` - Login (JSON body)
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user

### Users

- `GET /api/v1/users` - List users (paginated)
- `GET /api/v1/users/{id}` - Get user by ID
- `PUT /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user (superuser only)

### Virtual Machines

- `POST /api/v1/vms/` - Create new VM
- `GET /api/v1/vms/` - List VMs (paginated, user's own VMs)
- `GET /api/v1/vms/{vm_id}` - Get VM details by VM ID
- `PATCH /api/v1/vms/{vm_id}` - Update VM (name/description)
- `DELETE /api/v1/vms/{vm_id}` - Delete VM

### Utilities

- `GET /` - API information
- `GET /api/v1/health` - Health check
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc

## Usage Examples

### Register a User

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

### Access Protected Endpoint

```bash
# Get token from login
TOKEN="<your-access-token>"

# Use in request
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

### List Users (with pagination)

```bash
curl -X GET "http://localhost:8000/api/v1/users?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

### Create a VM

```bash
curl -X POST "http://localhost:8000/api/v1/vms/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-dev-server",
    "description": "Development environment",
    "vcpu_count": 2,
    "memory_mb": 1024
  }'
```

### List VMs

```bash
curl -X GET "http://localhost:8000/api/v1/vms/?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

### Get VM Details

```bash
curl -X GET "http://localhost:8000/api/v1/vms/srv-a1b2c3d4" \
  -H "Authorization: Bearer $TOKEN"
```

### Delete a VM

```bash
curl -X DELETE "http://localhost:8000/api/v1/vms/srv-a1b2c3d4" \
  -H "Authorization: Bearer $TOKEN"
```

## Configuration

All configurations are managed through environment variables in the `.env` file:

| Variable | Description | Default Value |
|----------|-------------|---------------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://postgres:postgres@localhost:5432/mikrom_db` |
| `SECRET_KEY` | Secret key for JWT | *Required* |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiration | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiration | `7` |
| `API_V1_PREFIX` | API v1 prefix | `/api/v1` |
| `PROJECT_NAME` | Project name | `Mikrom API` |
| `DEBUG` | Debug mode | `False` |
| `ENVIRONMENT` | Environment (development/production) | `production` |
| `BACKEND_CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` |
| `RATE_LIMIT_PER_MINUTE` | Requests limit per minute | `60` |
| `LOG_LEVEL` | Logging level | `INFO` |
| **VM Management** |
| `IPPOOL_DEFAULT_POOL_NAME` | Default IP pool name | `default` |
| `FIRECRACKER_DEPLOY_PATH` | Path to firecracker-deploy repo | - |
| `FIRECRACKER_DEFAULT_HOST` | Default KVM host (optional) | - |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `ARQ_QUEUE_NAME` | Task queue name | `mikrom:queue` |

## Security

### Generate SECRET_KEY

```bash
# Generate a secure secret key
openssl rand -hex 32
```

### Best Practices

- Change `SECRET_KEY` in production
- Use HTTPS in production
- Configure CORS appropriately
- Review rate limiting according to needs
- Keep dependencies updated
- Don't commit `.env` to git

## Docker

### Available Services

```bash
# Start all services
docker-compose up -d

# Only the database
docker-compose up -d db

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes (warning: deletes data!)
docker-compose down -v
```

### Access Adminer

Adminer is a web interface for managing the database:

- URL: http://localhost:8080
- System: PostgreSQL
- Server: db
- User: postgres
- Password: postgres
- Database: mikrom_db

## Useful Commands

The project includes a comprehensive Makefile with useful commands:

```bash
# View all available commands
make help

# Installation
make install          # Install production dependencies
make dev-install      # Install development dependencies

# Development
make run             # Run development server
make worker          # Run background task worker
make shell           # Open Python shell with project loaded

# Testing
make test            # Run all tests
make test-cov        # Run tests with coverage
make test-fast       # Run only fast tests

# Code quality
make lint            # Run linter
make lint-fix        # Run linter with auto-fix
make format          # Format code
make check           # Run all checks (lint + format + test)

# Database
make migrate-create MSG="message"  # Create new migration
make migrate-upgrade              # Apply migrations
make migrate-downgrade            # Revert last migration
make superuser                    # Create superuser
make db-reset                     # Reset database (⚠️ deletes data)

# Docker
make docker-build    # Build Docker images
make docker-up       # Start containers
make docker-down     # Stop containers
make docker-logs     # View logs

# Utilities
make health          # Check API health
make docs           # Open API documentation
make info           # Show project info
```

## VM Management

For detailed information about VM management, see [VM_GUIDE.md](VM_GUIDE.md).

### Prerequisites for VM Management

1. **IP Pool** configured in database (see migration for default pool)
2. **firecracker-deploy** repository configured with target hosts
3. **KVM Server** with SSH access and proper setup
4. **Redis** running for background task queue

### Quick VM Creation Example

```bash
# 1. Login and get token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | jq -r .access_token)

# 2. Create VM
curl -X POST "http://localhost:8000/api/v1/vms/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-vm",
    "vcpu_count": 1,
    "memory_mb": 512
  }'

# 3. Check VM status
curl -X GET "http://localhost:8000/api/v1/vms/srv-XXXXXXXX" \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

### Error: "Can't load plugin: sqlalchemy.dialects:driver"

Make sure that:
1. The `.env` file exists and has the correct `DATABASE_URL`
2. PostgreSQL is running (if using Docker: `docker-compose up -d db`)
3. The URL includes the driver: `postgresql://...` or `postgresql+asyncpg://...`

### Error: "ModuleNotFoundError"

```bash
# Reinstall dependencies
uv sync

# Or clean and reinstall
rm -rf .venv uv.lock
uv sync
```

### Database doesn't connect

```bash
# Verify PostgreSQL is running
docker-compose ps

# View PostgreSQL logs
docker-compose logs db

# Restart services
docker-compose restart
```

### Tests fail

```bash
# Start required services before running tests
docker compose up -d db redis

# Then run tests
make test
```

### VM stuck in "pending" status

```bash
# Check worker logs
docker compose logs worker

# Verify Redis is running
docker compose ps redis

# Check IP pool in database
docker compose exec db psql -U postgres -d mikrom_db -c "SELECT * FROM ip_pools;"
```

## Documentation

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment guide with production setup
- **[VM_GUIDE.md](VM_GUIDE.md)** - VM management usage guide (Spanish)
- **[STATUS.md](STATUS.md)** - Project status and implementation details (Spanish)

## Next Steps

### Features to Implement

- [ ] More granular roles and permissions system
- [ ] Password recovery via email
- [ ] Email verification
- [ ] File upload support
- [ ] Advanced search and filtering
- [ ] Cursor-based pagination
- [ ] WebSockets for real-time notifications
- [ ] Cache with Redis
- [x] Background tasks with arq ✅
- [ ] Monitoring with Prometheus/Grafana

### Security Improvements

- [ ] Implement 2FA (two-factor authentication)
- [ ] Rate limiting per user (not just IP)
- [ ] Token blacklist
- [ ] Audit logging
- [ ] Password strength validation
- [ ] Account lockout after failed attempts

### DevOps

- [ ] CI/CD with GitLab CI
- [ ] Production deployment (AWS/GCP/Azure)
- [ ] Kubernetes manifests
- [ ] Monitoring and alerts
- [ ] Automatic database backup

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [arq Documentation](https://arq-docs.helpmanual.io/)

## License

MIT License - Feel free to use this project as a base for your applications.

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a branch for your feature (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Support

If you encounter any issues or have questions, please open an issue in the repository.

---

**Built with FastAPI, SQLModel, and lots of ☕**
