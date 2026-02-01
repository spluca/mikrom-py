# GitLab CI/CD Troubleshooting

## Common Issues and Solutions

### 1. PostgreSQL Service Fails to Start - "No space left on device"

#### Symptoms

```
initdb: error: could not create directory "/var/lib/postgresql/18/docker/pg_wal": No space left on device
postgres:5432 - no response
Waiting for postgres...
ERROR: Job failed: execution took longer than 1h0m0s seconds
```

#### Root Cause

The GitLab runner's Docker host has run out of disk space. PostgreSQL cannot initialize its data directory.

#### Solution 1: Clean Up Runner Disk Space (Requires Admin Access)

**This is the PRIMARY solution and must be done by a GitLab administrator.**

```bash
# SSH into the GitLab runner server
ssh admin@gitlab-runner-host

# Check current disk usage
df -h

# Clean up Docker resources (removes unused images, containers, volumes, networks)
docker system prune -af --volumes

# Alternative: More aggressive cleanup
docker system prune -af --volumes --all

# Check disk usage again
df -h

# If still low on space, check for large log files
du -sh /var/lib/docker/*
du -sh /var/log/*

# Clean old logs if needed
journalctl --vacuum-time=7d
```

**Recommended Actions:**
1. Set up automatic Docker cleanup on the runner
2. Monitor disk usage with alerts
3. Increase runner disk size if needed

#### Solution 2: Use tmpfs for PostgreSQL (Workaround)

We've configured the CI to use in-memory storage (`/dev/shm`) for PostgreSQL data, which reduces disk I/O and space requirements:

```yaml
services:
  - name: postgres:18-alpine
    alias: postgres

variables:
  PGDATA: /dev/shm/postgres  # Use tmpfs (RAM) instead of disk
  POSTGRES_HOST_AUTH_METHOD: trust
```

**Note:** This is a workaround. The runner still needs adequate disk space for Docker images and build artifacts.

#### Solution 3: Optimize Runner Configuration

Add to the runner's `/etc/gitlab-runner/config.toml`:

```toml
[[runners]]
  [runners.docker]
    # Limit concurrent jobs
    limit = 2
    
    # Enable automatic cleanup
    disable_cache = false
    
    # Limit Docker image/container sizes
    allowed_images = ["*"]
    
    # Clean up containers after each job
    volumes = ["/cache", "/var/run/docker.sock:/var/run/docker.sock"]
    
    # Set disk space threshold
    [runners.docker.services_tmpfs]
      "/var/lib/postgresql/data" = "rw,noexec,nosuid,size=1g"
```

#### Solution 4: Use External PostgreSQL

Instead of running PostgreSQL as a service in CI, connect to an external PostgreSQL instance:

```yaml
# .gitlab-ci.yml
test:
  services: []  # Remove postgres service
  variables:
    DATABASE_URL: postgresql://user:pass@external-postgres:5432/mikrom_test_db
```

**Pros:**
- No disk space needed for PostgreSQL
- Faster CI jobs (no service startup time)
- Persistent test database

**Cons:**
- Requires maintaining external PostgreSQL instance
- Test isolation more complex

---

### 2. CI Timeout After 1 Hour

#### Symptoms

```
ERROR: Job failed: execution took longer than 1h0m0s seconds
```

#### Causes

1. PostgreSQL never starts (due to disk space)
2. Infinite loop waiting for PostgreSQL
3. Tests hang indefinitely

#### Solution

We've added a retry limit to the PostgreSQL wait loop:

```bash
MAX_RETRIES=30
RETRY_COUNT=0
until pg_isready -h postgres -U postgres || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
  echo "Waiting for postgres... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
  RETRY_COUNT=$((RETRY_COUNT + 1))
  sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "ERROR: PostgreSQL failed to start after $MAX_RETRIES attempts"
  echo "This usually indicates disk space issues on the runner"
  exit 1
fi
```

This ensures the job fails fast (after 60 seconds) instead of timing out after 1 hour.

---

### 3. Service Container Fails to Start

#### Symptoms

```
WARNING: Service postgres:18-alpine probably didn't start properly.
Health check error: start service container: Error response from daemon: 
Cannot link to a non running container
```

#### Causes

1. Previous container with same name still exists
2. Docker daemon issues on runner
3. Insufficient resources (CPU, RAM, disk)

#### Solution

On the runner:

```bash
# List all containers (including stopped)
docker ps -a | grep postgres

# Remove stale containers
docker rm -f $(docker ps -aq -f name=postgres)

# Restart Docker daemon if needed
systemctl restart docker
```

---

### 4. Cache Issues

#### Symptoms

- Dependencies reinstall every time
- `uv sync` takes too long
- Cache warnings in logs

#### Solution

The CI is configured with proper cache keys based on lock files:

```yaml
cache:
  key:
    files:
      - pyproject.toml
      - uv.lock
  paths:
    - .cache/uv
    - .venv/
  policy: pull-push
```

If cache is corrupt, clear it manually:

1. Go to CI/CD → Pipelines
2. Click "Clear runner caches"
3. Re-run pipeline

---

## Monitoring and Prevention

### 1. Set Up Disk Space Monitoring

On the GitLab runner:

```bash
# Add cron job to monitor disk space
cat << 'EOF' > /etc/cron.hourly/check-disk-space
#!/bin/bash
THRESHOLD=80
USAGE=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')

if [ "$USAGE" -gt "$THRESHOLD" ]; then
    echo "WARNING: Disk usage at ${USAGE}% (threshold: ${THRESHOLD}%)"
    # Send alert (email, Slack, etc.)
fi
EOF

chmod +x /etc/cron.hourly/check-disk-space
```

### 2. Automatic Docker Cleanup

Add to runner crontab:

```bash
# Clean Docker weekly
0 2 * * 0 /usr/bin/docker system prune -af --volumes
```

### 3. Runner Health Check Script

```bash
#!/bin/bash
# /usr/local/bin/gitlab-runner-health.sh

echo "=== GitLab Runner Health Check ==="
echo ""

echo "Disk Usage:"
df -h /

echo ""
echo "Docker Disk Usage:"
docker system df

echo ""
echo "Running Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Size}}"

echo ""
echo "Docker Images:"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
```

Run regularly:

```bash
chmod +x /usr/local/bin/gitlab-runner-health.sh
crontab -e
# Add: 0 */6 * * * /usr/local/bin/gitlab-runner-health.sh >> /var/log/runner-health.log
```

---

## Quick Reference

### Check Runner Status

```bash
# On runner host
sudo gitlab-runner status
sudo gitlab-runner verify

# Check disk space
df -h

# Check Docker
docker info
docker system df
```

### Emergency Cleanup

```bash
# Stop all running containers
docker stop $(docker ps -aq)

# Remove all containers
docker rm $(docker ps -aq)

# Remove all unused images
docker image prune -af

# Remove all volumes
docker volume prune -af

# Full cleanup (CAUTION: removes everything)
docker system prune -af --volumes
```

### Restart Runner

```bash
sudo gitlab-runner restart
```

---

## Contact

If you encounter issues not covered here:

1. Check runner logs: `sudo journalctl -u gitlab-runner -f`
2. Contact the DevOps team
3. Open an issue in the project repository

---

**Last Updated:** February 2025  
**Maintainer:** Mikrom Platform Team
