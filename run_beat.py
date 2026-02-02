#!/usr/bin/env python
"""Celery beat scheduler entry point."""

import logging
from mikrom.celery_app import celery_app

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


if __name__ == "__main__":
    celery_app.start(["beat", "--loglevel=info"])
