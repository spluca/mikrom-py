# Deployment en Producción: Celery Workers

## 📖 Descripción

Guía completa para desplegar Celery workers en producción usando Supervisor o systemd.

---

## 🏗️ Arquitectura de Producción

```
┌─────────────────┐
│   Nginx/Caddy   │ (HTTPS, reverse proxy para Flower)
└────────┬────────┘
         │
         ├─── Flower UI (port 5555)
         │
┌────────┴────────┐
│  Redis (Broker) │
└────────┬────────┘
         │
         ├─── Worker 1 (gevent pool, 100 concurrency)
         ├─── Worker 2 (gevent pool, 100 concurrency)
         └─── Beat (scheduler)
```

---

## 🐳 Docker Production

### Docker Compose

Ya configurado en `docker-compose.yml`:

```yaml
services:
  worker:
    image: mikrom-py:latest
    command: celery -A mikrom.celery_app worker --pool=gevent --concurrency=100 --loglevel=info
    restart: unless-stopped
    deploy:
      replicas: 2  # Múltiples workers
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
  
  beat:
    image: mikrom-py:latest
    command: celery -A mikrom.celery_app beat --loglevel=info
    restart: unless-stopped
    deploy:
      replicas: 1  # Solo un Beat
  
  flower:
    image: mikrom-py:latest
    command: celery -A mikrom.celery_app flower --port=5555 --basic_auth=${FLOWER_BASIC_AUTH}
    restart: unless-stopped
    ports:
      - "5555:5555"
```

### Comandos Docker

**Build:**
```bash
docker-compose build
```

**Deploy:**
```bash
docker-compose up -d
```

**Scale workers:**
```bash
docker-compose up -d --scale worker=4
```

**Ver logs:**
```bash
docker-compose logs -f worker
```

**Restart:**
```bash
docker-compose restart worker
```

---

## 🔧 Supervisor (Recomendado)

### Instalación

```bash
# Ubuntu/Debian
sudo apt-get install supervisor

# CentOS/RHEL
sudo yum install supervisor

# Verificar
sudo supervisorctl version
```

### Configuración Base

**Directorio:** `/etc/supervisor/conf.d/`

#### Worker Config

Crear `/etc/supervisor/conf.d/mikrom-worker.conf`:

```ini
[program:mikrom-worker]
command=/home/mikrom/venv/bin/celery -A mikrom.celery_app worker --pool=gevent --concurrency=100 --loglevel=info
directory=/home/mikrom/mikrom-py
user=mikrom
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
stopasgroup=true
killasgroup=true
priority=998
stdout_logfile=/var/log/mikrom/worker.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
stderr_logfile=/var/log/mikrom/worker.error.log
stderr_logfile_maxbytes=50MB
stderr_logfile_backups=10
environment=
    PATH="/home/mikrom/venv/bin",
    PYTHONPATH="/home/mikrom/mikrom-py",
    DATABASE_URL="postgresql://user:pass@localhost/mikrom",
    REDIS_URL="redis://localhost:6379",
    SECRET_KEY="your-secret-key"
```

#### Beat Config

Crear `/etc/supervisor/conf.d/mikrom-beat.conf`:

```ini
[program:mikrom-beat]
command=/home/mikrom/venv/bin/celery -A mikrom.celery_app beat --loglevel=info
directory=/home/mikrom/mikrom-py
user=mikrom
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=30
stopasgroup=true
killasgroup=true
priority=999
stdout_logfile=/var/log/mikrom/beat.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile=/var/log/mikrom/beat.error.log
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5
environment=
    PATH="/home/mikrom/venv/bin",
    PYTHONPATH="/home/mikrom/mikrom-py"
```

#### Flower Config

Crear `/etc/supervisor/conf.d/mikrom-flower.conf`:

```ini
[program:mikrom-flower]
command=/home/mikrom/venv/bin/celery -A mikrom.celery_app flower --port=5555 --basic_auth=%(ENV_FLOWER_USER)s:%(ENV_FLOWER_PASS)s
directory=/home/mikrom/mikrom-py
user=mikrom
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=30
stdout_logfile=/var/log/mikrom/flower.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
stderr_logfile=/var/log/mikrom/flower.error.log
stderr_logfile_maxbytes=10MB
stderr_logfile_backups=5
environment=
    PATH="/home/mikrom/venv/bin",
    FLOWER_USER="admin",
    FLOWER_PASS="secure_password"
```

### Múltiples Workers

Crear `/etc/supervisor/conf.d/mikrom-workers.conf`:

```ini
[group:mikrom-workers]
programs=mikrom-worker-1,mikrom-worker-2,mikrom-worker-3

[program:mikrom-worker-1]
command=/home/mikrom/venv/bin/celery -A mikrom.celery_app worker --pool=gevent --concurrency=100 -n worker1@%%h --loglevel=info
directory=/home/mikrom/mikrom-py
user=mikrom
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
stdout_logfile=/var/log/mikrom/worker-1.log
stderr_logfile=/var/log/mikrom/worker-1.error.log

[program:mikrom-worker-2]
command=/home/mikrom/venv/bin/celery -A mikrom.celery_app worker --pool=gevent --concurrency=100 -n worker2@%%h --loglevel=info
directory=/home/mikrom/mikrom-py
user=mikrom
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
stdout_logfile=/var/log/mikrom/worker-2.log
stderr_logfile=/var/log/mikrom/worker-2.error.log

[program:mikrom-worker-3]
command=/home/mikrom/venv/bin/celery -A mikrom.celery_app worker --pool=gevent --concurrency=100 -n worker3@%%h --loglevel=info
directory=/home/mikrom/mikrom-py
user=mikrom
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
stdout_logfile=/var/log/mikrom/worker-3.log
stderr_logfile=/var/log/mikrom/worker-3.error.log
```

### Comandos Supervisor

**Recargar configuración:**
```bash
sudo supervisorctl reread
sudo supervisorctl update
```

**Iniciar servicios:**
```bash
sudo supervisorctl start mikrom-worker
sudo supervisorctl start mikrom-beat
sudo supervisorctl start mikrom-flower
```

**Ver estado:**
```bash
sudo supervisorctl status
```

**Restart:**
```bash
sudo supervisorctl restart mikrom-worker
```

**Stop:**
```bash
sudo supervisorctl stop mikrom-worker
```

**Ver logs:**
```bash
sudo supervisorctl tail -f mikrom-worker
sudo supervisorctl tail -f mikrom-worker stderr
```

**Grupo de workers:**
```bash
sudo supervisorctl start mikrom-workers:*
sudo supervisorctl restart mikrom-workers:*
sudo supervisorctl status mikrom-workers:*
```

---

## ⚙️ Systemd

### Worker Service

Crear `/etc/systemd/system/mikrom-worker.service`:

```ini
[Unit]
Description=Mikrom Celery Worker
After=network.target redis.service postgresql.service
Requires=redis.service

[Service]
Type=simple
User=mikrom
Group=mikrom
WorkingDirectory=/home/mikrom/mikrom-py
Environment="PATH=/home/mikrom/venv/bin"
EnvironmentFile=/home/mikrom/mikrom-py/.env
ExecStart=/home/mikrom/venv/bin/celery -A mikrom.celery_app worker --pool=gevent --concurrency=100 --loglevel=info
Restart=always
RestartSec=10s
KillSignal=SIGTERM
TimeoutStopSec=600
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mikrom-worker

[Install]
WantedBy=multi-user.target
```

### Beat Service

Crear `/etc/systemd/system/mikrom-beat.service`:

```ini
[Unit]
Description=Mikrom Celery Beat Scheduler
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=mikrom
Group=mikrom
WorkingDirectory=/home/mikrom/mikrom-py
Environment="PATH=/home/mikrom/venv/bin"
EnvironmentFile=/home/mikrom/mikrom-py/.env
ExecStart=/home/mikrom/venv/bin/celery -A mikrom.celery_app beat --loglevel=info
Restart=always
RestartSec=10s
KillSignal=SIGTERM
TimeoutStopSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mikrom-beat

[Install]
WantedBy=multi-user.target
```

### Flower Service

Crear `/etc/systemd/system/mikrom-flower.service`:

```ini
[Unit]
Description=Mikrom Flower Monitoring
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=mikrom
Group=mikrom
WorkingDirectory=/home/mikrom/mikrom-py
Environment="PATH=/home/mikrom/venv/bin"
EnvironmentFile=/home/mikrom/mikrom-py/.env
ExecStart=/home/mikrom/venv/bin/celery -A mikrom.celery_app flower --port=5555 --basic_auth=${FLOWER_BASIC_AUTH}
Restart=always
RestartSec=10s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mikrom-flower

[Install]
WantedBy=multi-user.target
```

### Comandos Systemd

**Reload daemon:**
```bash
sudo systemctl daemon-reload
```

**Enable (iniciar en boot):**
```bash
sudo systemctl enable mikrom-worker
sudo systemctl enable mikrom-beat
sudo systemctl enable mikrom-flower
```

**Start:**
```bash
sudo systemctl start mikrom-worker
sudo systemctl start mikrom-beat
sudo systemctl start mikrom-flower
```

**Status:**
```bash
sudo systemctl status mikrom-worker
```

**Restart:**
```bash
sudo systemctl restart mikrom-worker
```

**Stop:**
```bash
sudo systemctl stop mikrom-worker
```

**Ver logs:**
```bash
sudo journalctl -u mikrom-worker -f
sudo journalctl -u mikrom-worker --since today
sudo journalctl -u mikrom-worker -n 100
```

---

## 🌐 Nginx Reverse Proxy para Flower

### Configuración HTTP

Crear `/etc/nginx/sites-available/flower.conf`:

