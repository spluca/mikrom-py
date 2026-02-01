"""arq worker settings."""

from mikrom.config import settings
from mikrom.worker.tasks import create_vm_task, delete_vm_task


class WorkerSettings:
    """arq worker configuration."""

    redis_settings = settings.REDIS_URL
    queue_name = settings.ARQ_QUEUE_NAME

    functions = [create_vm_task, delete_vm_task]

    # Worker settings
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # Keep results for 1 hour
