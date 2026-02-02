# Migración de arq a Celery + Redis + Flower

## 📋 Resumen

Este documento describe la migración completa del sistema de workers de **arq** a **Celery** con **Redis** como broker/backend y **Flower** para monitoreo web.

**Fecha de migración:** Febrero 2025  
**Versión de Celery:** 5.4.0+  
**Tipo de migración:** Limpia (sin mantener compatibilidad con arq)

---

## 🎯 Objetivos de la Migración

1. **Mayor madurez y ecosistema:** Celery tiene más de 10 años, comunidad grande, y documentación extensa
2. **Monitoreo mejorado:** Flower UI para visualizar tareas y workers en tiempo real
3. **Scheduling:** Celery Beat para tareas programadas (cron-like)
4. **Retry automático:** Política de reintentos configurada a nivel de decorador
5. **Preparación para escalar:** Task routing, prioridades, múltiples queues

---

## 📊 Comparación: arq vs Celery

| Característica | arq (Antes) | Celery (Ahora) |
|----------------|-------------|----------------|
| **Async support** | ✅ Nativo | ✅ Con gevent pool |
| **Monitoring UI** | ❌ No | ✅ Flower |
| **Scheduler** | ❌ No | ✅ Celery Beat |
| **Retry automático** | ❌ Manual | ✅ Decorador |
| **Comunidad** | ⚠️ Pequeña | ✅ Grande |
| **Documentación** | ⚠️ Básica | ✅ Extensa |
| **Task routing** | ⚠️ Limitado | ✅ Avanzado |
| **Production ready** | ✅ Sí | ✅ Muy probado |

---

## 🔄 Cambios Realizados

### 1. Dependencias (`pyproject.toml`)

**Eliminado:**
- `arq`

**Agregado:**
- `celery[redis]>=5.4.0` - Core de Celery con soporte Redis
- `flower>=2.0.0` - UI de monitoreo web
- `gevent>=24.2.1` - Pool async para mantener async/await

### 2. Nueva Estructura de Archivos

```
mikrom-py/
├── mikrom/
│   ├── celery_app.py          # NUEVO - Configuración de Celery
│   ├── config.py               # MODIFICADO - Variables de Flower
│   ├── worker/
│   │   ├── tasks.py            # MODIFICADO - Decoradores Celery
│   │   └── settings.py         # ELIMINADO - Ya no necesario
│   └── services/
│       └── vm_service.py       # MODIFICADO - Usa .delay()
├── run_worker.py               # MODIFICADO - Celery worker
├── run_beat.py                 # NUEVO - Celery Beat scheduler
├── docker-compose.yml          # MODIFICADO - Worker, Beat, Flower
└── .env.example                # MODIFICADO - FLOWER_BASIC_AUTH
```

### 3. Configuración de Celery (`mikrom/celery_app.py`)

Características principales:
- Redis como broker y backend
- Pool gevent para async/await
- Timeout de 5 minutos (igual que arq)
- Queue name: `mikrom:queue` (compatible)
- Result expiration: 1 hora
- Max retry: 3 intentos por tarea
- Worker max tasks per child: 1000

Ver archivo completo: `mikrom/celery_app.py`

### 4. Tasks Convertidas

Todas las 5 tareas fueron migradas:

**Patrón de migración:**

**Antes (arq):**
```python
async def create_vm_task(
    ctx: dict,
    vm_db_id: int,
    ...
) -> dict:
    # código
```

**Después (Celery):**
```python
@celery_app.task(name="create_vm_task", bind=True, max_retries=3)
async def create_vm_task(
    self,
    vm_db_id: int,
    ...
) -> dict:
    # Agregar task_id al tracing
    add_span_attributes(**{"celery.task_id": self.request.id})
    # código
```

**Tareas migradas:**
- ✅ `create_vm_task`
- ✅ `delete_vm_task`
- ✅ `stop_vm_task`
- ✅ `start_vm_task`
- ✅ `restart_vm_task`

### 5. Service Layer

**Patrón de enqueue actualizado:**

**Antes (arq):**
```python
redis = await self.get_redis_pool()
job = await redis.enqueue_job("create_vm_task", vm.id, ...)
logger.info("Job queued", extra={"job_id": job.job_id})
```

