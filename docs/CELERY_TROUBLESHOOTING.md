# Troubleshooting: Celery Workers

## 🐛 Problemas Comunes y Soluciones

---

## ⚠️ Docker Worker Showing as "Unhealthy"

### Síntomas
```bash
$ docker compose ps worker
NAME            STATUS
mikrom_worker   Up 5 minutes (unhealthy)

# Health check logs show:
Error: No nodes replied within time constraint
```

### Causa Raíz
El worker no puede responder a los health checks de Docker durante la ejecución de tareas de larga duración que bloquean el event loop. Esto ocurre especialmente con:
- Operaciones SSH bloqueantes (Ansible playbooks)
- Conexiones a hosts no alcanzables con timeouts largos
- Pool `gevent` con operaciones I/O bloqueantes

### Solución Implementada (v2.0+)

Hemos implementado **4 mejoras** para resolver este problema:

#### 1. Cambio de Pool: `gevent` → `prefork`
```yaml
# docker-compose.yml
command: celery -A mikrom.celery_app worker --pool=prefork --concurrency=4
```

**Ventajas de prefork:**
- ✅ Robusto para operaciones bloqueantes (SSH, subprocess)
- ✅ Aislamiento completo entre workers
- ✅ Timeout enforcement confiable
- ✅ Worker puede responder a health checks incluso durante tareas largas

**Configuración:**
```bash
# .env
CELERY_WORKER_POOL=prefork
CELERY_WORKER_CONCURRENCY=4  # Ajustar según CPU cores
```

#### 2. Timeouts Agresivos
```bash
# .env
CELERY_TASK_SOFT_TIME_LIMIT=180  # 3 minutos - aviso
CELERY_TASK_HARD_TIME_LIMIT=240  # 4 minutos - kill forzoso
ANSIBLE_PLAYBOOK_TIMEOUT=120     # 2 minutos - timeout Ansible
ANSIBLE_SSH_TIMEOUT=30           # 30 segundos - conexión SSH
```

Las tareas ahora tienen múltiples capas de protección:
1. **Ansible timeout** (120s): Playbook se cancela automáticamente
2. **Soft limit** (180s): Task recibe excepción `SoftTimeLimitExceeded`, puede hacer cleanup
3. **Hard limit** (240s): Worker process es matado forzosamente (SIGKILL)

#### 3. Health Check Más Tolerante
```yaml
healthcheck:
  test: ["CMD-SHELL", "celery -A mikrom.celery_app inspect ping -d celery@$$HOSTNAME || exit 1"]
  interval: 30s
  timeout: 30s    # Aumentado de 10s
  retries: 5      # Aumentado de 3
  start_period: 30s  # Aumentado de 10s
```

El health check ahora espera más tiempo antes de marcar el worker como unhealthy.

#### 4. Ansible en ThreadPoolExecutor
```python
# mikrom/clients/firecracker.py
with ThreadPoolExecutor(max_workers=1) as executor:
    future = executor.submit(ansible_runner.run, ...)
    runner = future.result(timeout=settings.ANSIBLE_PLAYBOOK_TIMEOUT)
```

Ansible ahora se ejecuta en un thread separado con timeout enforcement real, evitando bloquear el worker principal.

### Verificación

**1. Comprobar pool actual:**
```bash
docker exec mikrom_worker celery -A mikrom.celery_app inspect active_queues
```

**2. Verificar health check:**
```bash
docker inspect mikrom_worker | jq '.[0].State.Health'
```

**3. Monitorear durante tarea larga:**
```bash
# Terminal 1: Crear VM
curl -X POST http://localhost:8000/api/v1/vms -H "Authorization: Bearer $TOKEN" ...

# Terminal 2: Monitorear health
watch -n 5 'docker compose ps worker'
```

**Resultado esperado:** Worker debe permanecer **healthy** incluso durante ejecución de tareas.

### Troubleshooting Adicional

**Si el worker sigue unhealthy:**

1. **Verificar configuración del pool:**
```bash
docker exec mikrom_worker bash -c 'ps aux | grep celery'
# Debe mostrar: --pool=prefork --concurrency=4
```

2. **Verificar que se cargaron las configuraciones:**
```bash
docker exec mikrom_worker python -c "from mikrom.config import settings; print(f'Pool: {settings.CELERY_WORKER_POOL}, Timeout: {settings.ANSIBLE_PLAYBOOK_TIMEOUT}')"
```

