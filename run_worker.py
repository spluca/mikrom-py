"""Run arq worker for background tasks."""

from arq import run_worker
from mikrom.worker.settings import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)
