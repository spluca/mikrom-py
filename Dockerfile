# Multi-stage build for production optimization with Python 3.14 Alpine

# Stage 1: Builder
FROM python:3.14-alpine as builder

# Install build dependencies for Alpine
# - gcc, musl-dev: C compiler and standard library for Python packages
# - postgresql-dev: PostgreSQL client library headers
# - libffi-dev: Foreign Function Interface library for cryptography
# - openssl-dev: SSL/TLS library for secure connections
# - cargo, rust: Required for some Python cryptography packages
RUN apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    rust

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment with Python's venv (not uv venv) and install dependencies
RUN python3 -m venv /app/.venv && \
    /app/.venv/bin/pip install --upgrade pip && \
    . /app/.venv/bin/activate && \
    uv pip install --no-cache -r pyproject.toml

# Stage 2: Runtime
FROM python:3.14-alpine

# Install runtime dependencies only (smaller footprint)
RUN apk add --no-cache \
    libpq \
    libffi \
    openssl

# Create non-root user
RUN adduser -D -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Run the application
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "mikrom.main:app", "--host", "0.0.0.0", "--port", "8000"]