3. **Revisar logs de timeouts:**
```bash
docker logs mikrom_worker 2>&1 | grep -i "timeout\|time limit"
```

4. **Aumentar recursos si es necesario:**
```yaml
# docker-compose.yml
worker:
  deploy:
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 1G
```

### Cuándo Ajustar Timeouts

**Timeouts muy cortos** (tareas legítimas fallan):
```bash
# Aumentar gradualmente
CELERY_TASK_SOFT_TIME_LIMIT=300  # 5 minutos
CELERY_TASK_HARD_TIME_LIMIT=360  # 6 minutos
ANSIBLE_PLAYBOOK_TIMEOUT=240     # 4 minutos
```

**Timeouts muy largos** (tasks colgadas demoran mucho en fallar):
```bash
# Reducir para fail-fast
CELERY_TASK_SOFT_TIME_LIMIT=120  # 2 minutos
CELERY_TASK_HARD_TIME_LIMIT=150  # 2.5 minutos
ANSIBLE_PLAYBOOK_TIMEOUT=90      # 1.5 minutos
```

**Regla general:**
- `ANSIBLE_PLAYBOOK_TIMEOUT` < `CELERY_TASK_SOFT_TIME_LIMIT` < `CELERY_TASK_HARD_TIME_LIMIT`
- Diferencia de ~30-60 segundos entre cada nivel para permitir cleanup graceful

---

## ❌ Workers no responden

### Síntomas
```bash
$ celery -A mikrom.celery_app inspect active
Error: No nodes replied within time constraint
```

### Diagnóstico

**1. Verificar que Redis esté corriendo:**
```bash
redis-cli ping
# Debe responder: PONG
```

**2. Verificar conexión a Redis:**
```bash
redis-cli -h localhost -p 6379
> KEYS *
> LLEN mikrom:queue
```

**3. Verificar workers:**
```bash
ps aux | grep celery
```

**4. Ver logs:**
```bash
# Supervisor
sudo supervisorctl tail -f mikrom-worker stderr

# Systemd
sudo journalctl -u mikrom-worker -n 50

# Docker
docker-compose logs -f worker
```

### Soluciones

**Reiniciar workers:**
```bash
# Supervisor
sudo supervisorctl restart mikrom-worker

# Systemd
sudo systemctl restart mikrom-worker

# Docker
docker-compose restart worker
```

**Verificar configuración:**
```python
# mikrom/celery_app.py
print(celery_app.conf.broker_url)
print(celery_app.conf.result_backend)
```

---

## 🔴 Redis Connection Errors

### Error: `redis.exceptions.ConnectionError`

**Causas comunes:**
1. Redis no está corriendo
2. Redis en puerto incorrecto
3. Firewall bloqueando
4. Contraseña incorrecta

**Soluciones:**

**Verificar Redis:**
```bash
sudo systemctl status redis
sudo systemctl start redis
```

**Probar conexión:**
```bash
redis-cli -h localhost -p 6379 ping
```

**Con contraseña:**
```bash
redis-cli -h localhost -p 6379 -a your-password ping
```

**Verificar URL:**
```bash
echo $REDIS_URL
# Debe ser: redis://localhost:6379
# O con password: redis://:password@localhost:6379
```

---

## ⏱️ Tareas nunca se completan

### Síntomas
- Tareas quedan en estado `PENDING` o `STARTED`
- No se ve progreso en Flower

### Diagnóstico

**Ver tareas activas:**
```bash
celery -A mikrom.celery_app inspect active
```

**Ver tareas reservadas:**
```bash
celery -A mikrom.celery_app inspect reserved
```

**Verificar timeouts:**
```python
# mikrom/celery_app.py
print(celery_app.conf.task_time_limit)  # Debe ser 300 (5 min)
```

### Soluciones

**1. Aumentar timeout:**
```python
# mikrom/celery_app.py
celery_app.conf.task_time_limit = 600  # 10 minutos
```

**2. Task específica con timeout mayor:**
```python
@celery_app.task(time_limit=600)
async def long_running_task():
    pass
```

**3. Purgar tareas atascadas:**
```bash
celery -A mikrom.celery_app purge
```

**4. Revisar logs para excepciones:**
```bash
grep -i error /var/log/mikrom/worker.log
```

---

## 💥 Worker crashes o se reinicia constantemente

### Diagnóstico

**Ver logs:**
```bash
# Supervisor
sudo supervisorctl tail -100 mikrom-worker stderr

# Systemd
sudo journalctl -u mikrom-worker --since "10 minutes ago"
```

