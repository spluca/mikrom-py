"""Celery application configuration."""

from celery import Celery
from kombu import Queue
from mikrom.config import settings

# Crear app Celery
celery_app = Celery(
    "mikrom-worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Configuración principal
celery_app.conf.update(
    # Serialización
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Timeout y reintentos
    task_time_limit=300,  # 5 minutos (igual que arq)
    task_soft_time_limit=280,  # Advertencia antes del límite
    task_acks_late=True,  # Confirmar solo después de completar
    worker_prefetch_multiplier=1,  # Un job a la vez
    # Results
    result_expires=3600,  # 1 hora (igual que arq keep_result)
    result_backend_transport_options={
        "master_name": "mikrom",
    },
    # Cola
    task_default_queue=settings.CELERY_QUEUE_NAME,
    task_queues=(Queue(settings.CELERY_QUEUE_NAME, routing_key="mikrom.#"),),
    # Worker
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=True,
    # Imports
    imports=("mikrom.worker.tasks",),
    # Beat scheduler (para tareas programadas)
    beat_schedule={
        # Ejemplo: cleanup de tareas viejas cada día a las 2am
        # 'cleanup-old-results': {
        #     'task': 'mikrom.worker.tasks.cleanup_old_results',
        #     'schedule': crontab(hour=2, minute=0),
        # },
    },
    # Beat schedule file location (writable by appuser)
    beat_schedule_filename="/tmp/celerybeat-schedule",
)
