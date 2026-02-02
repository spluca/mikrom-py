#!/usr/bin/env python
"""Celery worker entry point with gevent pool for async tasks."""

import logging
from mikrom.celery_app import celery_app

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


if __name__ == "__main__":
    # Start worker with gevent pool for async support
    celery_app.worker_main(
        [
            "worker",
            "--loglevel=info",
            "--pool=gevent",
            "--concurrency=100",  # Gevent puede manejar muchas tareas concurrentes
            "--max-tasks-per-child=1000",
        ]
    )