**Verificar memoria:**
```bash
free -h
```

**Verificar CPU:**
```bash
top -u mikrom
```

### Causas comunes

**1. Memory leak:**
```bash
# Ver uso de memoria por worker
ps aux | grep celery | awk '{print $6/1024 " MB - " $11}'
```

**Solución:**
```python
# mikrom/celery_app.py
celery_app.conf.worker_max_tasks_per_child = 100  # Reiniciar después de 100 tareas
```

**2. Excepciones no manejadas:**
```python
# Agregar try/except en tasks
@celery_app.task(bind=True, max_retries=3)
async def my_task(self):
    try:
        # código
    except Exception as exc:
        logger.error(f"Task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
```

**3. Gevent issues:**
```bash
# Verificar que gevent esté instalado
pip show gevent
```

**Solución:**
```bash
pip install --upgrade gevent
```

---

## 🔄 Beat no programa tareas

### Síntomas
- Tareas programadas no se ejecutan
- Beat está corriendo pero no hay actividad

### Diagnóstico

**Ver logs de Beat:**
```bash
# Supervisor
sudo supervisorctl tail -f mikrom-beat

# Systemd
sudo journalctl -u mikrom-beat -f
```

**Verificar schedule:**
```bash
celery -A mikrom.celery_app inspect scheduled
```

### Soluciones

**1. Solo un Beat debe estar corriendo:**
```bash
# Verificar
ps aux | grep "celery.*beat"

# Debe haber solo UNO
```

**2. Verificar configuración:**
```python
# mikrom/celery_app.py
print(celery_app.conf.beat_schedule)
```

**3. Eliminar schedule database y reiniciar:**
```bash
rm -f celerybeat-schedule.db
sudo supervisorctl restart mikrom-beat
```

**4. Verificar permisos:**
```bash
ls -la celerybeat-schedule.db
chown mikrom:mikrom celerybeat-schedule.db
```

---

## 🌐 Flower no carga o muestra datos incorrectos

### Síntomas
- Flower UI muestra "No workers online"
- Estadísticas incorrectas
- No se pueden ver tareas

### Diagnóstico

**Verificar Flower:**
```bash
curl http://localhost:5555/api/workers
```

**Ver logs:**
```bash
sudo supervisorctl tail -f mikrom-flower stderr
```

### Soluciones

**1. Reiniciar Flower:**
```bash
sudo supervisorctl restart mikrom-flower
```

**2. Verificar broker_api:**
```bash
celery -A mikrom.celery_app flower --broker_api=redis://localhost:6379/0
```

**3. Limpiar persistent database:**
```bash
rm -f /var/flower/flower.db
```

**4. Verificar autenticación:**
```bash
# Probar sin basic_auth primero
celery -A mikrom.celery_app flower --port=5555
```

---

## 📦 Import Errors

### Error: `ModuleNotFoundError: No module named 'mikrom'`

**Soluciones:**

**1. Verificar PYTHONPATH:**
```bash
export PYTHONPATH=/home/mikrom/mikrom-py:$PYTHONPATH
```

**2. Instalar en modo editable:**
```bash
cd /home/mikrom/mikrom-py
pip install -e .
```

**3. Verificar virtual environment:**
```bash
which python
which celery
# Ambos deben estar en el mismo venv
```

---

## 🔒 Permission Errors

### Error: `PermissionError: [Errno 13] Permission denied`

**Soluciones:**

**1. Verificar ownership de logs:**
```bash
sudo chown -R mikrom:mikrom /var/log/mikrom
sudo chmod 755 /var/log/mikrom
```

**2. Verificar ownership de código:**
```bash
sudo chown -R mikrom:mikrom /home/mikrom/mikrom-py
```

**3. Verificar usuario en supervisor/systemd:**
```ini
# Debe ser:
user=mikrom
```

---

## 🐌 Tareas muy lentas

### Diagnóstico

**Ver tiempos en Flower:**
- Dashboard → Tasks → Runtime

**Profile tarea:**
```python
import time

@celery_app.task
async def slow_task():
    start = time.time()
    
    # Operación 1
    t1 = time.time()
    await operation_1()
    print(f"Op1: {time.time() - t1}s")
    
    # Operación 2
    t2 = time.time()
    await operation_2()
    print(f"Op2: {time.time() - t2}s")
    
    print(f"Total: {time.time() - start}s")
```

### Soluciones

