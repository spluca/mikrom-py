# Guía de Uso: Celery Workers

## 📖 Descripción General

Mikrom utiliza **Celery** con **Redis** como broker para manejar tareas en background:

- **Worker:** Ejecuta tareas async (crear/eliminar/stop/start VMs)
- **Beat:** Scheduler para tareas programadas (limpieza, mantenimiento)
- **Flower:** Interfaz web para monitorear tareas y workers

---

## 🚀 Inicio Rápido

### Desarrollo Local con Docker

**Iniciar todos los servicios:**
```bash
cd mikrom-py
docker-compose up -d
```

**Ver logs del worker:**
```bash
docker-compose logs -f worker
```

**Ver logs de Beat:**
```bash
docker-compose logs -f beat
```

**Ver logs de Flower:**
```bash
docker-compose logs -f flower
```

**Detener servicios:**
```bash
docker-compose down
```

---

## 🌐 Flower UI

### Acceso

```
URL: http://localhost:5555
Usuario: admin
Contraseña: (configurada en FLOWER_BASIC_AUTH en .env)
```

### Funcionalidades

**Dashboard:**
- Estado de workers activos
- Número de tareas completadas, fallidas, pendientes
- Gráficos de tiempo real

**Tasks:**
- Lista de todas las tareas ejecutadas
- Filtrar por estado (SUCCESS, FAILURE, PENDING, etc.)
- Ver detalles de cada tarea (argumentos, resultado, excepciones)

**Workers:**
- Workers activos
- Pool type (gevent)
- Concurrency (100)
- Estadísticas de cada worker

**Broker:**
- Estado de Redis
- Queues activas
- Mensajes pendientes

**Monitor:**
- Vista en tiempo real de tareas ejecutándose
- Task timeline

---

## 💻 Comandos de Celery CLI

### Worker

**Ejecutar worker standalone:**
```bash
celery -A mikrom.celery_app worker \
  --pool=gevent \
  --concurrency=100 \
  --loglevel=info
```

**Con más opciones:**
```bash
celery -A mikrom.celery_app worker \
  --pool=gevent \
  --concurrency=100 \
  --loglevel=info \
  --max-tasks-per-child=1000 \
  --time-limit=300 \
  --soft-time-limit=280
```

**Ejecutar con script Python:**
```bash
python run_worker.py
```

### Beat (Scheduler)

**Ejecutar Beat standalone:**
```bash
celery -A mikrom.celery_app beat --loglevel=info
```

**Con script Python:**
```bash
python run_beat.py
```

### Flower (Monitoring)

**Ejecutar Flower standalone:**
```bash
celery -A mikrom.celery_app flower \
  --port=5555 \
  --basic_auth=admin:password
```

**Con opciones avanzadas:**
```bash
celery -A mikrom.celery_app flower \
  --port=5555 \
  --basic_auth=admin:password \
  --url_prefix=flower \
  --max_tasks=10000
```

---

## 🔍 Inspeccionar Workers

### Workers Activos

```bash
celery -A mikrom.celery_app inspect active
```

**Output:**
```json
{
  "celery@hostname": [
    {
      "id": "task-id-123",
      "name": "create_vm_task",
      "args": [1, 2, 2048],
      "time_start": 1234567890.123
    }
  ]
}
```

### Estadísticas

```bash
celery -A mikrom.celery_app inspect stats
```

**Output incluye:**
- Total de tareas ejecutadas
- Pool type y concurrency
- Rusage (memoria, CPU)
- Clock offset

### Tareas Registradas

```bash
celery -A mikrom.celery_app inspect registered
```

**Output:**
```
create_vm_task
delete_vm_task
stop_vm_task
start_vm_task
restart_vm_task
```

### Tareas Programadas (Scheduled)

```bash
celery -A mikrom.celery_app inspect scheduled
```

### Tareas Reservadas

```bash
celery -A mikrom.celery_app inspect reserved
```

---

## 🗑️ Gestión de Colas

### Ver Estado de Queues

```bash
celery -A mikrom.celery_app inspect active_queues
```

### Purgar Cola (¡PELIGRO!)

**Eliminar TODAS las tareas pendientes:**
```bash
celery -A mikrom.celery_app purge
```

**Confirmación requerida:**
```
WARNING: This will remove all tasks from queue: mikrom:queue
         Proceed with purge (yes/no)? yes
Purged 42 messages from 1 known task queue.
```

**Purgar sin confirmación:**
```bash
celery -A mikrom.celery_app purge -f
```

---

## 🔄 Control de Workers

### Shutdown Worker

**Graceful shutdown (espera tareas actuales):**
```bash
celery -A mikrom.celery_app control shutdown
```

### Restart Worker Pool

```bash
celery -A mikrom.celery_app control pool_restart
```

### Aumentar/Disminuir Concurrency

**Aumentar:**
```bash
celery -A mikrom.celery_app control pool_grow 10
```

**Disminuir:**
```bash
celery -A mikrom.celery_app control pool_shrink 5
```

---

## 📊 Monitoreo y Eventos

### Ver Eventos en Tiempo Real

```bash
celery -A mikrom.celery_app events
```

**Output:**
```
celery@hostname [2024-02-02 12:34:56,789: INFO] Task create_vm_task[abc-123] received
celery@hostname [2024-02-02 12:34:56,890: INFO] Task create_vm_task[abc-123] started
celery@hostname [2024-02-02 12:34:59,123: INFO] Task create_vm_task[abc-123] succeeded in 2.23s
```

### Capturar Eventos (Dump)

```bash
celery -A mikrom.celery_app events --dump
```

---

## 🧪 Testing y Debugging

### Ejecutar Tarea Manualmente desde Python

