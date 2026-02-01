"""Run arq worker for background tasks."""

import asyncio
import logging
from arq.worker import create_worker
from mikrom.worker.settings import WorkerSettings

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def main():
    """Run the worker."""
    worker = create_worker(WorkerSettings)
    await worker.main()


if __name__ == "__main__":
    asyncio.run(main())