**Después (Celery):**
```python
result = create_vm_task.delay(vm.id, ...)
logger.info("Job queued", extra={"job_id": result.id})
```

**Cambios:**
- Eliminado `get_redis_pool()` - Celery maneja conexiones
- Método `close()` simplificado - No hay pool que cerrar
- `.delay()` para enqueue simple
- `.apply_async()` disponible para opciones avanzadas (ETA, countdown, routing)

### 6. Docker Compose

**Servicios:**

**Worker (actualizado):**
```yaml
command: celery -A mikrom.celery_app worker --pool=gevent --concurrency=100 --loglevel=info
restart: unless-stopped
```

**Beat (nuevo):**
```yaml
command: celery -A mikrom.celery_app beat --loglevel=info
restart: unless-stopped
```

**Flower (nuevo):**
```yaml
command: celery -A mikrom.celery_app flower --port=5555 --basic_auth=${FLOWER_BASIC_AUTH}
ports:
  - "5555:5555"
restart: unless-stopped
```

### 7. Variables de Entorno

**Agregadas en `.env`:**
```bash
# Celery/Redis
CELERY_QUEUE_NAME=mikrom:queue

# Flower UI
FLOWER_BASIC_AUTH=admin:password_segura_aqui
FLOWER_PORT=5555
```

---

## 🧪 Testing

### Resultados

**Tests de Worker:**
```
tests/test_worker/test_task_logging.py
✅ test_create_vm_logs_all_steps - PASSED
✅ test_create_vm_logs_error_and_cleanup - PASSED
✅ test_delete_vm_logs_all_steps - PASSED
✅ test_delete_vm_continues_on_partial_failure - PASSED

4/4 tests PASANDO
```

### Cambios en Tests

Eliminado parámetro `ctx` de llamadas:

**Antes:**
```python
await create_vm_task(ctx={}, vm_db_id=1, vcpu_count=2, memory_mb=2048)
```

**Después:**
```python
await create_vm_task(vm_db_id=1, vcpu_count=2, memory_mb=2048)
```

---

## 🚀 Uso del Sistema

Ver documentación completa en: [`CELERY_USAGE.md`](./CELERY_USAGE.md)

### Quick Start

**1. Iniciar servicios (Docker):**
```bash
docker-compose up -d
```

**2. Ver logs:**
```bash
docker-compose logs -f worker
docker-compose logs -f beat
docker-compose logs -f flower
```

**3. Acceder a Flower:**
```
URL: http://localhost:5555
Usuario: admin
Password: (ver FLOWER_BASIC_AUTH en .env)
```

---

## 🔒 Seguridad

### Configuración de Producción

1. **Cambiar credenciales de Flower:**
   ```bash
   FLOWER_BASIC_AUTH=usuario_produccion:contraseña_muy_segura_123
   ```

2. **Usar HTTPS para Flower** (nginx reverse proxy)

3. **Restringir acceso por IP:**
   - Firewall
   - Nginx `allow/deny`

4. **Redis con contraseña** (recomendado)

---

## 📖 Documentación Adicional

- [Uso de Celery](./CELERY_USAGE.md) - Comandos y operaciones diarias
- [Deployment en Producción](./CELERY_DEPLOYMENT.md) - Supervisor, systemd, monitoreo
- [Troubleshooting](./CELERY_TROUBLESHOOTING.md) - Solución de problemas comunes

---

## ✅ Checklist de Migración Completada

- [x] Dependencias actualizadas
- [x] `mikrom/celery_app.py` creado
- [x] Settings actualizados con variables de Flower
- [x] 5 tareas convertidas a decoradores Celery
- [x] `mikrom/worker/settings.py` eliminado
- [x] Service layer actualizado (`.delay()`)
- [x] `run_worker.py` actualizado (gevent pool)
- [x] `run_beat.py` creado
- [x] Tests actualizados (4/4 pasando)
- [x] Docker Compose con worker, beat, flower
- [x] `.env.example` actualizado
- [x] Documentación completa

---

## 🎉 Resultado

✅ **Migración completada exitosamente**

- Sistema de workers robusto con Celery
- Pool gevent para tareas async
- Autorestart configurado
- Flower UI con autenticación
- Celery Beat para scheduling
- Producción-ready