```python
from mikrom.worker.tasks import create_vm_task

# Async call (devuelve AsyncResult)
result = create_vm_task.delay(
    vm_db_id=1,
    vcpu_count=2,
    memory_mb=2048,
    kernel_path=None,
    host=None
)

# Get result (blocking)
print(result.get(timeout=10))

# Check status
print(result.status)  # PENDING, STARTED, SUCCESS, FAILURE

# Get task ID
print(result.id)
```

### Ejecutar Tarea con Opciones Avanzadas

```python
# Con countdown (retraso en segundos)
result = create_vm_task.apply_async(
    args=[1, 2, 2048, None, None],
    countdown=60  # Ejecutar en 60 segundos
)

# Con ETA (fecha/hora específica)
from datetime import datetime, timedelta
eta = datetime.now() + timedelta(hours=1)

result = create_vm_task.apply_async(
    args=[1, 2, 2048, None, None],
    eta=eta
)

# Con prioridad (0-9, 9 = máxima)
result = create_vm_task.apply_async(
    args=[1, 2, 2048, None, None],
    priority=9
)

# Con retry
result = create_vm_task.apply_async(
    args=[1, 2, 2048, None, None],
    retry=True,
    retry_policy={
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.2,
    }
)
```

### Ver Resultado de Tarea

```python
result = create_vm_task.delay(1, 2, 2048, None, None)

# Blocking wait
try:
    output = result.get(timeout=10)
    print(f"Success: {output}")
except TimeoutError:
    print("Task timed out")
except Exception as e:
    print(f"Task failed: {e}")

# Non-blocking check
if result.ready():
    if result.successful():
        print(f"Success: {result.result}")
    else:
        print(f"Failed: {result.result}")
else:
    print("Still running...")
```

---

## 📅 Tareas Programadas (Beat)

### Configurar Schedule

Editar `mikrom/celery_app.py`:

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Cada día a las 2 AM
    'cleanup-old-vms': {
        'task': 'mikrom.worker.tasks.cleanup_old_vms',
        'schedule': crontab(hour=2, minute=0),
    },
    
    # Cada hora
    'health-check': {
        'task': 'mikrom.worker.tasks.health_check',
        'schedule': crontab(minute=0),
    },
    
    # Cada 5 minutos
    'sync-status': {
        'task': 'mikrom.worker.tasks.sync_vm_status',
        'schedule': 300.0,  # segundos
    },
    
    # Lunes a Viernes a las 9 AM
    'weekly-report': {
        'task': 'mikrom.worker.tasks.generate_report',
        'schedule': crontab(hour=9, minute=0, day_of_week='1-5'),
    },
}
```

### Formatos de Schedule

**Crontab:**
```python
# Cada minuto
crontab()

# Cada 15 minutos
crontab(minute='*/15')

# Cada hora
crontab(minute=0)

# Cada día a medianoche
crontab(hour=0, minute=0)

# Lunes, Miércoles, Viernes a las 3 PM
crontab(hour=15, minute=0, day_of_week='1,3,5')

# Primer día del mes
crontab(hour=0, minute=0, day_of_month=1)
```

**Intervalos:**
```python
from celery.schedules import schedule

# Cada 30 segundos
schedule(run_every=30.0)

# Cada 10 minutos
schedule(run_every=600.0)
```

---

## 🐛 Debugging

### Ver Traceback de Tarea Fallida

```python
result = create_vm_task.delay(1, 2, 2048, None, None)

if result.failed():
    print(result.traceback)
```

### Logs Detallados

**Worker con debug:**
```bash
celery -A mikrom.celery_app worker --loglevel=debug
```

**Solo tareas específicas:**
```bash
celery -A mikrom.celery_app worker \
  --loglevel=info \
  -Q mikrom:queue \
  --without-gossip \
  --without-mingle
```

---

## 🔧 Configuración Avanzada

### Worker Options

```bash
celery -A mikrom.celery_app worker \
  --pool=gevent \              # Pool type (gevent, prefork, solo, threads)
  --concurrency=100 \          # Número de workers concurrentes
  --loglevel=info \            # Log level (debug, info, warning, error)
  --max-tasks-per-child=1000 \ # Reiniciar worker después de N tareas
  --time-limit=300 \           # Hard timeout (segundos)
  --soft-time-limit=280 \      # Soft timeout (segundos)
  -Q mikrom:queue \            # Queue específica
  -n worker1@%h \              # Nombre del worker
  --autoscale=10,3 \           # Autoscaling (max,min)
  --without-heartbeat \        # Deshabilitar heartbeat
  --without-gossip \           # Deshabilitar gossip
  --without-mingle             # Deshabilitar mingle
```

### Flower Options

```bash
celery -A mikrom.celery_app flower \
  --port=5555 \
  --basic_auth=user1:pass1,user2:pass2 \
  --url_prefix=flower \
  --max_tasks=10000 \
  --persistent=True \
  --db=/var/flower/flower.db \
  --broker_api=redis://localhost:6379/0
```

---

## 📚 Referencias

- [Documentación oficial de Celery](https://docs.celeryq.dev/)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Redis Documentation](https://redis.io/documentation)

---

## ⚡ Tips y Mejores Prácticas

1. **Usar `.delay()` para casos simples** - Más limpio
2. **Usar `.apply_async()` para control avanzado** - Countdown, ETA, priority
3. **Monitorear Flower regularmente** - Detectar problemas temprano
4. **Configurar alertas** - Prometheus + Grafana
5. **Logs estructurados** - Ya configurados en mikrom
6. **Retry automático** - Ya configurado (max_retries=3)
7. **Task timeout** - 5 minutos configurado
8. **No bloquear el event loop** - Usar async/await correctamente
