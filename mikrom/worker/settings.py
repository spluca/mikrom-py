"""arq worker settings."""

from arq.connections import RedisSettings
from mikrom.config import settings
from mikrom.worker.tasks import (
    create_vm_task,
    delete_vm_task,
    stop_vm_task,
    start_vm_task,
    restart_vm_task,
)


def get_redis_settings() -> RedisSettings:
    """Parse Redis URL and return RedisSettings object."""
    # Parse redis://host:port or redis://host:port/db format
    url = settings.REDIS_URL

    # Simple URL parsing for redis://host:port or redis://host:port/db
    if url.startswith("redis://"):
        url = url[8:]  # Remove redis://

    # Split host:port and optional /db
    if "/" in url:
        host_port, db = url.split("/", 1)
        db = int(db)
    else:
        host_port = url
        db = 0

    # Split host and port
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host = host_port
        port = 6379

    # Force IPv4 by converting localhost to 127.0.0.1
    if host == "localhost":
        host = "127.0.0.1"

    return RedisSettings(host=host, port=port, database=db)


class WorkerSettings:
    """arq worker configuration."""

    redis_settings = get_redis_settings()
    queue_name = settings.ARQ_QUEUE_NAME

    functions = [
        create_vm_task,
        delete_vm_task,
        stop_vm_task,
        start_vm_task,
        restart_vm_task,
    ]

    # Worker settings
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    keep_result = 3600  # Keep results for 1 hour
