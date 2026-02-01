"""Run arq worker for background tasks."""

import asyncio
from arq import run_worker
from mikrom.worker.settings import WorkerSettings

if __name__ == "__main__":
    # Python 3.14 compatibility: explicitly create event loop
    # In Python 3.14+, asyncio.get_event_loop() no longer creates a loop automatically
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    run_worker(WorkerSettings)