**1. Aumentar concurrency:**
```bash
celery -A mikrom.celery_app worker --pool=gevent --concurrency=200
```

**2. Múltiples workers:**
```bash
# Worker 1
celery -A mikrom.celery_app worker -n worker1@%h

# Worker 2
celery -A mikrom.celery_app worker -n worker2@%h
```

**3. Optimizar código:**
- Usar conexiones persistentes
- Batch operations
- Cachear resultados
- Async I/O correctamente

**4. Queue prioritization:**
```python
# Alta prioridad
task.apply_async(priority=9)

# Baja prioridad
task.apply_async(priority=0)
```

---

## 📊 Monitoreo de Problemas

### Health Check Script

```bash
#!/bin/bash

# Verificar workers
ACTIVE=$(celery -A mikrom.celery_app inspect active 2>&1)
if [[ $? -ne 0 ]]; then
    echo "ERROR: Workers no responden"
    exit 1
fi

# Verificar queue length
QUEUE_LEN=$(redis-cli llen mikrom:queue)
if [ "$QUEUE_LEN" -gt 1000 ]; then
    echo "WARNING: Queue tiene $QUEUE_LEN tareas"
fi

# Verificar failed tasks
FAILED=$(redis-cli get celery-task-meta-* | grep -c FAILURE)
if [ "$FAILED" -gt 10 ]; then
    echo "WARNING: $FAILED tareas fallidas"
fi

echo "OK: Sistema saludable"
exit 0
```

---

## 🔍 Debugging Avanzado

### Habilitar debug logging

```bash
celery -A mikrom.celery_app worker --loglevel=debug
```

### Ver requests de tasks

```python
# En la task
@celery_app.task(bind=True)
async def debug_task(self):
    print(f"Task ID: {self.request.id}")
    print(f"Task name: {self.request.task}")
    print(f"Args: {self.request.args}")
    print(f"Kwargs: {self.request.kwargs}")
    print(f"Retries: {self.request.retries}")
```

### Inspeccionar worker stats

```bash
celery -A mikrom.celery_app inspect stats | python -m json.tool
```

### Redis debugging

```bash
# Ver todas las keys
redis-cli keys "celery*"

# Ver queue
redis-cli lrange mikrom:queue 0 -1

# Ver results
redis-cli keys "celery-task-meta-*"
redis-cli get celery-task-meta-<task-id>
```

---

## 📞 Obtener Ayuda

**1. Logs completos:**
```bash
# Guardar logs
sudo supervisorctl tail -1000 mikrom-worker > worker.log
sudo supervisorctl tail -1000 mikrom-worker stderr > worker.error.log
```

**2. Estado del sistema:**
```bash
celery -A mikrom.celery_app inspect stats > celery-stats.json
celery -A mikrom.celery_app report > celery-report.txt
```

**3. Información de Redis:**
```bash
redis-cli info > redis-info.txt
```

**4. Crear issue en GitHub con:**
- Versión de Celery: `celery --version`
- Versión de Python: `python --version`
- Logs relevantes
- Configuración (sin credenciales)
- Pasos para reproducir

---

## 🛠️ Herramientas Útiles

### Celery Inspector

```python
from celery import Celery
from mikrom.celery_app import celery_app

# Inspeccionar
i = celery_app.control.inspect()
print(i.active())
print(i.stats())
print(i.registered())
```

### Redis Commander

```bash
npm install -g redis-commander
redis-commander
# Abrir http://localhost:8081
```

### Flower API

```bash
# Workers
curl http://localhost:5555/api/workers

# Tasks
curl http://localhost:5555/api/tasks

# Task by ID
curl http://localhost:5555/api/task/info/<task-id>
```

---

## ✅ Checklist de Troubleshooting

Antes de pedir ayuda, verificar:

- [ ] Redis está corriendo y accesible
- [ ] Workers están corriendo
- [ ] Logs no muestran excepciones
- [ ] PYTHONPATH correcto
- [ ] Virtual environment activado
- [ ] Permisos de archivos correctos
- [ ] Solo un Beat corriendo
- [ ] Configuración de broker_url correcta
- [ ] Firewall no bloqueando puertos
- [ ] Suficiente memoria disponible
- [ ] Timeouts apropiados

---

## 📚 Referencias

- [Celery Troubleshooting](https://docs.celeryq.dev/en/stable/faq.html)
- [Redis Troubleshooting](https://redis.io/docs/management/troubleshooting/)
- [Flower Issues](https://github.com/mher/flower/issues)
