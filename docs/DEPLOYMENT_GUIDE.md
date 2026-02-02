# 🚀 Mikrom-py Deployment Guide

Complete guide to set up and deploy the **mikrom-py** FastAPI application with VM management capabilities.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Detailed Setup](#detailed-setup)
5. [Configuration](#configuration)
6. [Running the Application](#running-the-application)
7. [VM Management](#vm-management)
8. [Deployment Options](#deployment-options)
9. [Monitoring & Maintenance](#monitoring--maintenance)
10. [Troubleshooting](#troubleshooting)
11. [Production Checklist](#production-checklist)

---

## 🎯 Overview

**mikrom-py** is a modern FastAPI-based REST API that provides:
- **User Authentication** (JWT-based with access and refresh tokens)
- **User Management** (CRUD operations with role-based access)
- **VM Management** (Firecracker microVM provisioning and management)
- **Background Tasks** (Redis + arq for async operations)
- **Database Migrations** (Alembic for schema versioning)

### Architecture

```
┌─────────────┐      ┌─────────────┐      ┌──────────────┐
│   Client    │─────▶│   FastAPI   │─────▶│  PostgreSQL  │
│ (Android/Web)│      │     API     │      │   Database   │
└─────────────┘      └─────────────┘      └──────────────┘
                            │
                            ├──────────────▶┌──────────────┐
                            │               │    Redis     │
                            │               │  (Task Queue)│
                            │               └──────────────┘
                            │                       │
                            ├───────────────────────┘
                            │                       ▼
                            │               ┌──────────────┐
                            │               │  arq Worker  │
                            │               │ (Background) │
                            │               └──────────────┘
                            │                       │
                            ▼                       ▼
                    ┌──────────────┐       ┌──────────────┐
                    │   IP Pool    │       │  Firecracker │
                    │   Service    │       │   Ansible    │
                    └──────────────┘       └──────────────┘
                                                   │
                                                   ▼
                                          ┌──────────────┐
                                          │  KVM Server  │
                                          │   (VMs run)  │
                                          └──────────────┘
```

---

## 📦 Prerequisites

### Required Software

1. **Python 3.12+**
   ```bash
   python --version
   # Should show: Python 3.12.x or higher
   ```

2. **uv Package Manager**
   ```bash
   # Install uv
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Or with pip
   pip install uv
   
   # Verify installation
   uv --version
   ```

3. **Docker & Docker Compose** (recommended for development)
   ```bash
   docker --version
   docker compose version
   ```

4. **PostgreSQL** (if not using Docker)
   ```bash
   # Version 13+ recommended
   psql --version
   ```

5. **Redis** (if not using Docker)
   ```bash
   redis-server --version
   ```

### Required for VM Management

6. **ippool Service** (IP address management)
   - Must be running and accessible
   - Default: `http://localhost:8080`
   - Repository: `../ippool`

7. **firecracker-deploy** (Ansible playbooks)
   - Configured with target hosts
   - Default path: `../firecracker-deploy`
   - Repository: `../firecracker-deploy`

8. **KVM Server** (for running VMs)
   - Linux server with KVM support
   - SSH access configured
   - Network bridge set up

### Verify Prerequisites

```bash
# Check all requirements
python --version          # ≥ 3.12
uv --version             # Latest
docker --version         # ≥ 20.10
docker compose version   # ≥ 2.0
psql --version          # ≥ 13 (optional)
redis-server --version  # ≥ 6.0 (optional)
```

---

## ⚡ Quick Start

For the impatient developer who wants to get running immediately:

```bash
# 1. Clone/navigate to project
cd /path/to/mikrom-py

# 2. Copy environment file
cp .env.example .env

# 3. Edit .env (at minimum, set SECRET_KEY)
nano .env  # or your favorite editor

# 4. Install dependencies
uv sync

# 5. Start services (PostgreSQL + Redis)
docker compose up -d db redis

# 6. Run database migrations
uv run alembic upgrade head

# 7. Create a superuser
make superuser

# 8. Start the API (terminal 1)
make run

# 9. Start the worker (terminal 2)
make worker

# 10. Open browser
open http://localhost:8000/docs
```

**Done!** Your API is running at http://localhost:8000

---

## 🔧 Detailed Setup

### Step 1: Project Setup

```bash
# Navigate to project directory
cd /path/to/mikrom-py

# Verify you're in the right place
ls -la
# Should see: mikrom/, tests/, pyproject.toml, docker-compose.yml, etc.
```

### Step 2: Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit the .env file
nano .env
```

**Minimum required changes:**

```bash
# Generate a secure secret key
openssl rand -hex 32

# Add to .env
SECRET_KEY=<your-generated-key>

# Update database URL if needed (default works with Docker)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mikrom_db
```

**For VM management, also configure:**

```bash
# IP Pool API (adjust port if needed to avoid conflicts)
IPPOOL_API_URL=http://localhost:8090

# Firecracker deployment path (absolute path!)
FIRECRACKER_DEPLOY_PATH=/home/youruser/path/to/firecracker-deploy

# Optional: specify default KVM host
FIRECRACKER_DEFAULT_HOST=your-kvm-server.example.com

# Redis (default works with Docker)
REDIS_URL=redis://localhost:6379
ARQ_QUEUE_NAME=mikrom:queue
```

### Step 3: Install Dependencies

```bash
# Install all dependencies including dev dependencies
uv sync

# Or production only
uv sync --no-dev

# Verify installation
uv pip list
```

### Step 4: Database Setup

**Option A: Using Docker (Recommended)**

```bash
# Start PostgreSQL container
docker compose up -d db

# Wait for database to be ready (check health)
docker compose ps db

# Run migrations
uv run alembic upgrade head

# Verify migration
uv run alembic current
```

**Option B: Using Local PostgreSQL**

```bash
# Create database
createdb mikrom_db

# Or via psql
psql -U postgres
CREATE DATABASE mikrom_db;
\q

# Update .env with your PostgreSQL credentials
DATABASE_URL=postgresql://youruser:yourpass@localhost:5432/mikrom_db

# Run migrations
uv run alembic upgrade head
```

### Step 5: Redis Setup

**Option A: Using Docker (Recommended)**

```bash
# Start Redis container
docker compose up -d redis

# Verify it's running
docker compose ps redis
```

**Option B: Using Local Redis**

```bash
# Start Redis server
redis-server

# Or as a service
sudo systemctl start redis

# Update .env if using non-default settings
REDIS_URL=redis://localhost:6379
```

### Step 6: Create Initial User

```bash
# Interactive superuser creation
make superuser

# Follow prompts:
# Email: admin@example.com
# Username: admin
# Password: <your-secure-password>
# Full Name: Administrator
```

**Or create user programmatically:**

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
        hashed_password=get_password_hash('your-password'),
        full_name='Administrator',
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    print(f'Superuser created: {user.username}')
"
```

---

## ⚙️ Configuration

### Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| **Database** |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/mikrom_db` | ✅ |
| `DATABASE_ECHO` | Log SQL queries | `False` | ❌ |
| **Security** |
| `SECRET_KEY` | JWT secret key (use `openssl rand -hex 32`) | - | ✅ |
| `ALGORITHM` | JWT algorithm | `HS256` | ❌ |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` | ❌ |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` | ❌ |
| **API** |
| `API_V1_PREFIX` | API version prefix | `/api/v1` | ❌ |
| `PROJECT_NAME` | Application name | `Mikrom API` | ❌ |
| `VERSION` | API version | `1.0.0` | ❌ |
| `DEBUG` | Debug mode | `False` | ❌ |
| `ENVIRONMENT` | Environment name | `production` | ❌ |
| **CORS** |
| `BACKEND_CORS_ORIGINS` | Allowed origins (JSON array) | `["http://localhost:3000"]` | ❌ |
| **Rate Limiting** |
| `RATE_LIMIT_PER_MINUTE` | Max requests per minute | `60` | ❌ |
| **Logging** |
| `LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) | `INFO` | ❌ |
| **VM Management** |
| `IPPOOL_API_URL` | IP Pool service URL | `http://localhost:8080` | ⚠️ * |
| `FIRECRACKER_DEPLOY_PATH` | Path to firecracker-deploy repo | - | ⚠️ * |
| `FIRECRACKER_DEFAULT_HOST` | Default KVM host (optional) | - | ❌ |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` | ⚠️ * |
| `ARQ_QUEUE_NAME` | Task queue name | `mikrom:queue` | ❌ |

\* Required if using VM management features

### Security Configuration

**Generate SECRET_KEY:**
```bash
openssl rand -hex 32
```

**Configure CORS for your frontend:**
```bash
# In .env
BACKEND_CORS_ORIGINS=["http://localhost:3000","https://yourdomain.com"]
```

**Adjust token expiration:**
```bash
# Short-lived access tokens (30 min)
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Long-lived refresh tokens (7 days)
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Database Configuration

**Standard PostgreSQL:**
```bash
DATABASE_URL=postgresql://user:password@host:port/database
```

**With asyncpg driver (for better async performance):**
```bash
DATABASE_URL=postgresql+asyncpg://user:password@host:port/database
```

**Unix socket connection:**
```bash
DATABASE_URL=postgresql://user:password@/database?host=/var/run/postgresql
```

### VM Management Configuration

**Configure IP Pool:**
```bash
# If ippool runs on different port to avoid Adminer conflict
IPPOOL_API_URL=http://localhost:8090
```

**Configure Firecracker deployment:**
```bash
# Absolute path to firecracker-deploy repository
FIRECRACKER_DEPLOY_PATH=/home/user/mikrom/firecracker-deploy

# Optional: specify a single default host
FIRECRACKER_DEFAULT_HOST=kvm-server-01.example.com
```

**Configure Redis:**
```bash
# Standard connection
REDIS_URL=redis://localhost:6379

# With password
REDIS_URL=redis://:password@localhost:6379

# Redis Cluster
REDIS_URL=redis://localhost:6379/0
```

---

## 🏃 Running the Application

### Development Mode (Recommended)

Run each component in a separate terminal for easier debugging:

**Terminal 1: Services**
```bash
# Start PostgreSQL + Redis + Adminer
docker compose up -d db redis adminer

# Check status
docker compose ps
```

**Terminal 2: API Server**
```bash
# Start API with auto-reload on code changes
make run

# Or manually
uv run uvicorn mikrom.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3: Background Worker** (if using VM management)
```bash
# Start arq worker
make worker

# Or manually
uv run python run_worker.py
```

**Access the application:**
- **API:** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Adminer:** http://localhost:8080 (database admin)

### Production Mode

**Option A: Docker Compose (All-in-one)**

```bash
# Build images
docker compose build

# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

**Option B: Systemd Services (Linux)**

Create systemd service files:

**/etc/systemd/system/mikrom-api.service:**
```ini
[Unit]
Description=Mikrom API Service
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=mikrom
WorkingDirectory=/opt/mikrom-py
Environment="PATH=/opt/mikrom-py/.venv/bin"
ExecStart=/opt/mikrom-py/.venv/bin/uvicorn mikrom.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**/etc/systemd/system/mikrom-worker.service:**
```ini
[Unit]
Description=Mikrom Background Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=mikrom
WorkingDirectory=/opt/mikrom-py
Environment="PATH=/opt/mikrom-py/.venv/bin"
ExecStart=/opt/mikrom-py/.venv/bin/python run_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start services:**
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable mikrom-api mikrom-worker

# Start services
sudo systemctl start mikrom-api mikrom-worker

# Check status
sudo systemctl status mikrom-api
sudo systemctl status mikrom-worker

# View logs
sudo journalctl -u mikrom-api -f
sudo journalctl -u mikrom-worker -f
```

### Using Makefile Commands

The project includes a comprehensive Makefile with useful commands:

```bash
# View all available commands
make help

# Common development commands
make dev-install     # Install dependencies
make run            # Run API server
make worker         # Run background worker
make test           # Run tests
make lint           # Check code quality
make format         # Format code
make migrate-upgrade # Apply migrations

# Docker commands
make docker-up      # Start all containers
make docker-down    # Stop all containers
make docker-logs    # View logs

# Database commands
make migrate-create MSG="your message"  # Create migration
make migrate-upgrade                     # Apply migrations
make superuser                          # Create superuser
make db-reset                           # Reset database (⚠️ deletes data)

# Testing
make test           # Run all tests
make test-cov       # Run tests with coverage
make test-fast      # Run fast tests only

# Utilities
make health         # Check API health
make docs          # Open API documentation
make info          # Show project info
```

---

## 🖥️ VM Management

### Prerequisites for VM Management

Before creating VMs, ensure these external services are running:

1. **IP Pool Service**
   ```bash
   cd ../ippool
   # Start ippool service (refer to ippool documentation)
   # Ensure it's accessible at http://localhost:8090
   ```

2. **Firecracker Deploy**
   ```bash
   cd ../firecracker-deploy
   
   # Configure inventory with your KVM hosts
   nano inventory/hosts.yml
   
   # Test SSH access
   ansible all -m ping
   
   # Set up network (first time only)
   make network-setup
   
   # Create rootfs template (first time only)
   make template-create
   ```

3. **KVM Server**
   - Ensure KVM is installed and enabled
   - Network bridge configured
   - SSH access working with your SSH key

### Creating VMs via API

**Step 1: Authenticate**
```bash
# Login to get access token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your-password"

# Response contains access_token
export TOKEN="<your-access-token>"
```

**Step 2: Create a VM**
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

**Response:**
```json
{
  "id": 1,
  "vm_id": "srv-a1b2c3d4",
  "name": "my-dev-server",
  "description": "Development environment",
  "vcpu_count": 2,
  "memory_mb": 1024,
  "ip_address": null,
  "status": "pending",
  "host": null,
  "user_id": 1,
  "created_at": "2024-02-01T10:00:00Z",
  "updated_at": "2024-02-01T10:00:00Z"
}
```

**Step 3: Monitor VM Creation**

The VM creation happens asynchronously in the background worker. Monitor progress:

```bash
# Check VM status (use vm_id, not database id)
curl -X GET "http://localhost:8000/api/v1/vms/srv-a1b2c3d4" \
  -H "Authorization: Bearer $TOKEN"
```

**Status progression:**
1. `pending` → VM request created
2. `provisioning` → IP allocated, VM being created
3. `running` → VM successfully created and running
4. `error` → Something went wrong (check error_message)

**When provisioning completes:**
```json
{
  "vm_id": "srv-a1b2c3d4",
  "name": "my-dev-server",
  "ip_address": "172.16.0.10",
  "status": "running",
  "host": "kvm-server-01.example.com",
  ...
}
```

**Step 4: List All VMs**
```bash
curl -X GET "http://localhost:8000/api/v1/vms/?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

**Step 5: Update VM (name/description only)**
```bash
curl -X PATCH "http://localhost:8000/api/v1/vms/srv-a1b2c3d4" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-production-server",
    "description": "Production environment"
  }'
```

**Step 6: Connect to VM**
```bash
# SSH into the VM using assigned IP
ssh debian@172.16.0.10

# Default credentials (configured in firecracker-deploy)
# Username: debian
# Password: debian
```

**Step 7: Delete VM**
```bash
# Delete VM (async operation)
curl -X DELETE "http://localhost:8000/api/v1/vms/srv-a1b2c3d4" \
  -H "Authorization: Bearer $TOKEN"

# Response: 202 Accepted
{
  "message": "VM deletion started",
  "vm_id": "srv-a1b2c3d4"
}
```

The deletion process:
1. VM status changes to `deleting`
2. Background worker stops the VM
3. IP address is released back to pool
4. VM record is removed from database

### VM Resource Limits

Current resource limits (configured in schemas):

- **vCPU:** 1-32 cores
- **Memory:** 512 MB - 32 GB (32768 MB)
- **Name:** 1-64 characters (alphanumeric, hyphens, underscores)

---

## 🚢 Deployment Options

### Option 1: Docker Compose (Recommended for small deployments)

**Advantages:**
- Simple setup
- All services containerized
- Easy to reproduce
- Good for development and small production

**Setup:**
```bash
# 1. Configure .env
cp .env.example .env
nano .env  # Set SECRET_KEY and other vars

# 2. Build and start
docker compose up -d

# 3. Run migrations
docker compose exec app alembic upgrade head

# 4. Create superuser
docker compose exec app python -c "..."

# 5. Access
# API: http://localhost:8000
# Adminer: http://localhost:8080
```

**Production considerations:**
- Use Docker secrets for sensitive data
- Configure restart policies
- Set up log rotation
- Use volumes for persistent data
- Configure health checks

### Option 2: Systemd Services (Recommended for production)

**Advantages:**
- Native Linux integration
- Better resource control
- Easier monitoring
- More flexible

**Setup:**
See [Running the Application → Production Mode](#production-mode) section above.

### Option 3: Kubernetes

**For large-scale deployments:**

```yaml
# Example k8s deployment (basic)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mikrom-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mikrom-api
  template:
    metadata:
      labels:
        app: mikrom-api
    spec:
      containers:
      - name: api
        image: mikrom-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mikrom-secrets
              key: database-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: mikrom-secrets
              key: secret-key
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mikrom-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mikrom-worker
  template:
    metadata:
      labels:
        app: mikrom-worker
    spec:
      containers:
      - name: worker
        image: mikrom-api:latest
        command: ["python", "run_worker.py"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: mikrom-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: mikrom-secrets
              key: redis-url
```

### Option 4: Behind Nginx Reverse Proxy

**Production setup with Nginx:**

```nginx
# /etc/nginx/sites-available/mikrom-api
server {
    listen 80;
    server_name api.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL certificates (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Logging
    access_log /var/log/nginx/mikrom-api-access.log;
    error_log /var/log/nginx/mikrom-api-error.log;

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req zone=api_limit burst=20 nodelay;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

**Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/mikrom-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📊 Monitoring & Maintenance

### Health Checks

**API Health Endpoint:**
```bash
# Quick health check
curl http://localhost:8000/api/v1/health

# Expected response
{
  "status": "healthy",
  "timestamp": "2024-02-01T10:00:00Z",
  "database": "connected",
  "version": "1.0.0"
}
```

**Service Status:**
```bash
# Check all services (Docker)
docker compose ps

# Check specific service
docker compose ps db
docker compose ps redis
docker compose ps worker

# Check systemd services
sudo systemctl status mikrom-api
sudo systemctl status mikrom-worker
```

### Viewing Logs

**Docker Compose:**
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f app
docker compose logs -f worker
docker compose logs -f db

# Last N lines
docker compose logs --tail=100 app

# Since timestamp
docker compose logs --since 2024-02-01T10:00:00 app
```

**Systemd:**
```bash
# Follow logs
sudo journalctl -u mikrom-api -f
sudo journalctl -u mikrom-worker -f

# Last N lines
sudo journalctl -u mikrom-api -n 100

# Since timestamp
sudo journalctl -u mikrom-api --since "2024-02-01 10:00:00"

# Filter by priority
sudo journalctl -u mikrom-api -p err
```

**Application Logs:**
```bash
# If logging to file (configure in config.py)
tail -f /var/log/mikrom/api.log
tail -f /var/log/mikrom/worker.log
```

### Database Maintenance

**Backup Database:**
```bash
# Using Docker
docker compose exec db pg_dump -U postgres mikrom_db > backup_$(date +%Y%m%d).sql

# Local PostgreSQL
pg_dump -U postgres mikrom_db > backup_$(date +%Y%m%d).sql

# With compression
pg_dump -U postgres mikrom_db | gzip > backup_$(date +%Y%m%d).sql.gz
```

**Restore Database:**
```bash
# Using Docker
docker compose exec -T db psql -U postgres mikrom_db < backup.sql

# Local PostgreSQL
psql -U postgres mikrom_db < backup.sql

# From compressed
gunzip < backup.sql.gz | psql -U postgres mikrom_db
```

**Vacuum Database (maintenance):**
```bash
# Using Docker
docker compose exec db psql -U postgres -d mikrom_db -c "VACUUM ANALYZE;"

# Local PostgreSQL
psql -U postgres -d mikrom_db -c "VACUUM ANALYZE;"
```

### Redis Maintenance

**Check Redis Status:**
```bash
# Using Docker
docker compose exec redis redis-cli ping
# Should return: PONG

# Check queue size
docker compose exec redis redis-cli llen "arq:queue:mikrom:queue"

# Monitor Redis in real-time
docker compose exec redis redis-cli monitor
```

**Clear Redis Queue (if needed):**
```bash
# Flush specific queue
docker compose exec redis redis-cli del "arq:queue:mikrom:queue"

# Flush all Redis data (⚠️ careful!)
docker compose exec redis redis-cli flushall
```

### Database Migrations

**Check Current Migration:**
```bash
uv run alembic current
```

**View Migration History:**
```bash
uv run alembic history
```

**Apply New Migrations:**
```bash
uv run alembic upgrade head
```

**Rollback Migration:**
```bash
# Rollback one version
uv run alembic downgrade -1

# Rollback to specific version
uv run alembic downgrade <revision>
```

**Create New Migration:**
```bash
# Auto-generate from model changes
make migrate-create MSG="add new feature"

# Or manually
uv run alembic revision --autogenerate -m "add new feature"
```

### Automated Backups (Cron)

Add to crontab:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/backup-script.sh
```

**backup-script.sh:**
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/mikrom"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
docker compose exec -T db pg_dump -U postgres mikrom_db | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete

# Log
echo "Backup completed: $DATE" >> $BACKUP_DIR/backup.log
```

Make executable:
```bash
chmod +x /path/to/backup-script.sh
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "Can't connect to database"

**Symptoms:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solutions:**
```bash
# Check if PostgreSQL is running
docker compose ps db
# or
sudo systemctl status postgresql

# Check DATABASE_URL in .env
cat .env | grep DATABASE_URL

# Test connection manually
docker compose exec db psql -U postgres -d mikrom_db
# or
psql -U postgres -d mikrom_db

# Restart database
docker compose restart db
# or
sudo systemctl restart postgresql
```

#### 2. "Can't connect to Redis"

**Symptoms:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions:**
```bash
# Check if Redis is running
docker compose ps redis
# or
sudo systemctl status redis

# Test connection
docker compose exec redis redis-cli ping
# or
redis-cli ping

# Restart Redis
docker compose restart redis
# or
sudo systemctl restart redis
```

#### 3. "Worker not processing tasks"

**Symptoms:**
- VMs stuck in "pending" status
- Background tasks not executing

**Solutions:**
```bash
# Check if worker is running
docker compose ps worker
# or
ps aux | grep run_worker.py

# Check worker logs
docker compose logs worker
# or
sudo journalctl -u mikrom-worker -n 50

# Verify Redis queue
docker compose exec redis redis-cli llen "arq:queue:mikrom:queue"

# Restart worker
docker compose restart worker
# or
sudo systemctl restart mikrom-worker
```

#### 4. "Migration conflicts"

**Symptoms:**
```
alembic.util.exc.CommandError: Target database is not up to date
```

**Solutions:**
```bash
# Check current migration
uv run alembic current

# Check migration history
uv run alembic history

# Stamp database to specific version (if needed)
uv run alembic stamp head

# Downgrade and re-upgrade
uv run alembic downgrade -1
uv run alembic upgrade head
```

#### 5. "VM creation fails"

**Symptoms:**
- VM status shows "error"
- Error message in VM record

**Check list:**
```bash
# 1. Check if ippool is running
curl http://localhost:8090/health

# 2. Check firecracker-deploy path
ls -la $FIRECRACKER_DEPLOY_PATH

# 3. Check SSH access to KVM server
ssh user@kvm-server-01.example.com "hostname"

# 4. Check worker logs
docker compose logs worker | grep ERROR

# 5. Test Ansible playbook manually
cd $FIRECRACKER_DEPLOY_PATH
ansible-playbook playbooks/create-vm.yml -e "vm_id=test-vm vcpu=1 mem=256"

# 6. Check IP pool has available IPs
curl http://localhost:8090/api/v1/pools
```

#### 6. "Port already in use"

**Symptoms:**
```
Error starting userland proxy: listen tcp 0.0.0.0:8000: bind: address already in use
```

**Solutions:**
```bash
# Find process using the port
sudo lsof -i :8000
# or
sudo netstat -tlnp | grep 8000

# Kill the process
sudo kill -9 <PID>

# Or use different port
# In docker-compose.yml, change:
# ports:
#   - "8001:8000"  # external:internal
```

#### 7. "Permission denied" errors

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/path/to/file'
```

**Solutions:**
```bash
# Fix file ownership
sudo chown -R $USER:$USER /path/to/mikrom-py

# Fix firecracker-deploy permissions
sudo chown -R $USER:$USER $FIRECRACKER_DEPLOY_PATH

# Ensure .env is readable
chmod 600 .env

# Fix log directory permissions (if logging to file)
sudo mkdir -p /var/log/mikrom
sudo chown -R $USER:$USER /var/log/mikrom
```

#### 8. "Module not found" errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'mikrom'
```

**Solutions:**
```bash
# Reinstall dependencies
rm -rf .venv uv.lock
uv sync

# Verify installation
uv pip list | grep mikrom

# Make sure you're in project root
pwd  # Should be /path/to/mikrom-py

# Run with uv
uv run python -m mikrom.main
```

### Debug Mode

**Enable debug logging:**

```bash
# In .env
DEBUG=True
LOG_LEVEL=DEBUG

# Restart services
docker compose restart app worker
```

**Check detailed logs:**
```bash
# API logs
docker compose logs -f app

# Worker logs
docker compose logs -f worker

# Database logs
docker compose logs -f db
```

### Testing Components

**Test database connection:**
```bash
uv run python -c "
from mikrom.database import engine
from sqlmodel import text, Session

with Session(engine) as session:
    result = session.exec(text('SELECT version()')).first()
    print(f'PostgreSQL version: {result}')
"
```

**Test Redis connection:**
```bash
uv run python -c "
import redis
from mikrom.config import get_settings

settings = get_settings()
r = redis.from_url(settings.REDIS_URL)
print(f'Redis ping: {r.ping()}')
"
```

**Test IP Pool connection:**
```bash
curl -v http://localhost:8090/api/v1/health
```

**Test Ansible connectivity:**
```bash
cd $FIRECRACKER_DEPLOY_PATH
ansible all -m ping -i inventory/hosts.yml
```

---

## ✅ Production Checklist

### Security

- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set `DEBUG=False` in production
- [ ] Configure CORS origins appropriately
- [ ] Use HTTPS (SSL/TLS certificates)
- [ ] Enable firewall rules (allow only necessary ports)
- [ ] Set strong passwords for PostgreSQL
- [ ] Use Redis password if exposed
- [ ] Keep dependencies up to date
- [ ] Review and adjust rate limiting
- [ ] Implement API key rotation policy
- [ ] Set up security monitoring

### Infrastructure

- [ ] PostgreSQL is backed up regularly
- [ ] Redis persistence is configured
- [ ] Log rotation is set up
- [ ] Monitoring is in place
- [ ] Health checks are configured
- [ ] Auto-restart on failure
- [ ] Resource limits are set (Docker/systemd)
- [ ] Separate database server (recommended)
- [ ] Load balancer configured (if needed)
- [ ] CDN for static files (if applicable)

### Application

- [ ] All migrations are applied
- [ ] Environment variables are configured
- [ ] Worker is running
- [ ] Email service configured (if using)
- [ ] External services are accessible (ippool, firecracker-deploy)
- [ ] SSH keys for KVM servers are set up
- [ ] Test VM creation works end-to-end
- [ ] Documentation is up to date
- [ ] Error tracking is configured (Sentry, etc.)
- [ ] Performance monitoring is active

### Testing

- [ ] All tests pass (`make test`)
- [ ] Load testing completed
- [ ] API endpoints tested
- [ ] VM lifecycle tested (create/delete)
- [ ] Backup/restore tested
- [ ] Failover tested
- [ ] Rollback procedure tested

### Monitoring

- [ ] API health endpoint monitored
- [ ] Database performance monitored
- [ ] Worker queue size monitored
- [ ] Disk space monitored
- [ ] Memory usage monitored
- [ ] CPU usage monitored
- [ ] Logs are aggregated
- [ ] Alerts are configured
- [ ] On-call schedule defined

### Documentation

- [ ] API documentation is accessible
- [ ] Deployment runbook created
- [ ] Incident response plan documented
- [ ] Architecture diagrams updated
- [ ] Credentials stored securely
- [ ] Contact information updated

---

## 📚 Additional Resources

### Documentation

- **FastAPI:** https://fastapi.tiangolo.com/
- **SQLModel:** https://sqlmodel.tiangolo.com/
- **Pydantic:** https://docs.pydantic.dev/
- **Alembic:** https://alembic.sqlalchemy.org/
- **uv:** https://github.com/astral-sh/uv
- **arq:** https://arq-docs.helpmanual.io/

### Project Files

- **API Documentation:** http://localhost:8000/docs (when running)
- **README:** `README.md` (Spanish, general overview)
- **VM Guide:** `VM_GUIDE.md` (Spanish, VM-specific usage)
- **This Guide:** `DEPLOYMENT_GUIDE.md` (English, deployment)

### Getting Help

1. Check the troubleshooting section above
2. Review application logs
3. Check GitHub issues (if public repo)
4. Contact the development team

---

## 🎉 Success!

If you've followed this guide, you should now have:

✅ **mikrom-py API** running and accessible  
✅ **PostgreSQL** database configured and migrated  
✅ **Redis** queue for background tasks  
✅ **Background worker** processing VM operations  
✅ **Monitoring and logging** in place  
✅ **Ready for production** deployment  

**Next Steps:**
1. Create your first user
2. Test VM creation
3. Integrate with Android app
4. Monitor and optimize
5. Scale as needed

**Questions or issues?** Review the troubleshooting section or check the logs!

---

*Last updated: February 2024*  
*Version: 1.0.0*
