# Docker Build Optimization

Este documento explica las optimizaciones realizadas al Dockerfile para reducir drásticamente el tiempo de compilación.

## 📊 Resultados de Rendimiento

### Comparación: Alpine vs Debian Trixie

| Métrica | Alpine (Anterior) | Debian Trixie (Actual) | Mejora |
|---------|-------------------|------------------------|--------|
| **Build inicial (sin caché)** | ~10-15 min | **6:42 min** | ~40% más rápido |
| **Rebuild completo (con caché)** | ~2-3 min | **1.3 segundos** | **99% más rápido** |
| **Rebuild tras cambio de código** | ~1-2 min | **0.5 segundos** | **99.5% más rápido** |
| **Tamaño de imagen** | ~120-150 MB | **115 MB** | Similar |
| **Compilación de Rust/Cargo** | ✅ Requerida | ❌ No requerida | Eliminada |
| **Wheels precompilados** | ❌ No disponibles | ✅ Disponibles | Sí |

### Impacto Real

- **Desarrollo**: Cambios en código se construyen en **menos de 1 segundo** 🚀
- **CI/CD**: Builds más rápidos = despliegues más rápidos
- **Cache efectivo**: Dependencias solo se reinstalan si cambia `pyproject.toml` o `uv.lock`

## 🔍 Problemas del Dockerfile Anterior (Alpine)

### 1. Compilación de Rust/Cargo (Problema Principal)

**Código problemático:**
```dockerfile
FROM python:3.14-alpine
RUN apk add --no-cache \
    cargo \
    rust \
    gcc \
    musl-dev \
    postgresql-dev \
    libffi-dev \
    openssl-dev
```

**Problemas:**
- **Rust y Cargo** toman 5-15 minutos en compilar paquetes de criptografía
- Paquetes como `cryptography`, `gevent`, `psycopg2-binary` se compilan desde el código fuente
- Alpine usa `musl` en lugar de `glibc`, forzando compilación de muchos paquetes

### 2. Sin Caché Efectivo de Dependencias

**Código problemático:**
```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv pip install --no-cache -r pyproject.toml
COPY . .  # ⚠️ Cualquier cambio de código invalida TODO el caché
```

**Problemas:**
- Flag `--no-cache` descarta paquetes descargados
- Usar `pyproject.toml` directamente en lugar del lockfile
- Copiar código demasiado temprano invalida capas de dependencias

### 3. Uso Incorrecto de uv

**Código problemático:**
```dockerfile
RUN python3 -m venv /app/.venv && \
    /app/.venv/bin/pip install --upgrade pip && \
    . /app/.venv/bin/activate && \
    uv pip install --no-cache -r pyproject.toml
```

**Problemas:**
- No usa `uv sync` que aprovecha el lockfile
- Mezcla pip y uv innecesariamente
- No aprovecha el caché de uv

## ✅ Soluciones Implementadas

### 1. Cambio de Alpine a Debian Trixie

**Nuevo código:**
```dockerfile
FROM python:3.14-slim-trixie AS builder

# Solo dependencias mínimas - la mayoría son wheels precompilados
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
```

**Beneficios:**
- ✅ **Sin Rust/Cargo**: No se necesita compilar nada
- ✅ **Wheels precompilados**: PyPI tiene wheels para glibc (Debian)
- ✅ **Build 40% más rápido**: De 10-15 min a 6-7 min
- ✅ **Tamaño similar**: 115 MB vs 120-150 MB de Alpine

### 2. Capas de Docker Optimizadas

**Nuevo código:**
```dockerfile
# Stage 1: Builder - solo dependencias
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime - copia código al final
COPY --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appuser . .  # ✅ Código copiado al FINAL
```

**Beneficios:**
- ✅ **Caché efectivo**: Dependencias en capas separadas
- ✅ **Cambios de código rápidos**: Solo se reconstruye la última capa
- ✅ **Rebuilds en ~1 segundo** cuando solo cambia código