```nginx
server {
    listen 80;
    server_name flower.example.com;
    
    location / {
        proxy_pass http://localhost:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support para live updates
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Configuración HTTPS (con Let's Encrypt)

```nginx
server {
    listen 80;
    server_name flower.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name flower.example.com;
    
    ssl_certificate /etc/letsencrypt/live/flower.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/flower.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Restringir por IP (opcional)
    allow 192.168.1.0/24;
    allow 10.0.0.0/8;
    deny all;
    
    location / {
        proxy_pass http://localhost:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Activar:**
```bash
sudo ln -s /etc/nginx/sites-available/flower.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 📊 Monitoreo y Alertas

### Prometheus + Grafana

**Instalar flower-prometheus-exporter:**
```bash
pip install flower-prometheus
```

**Configurar Prometheus scrape:**
```yaml
scrape_configs:
  - job_name: 'celery'
    static_configs:
      - targets: ['localhost:5555']
    metrics_path: '/metrics'
```

### Health Check Script

Crear `/usr/local/bin/celery-health-check.sh`:

```bash
#!/bin/bash

CELERY_APP="mikrom.celery_app"
ALERT_EMAIL="admin@example.com"

# Check if workers are responding
ACTIVE_WORKERS=$(celery -A $CELERY_APP inspect active 2>&1)

if [[ $? -ne 0 ]] || [[ "$ACTIVE_WORKERS" == *"Error"* ]]; then
    echo "ALERT: Celery workers not responding!" | mail -s "Celery Alert" $ALERT_EMAIL
    exit 1
fi

# Check pending tasks
QUEUE_LENGTH=$(redis-cli -h localhost -p 6379 llen mikrom:queue)

if [ "$QUEUE_LENGTH" -gt 1000 ]; then
    echo "ALERT: Queue length is $QUEUE_LENGTH!" | mail -s "Celery Queue Alert" $ALERT_EMAIL
fi

exit 0
```

**Cron job (cada 5 minutos):**
```bash
*/5 * * * * /usr/local/bin/celery-health-check.sh
```

---

## 🔐 Seguridad

### Redis

**Configurar contraseña:**
```bash
# /etc/redis/redis.conf
requirepass your-strong-password-here
```

**Actualizar REDIS_URL:**
```bash
REDIS_URL=redis://:your-strong-password-here@localhost:6379
```

### Flower

**Autenticación HTTP básica:**
```bash
FLOWER_BASIC_AUTH=admin:password,user2:password2
```

**OAuth2 (Google):**
```bash
celery -A mikrom.celery_app flower \
  --auth=".*@example\.com" \
  --auth_provider=flower.views.auth.GoogleAuth2LoginHandler \
  --oauth2_key=your-google-oauth-key \
  --oauth2_secret=your-google-oauth-secret \
  --oauth2_redirect_uri=https://flower.example.com/login
```

### Firewall

```bash
# Permitir solo localhost para Redis
sudo ufw allow from 127.0.0.1 to any port 6379

# Permitir Flower solo desde IPs específicas
sudo ufw allow from 192.168.1.0/24 to any port 5555
```

---

## 📝 Logs

### Logrotate

Crear `/etc/logrotate.d/mikrom`:

```
/var/log/mikrom/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
    create 0640 mikrom mikrom
}
```

### Centralized Logging

**Filebeat + ELK Stack:**

`/etc/filebeat/filebeat.yml`:
```yaml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/mikrom/worker*.log
  fields:
    service: mikrom-worker
    
- type: log
  enabled: true
  paths:
    - /var/log/mikrom/beat.log
  fields:
    service: mikrom-beat

output.elasticsearch:
  hosts: ["localhost:9200"]
```

---

## ⚡ Performance Tuning

### Worker Optimization

```bash
# Para tareas CPU-bound (cambiar a prefork)
celery -A mikrom.celery_app worker --pool=prefork --concurrency=4

# Para tareas I/O-bound (gevent, alta concurrency)
celery -A mikrom.celery_app worker --pool=gevent --concurrency=500

# Autoscaling
celery -A mikrom.celery_app worker --autoscale=10,3

# Rate limiting
celery -A mikrom.celery_app worker --max-tasks-per-child=100
```

### Redis Optimization

`/etc/redis/redis.conf`:
```
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""
appendonly no
```

---

## 🚨 Troubleshooting Production

Ver: [`CELERY_TROUBLESHOOTING.md`](./CELERY_TROUBLESHOOTING.md)

---

## ✅ Production Checklist

- [ ] Supervisor o systemd configurado
- [ ] Múltiples workers para redundancia
- [ ] Solo un Beat (scheduler)
- [ ] Flower con HTTPS y autenticación
- [ ] Redis con contraseña
- [ ] Firewall configurado
- [ ] Logs rotando (logrotate)
- [ ] Monitoreo (Prometheus/Grafana)
- [ ] Health checks automatizados
- [ ] Alertas configuradas
- [ ] Backups de Redis (si es necesario)
- [ ] Documentación de runbooks

---

## 📚 Referencias

- [Celery Daemonization](https://docs.celeryq.dev/en/stable/userguide/daemonizing.html)
- [Supervisor Documentation](http://supervisord.org/)
- [Systemd Documentation](https://www.freedesktop.org/software/systemd/man/)