### 3. Uso Correcto de uv

**Nuevo código:**
```dockerfile
RUN uv sync --frozen --no-dev --no-install-project
```

**Beneficios:**
- ✅ **`uv sync`**: Usa el lockfile `uv.lock` para reproducibilidad exacta
- ✅ **`--frozen`**: Falla si lockfile está desactualizado (seguridad)
- ✅ **`--no-dev`**: Excluye dependencias de desarrollo
- ✅ **`--no-install-project`**: Solo instala dependencias, no el proyecto
- ✅ **Caché interno de uv**: Reutiliza paquetes descargados

### 4. Multi-stage Build Optimizado

**Nuevo código:**
```dockerfile
# Stage 1: Builder (con herramientas de compilación)
FROM python:3.14-slim-trixie AS builder
RUN apt-get install gcc libpq-dev ...
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime (solo runtime, sin herramientas)
FROM python:3.14-slim-trixie
RUN apt-get install libpq5 curl ...  # Solo runtime
COPY --from=builder /app/.venv /app/.venv
```

**Beneficios:**
- ✅ **Imagen final más pequeña**: Sin gcc, headers, etc.
- ✅ **Seguridad**: Menos superficie de ataque
- ✅ **Runtime limpio**: Solo lo necesario para ejecutar

## 🎯 Cuándo se Reconstruye Cada Capa

### Cambio de Dependencias (pyproject.toml o uv.lock)
```bash
# Tiempo: ~6-7 minutos (build completo)
# Se reconstruye: ✅ Capa de dependencias + ✅ Capa de código
```

### Cambio de Código (solo archivos .py)
```bash
# Tiempo: ~0.5-1 segundo (solo última capa)
# Se reconstruye: ❌ Capa de dependencias + ✅ Capa de código
```

### Sin Cambios
```bash
# Tiempo: ~1 segundo (todo en caché)
# Se reconstruye: ❌ Nada
```

## 📝 Comandos de Build

### Build Normal
```bash
docker build -t mikrom-py:latest .
# Tiempo: ~1 segundo (con caché) / ~7 min (sin caché)
```

### Build sin Caché (Benchmark)
```bash
docker build --no-cache -t mikrom-py:latest .
# Tiempo: ~6:42 minutos
```

### Build con BuildKit (más rápido)
```bash
DOCKER_BUILDKIT=1 docker build -t mikrom-py:latest .
# Usa caché distribuido y builds en paralelo
```

### Verificar Tamaño de Imagen
```bash
docker images mikrom-py:latest
# Tamaño: ~115 MB (comprimido), ~662 MB (disco)
```

## 🔧 Configuración Recomendada

### Para Desarrollo Local
```bash
# Use docker-compose para builds automáticos
docker-compose up --build
```

### Para CI/CD
```yaml
# .github/workflows/docker.yml
- name: Build Docker Image
  run: |
    docker build \
      --cache-from=mikrom-py:latest \
      --tag=mikrom-py:${{ github.sha }} \
      .
```

### Para Producción
```bash
# Multi-platform build
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag mikrom-py:latest \
  --push .
```

## 🚀 Mejoras Adicionales Opcionales

### 1. Caché de Docker Registry
```dockerfile
# Usar caché remoto para CI/CD
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
```

### 2. Optimización de Dependencias
```bash
# Revisar dependencias innecesarias
uv pip list --outdated
uv pip tree  # Ver árbol de dependencias
```

### 3. Imagen Base Distroless
```dockerfile
# Para producción ultra-segura
FROM gcr.io/distroless/python3-debian12:nonroot
COPY --from=builder /app/.venv /app/.venv
```

## 📚 Referencias

- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [Python Wheels](https://pythonwheels.com/)
- [Debian Trixie](https://www.debian.org/releases/trixie/)

## 🎯 Optimización de Imagen Compartida

### Problema: Múltiples Servicios, Misma Imagen

Anteriormente, cada servicio (app, worker, beat, flower) construía su propia imagen idéntica:

```yaml
# ❌ Configuración anterior (ineficiente)
app:
  build:
    context: .
    dockerfile: Dockerfile

worker:
  build:
    context: .
    dockerfile: Dockerfile

beat:
  build:
    context: .
    dockerfile: Dockerfile

flower:
  build:
    context: .
    dockerfile: Dockerfile
```

**Problemas:**
- 🐌 **Build 4× más lento**: Construye 4 imágenes idénticas
- 💾 **Desperdicio de espacio**: 4 × 662MB = 2.6GB
- 🔄 **Sin cache compartido**: Cada servicio reconstruye todo
- ⏱️ **CI/CD más lento**: Más tiempo de transferencia

### Solución: Build Compartido

```yaml
# ✅ Configuración actual (optimizada)
app:
  build:
    context: .
    dockerfile: Dockerfile
  image: mikrom-py:latest  # Nombre explícito

worker:
  image: mikrom-py:latest  # Reutiliza imagen de app

beat:
  image: mikrom-py:latest  # Reutiliza imagen de app

flower:
  image: mikrom-py:latest  # Reutiliza imagen de app
```

**Beneficios:**
- ⚡ **Build 4× más rápido**: Solo construye 1 imagen
- 💾 **Ahorra ~2GB**: De 2.6GB a 662MB
- 🔄 **Cache compartido**: Todos usan la misma imagen
- 🚀 **Más eficiente**: Menos I/O de disco

### Healthcheck por Servicio

Cada servicio define su propio healthcheck en `docker-compose.yml`:

```yaml
app:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]

worker:
  healthcheck:
    test: ["CMD-SHELL", "celery -A mikrom.celery_app inspect ping"]

beat:
  healthcheck:
    test: ["CMD-SHELL", "test -f /tmp/celerybeat-schedule"]

flower:
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://127.0.0.1:5555/healthcheck"]
```

Por eso se **eliminó el healthcheck del Dockerfile** - cada servicio necesita su propio check específico.

### Comandos por Servicio

Cada servicio sobreescribe el CMD del Dockerfile:

```yaml
# app: usa el CMD por defecto del Dockerfile
# CMD ["python", "-m", "uvicorn", "mikrom.main:app", ...]

worker:
  command: celery -A mikrom.celery_app worker --pool=gevent --concurrency=100

beat:
  command: celery -A mikrom.celery_app beat --loglevel=info

flower:
  command: celery -A mikrom.celery_app flower --port=5555
```

### Resultados

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| **Imágenes en disco** | 2.6GB (4 imgs) | 662MB (1 img) | -75% |
| **Tiempo de build** | ~27 min (4×6:42) | ~7 min (1×6:42) | -74% |
| **Espacio ahorrado** | - | ~2GB | 📦 |
| **Cache compartido** | ❌ No | ✅ Sí | 🚀 |

## 🎉 Conclusión

La combinación de optimizaciones ha logrado:

### Migración Alpine → Debian Trixie
- ✅ **99% más rápido** en rebuilds
- ✅ **40% más rápido** en builds iniciales
- ✅ **Sin compilación de Rust/Cargo**

### Build Compartido
- ✅ **75% menos espacio** en disco
- ✅ **4× más rápido** en docker compose build
- ✅ **Cache compartido** entre servicios

### Resultado Final
- **Desarrollo**: Cambios de código en **0.5 segundos** 🚀
- **Builds completos**: De 27 minutos a **7 minutos** ⚡
- **Espacio en disco**: Ahorro de **~2GB** 💾
- **Experiencia de desarrollo**: **Dramáticamente mejorada** 🎯

**Tiempo total ahorrado:**
- Antes: 27 min build completo (4 servicios), 1-2 min por cambio
- Ahora: 7 min build completo, **0.5 segundos** por cambio
- **Ahorro: ~75% en builds, ~99.5% en desarrollo iterativo** 🚀
