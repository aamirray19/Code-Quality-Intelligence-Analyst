"""Entrypoint for the Phase 2 RQ worker.

Run with:
    uv run python run_worker.py
or
    .venv/Scripts/python.exe run_worker.py

Listens on `settings.redis_queue_name` (default: repo_scan_queue) and
processes jobs with `app.workers.jobs.process_repo_scan`.
"""

import os

from rq import SimpleWorker, Worker

from app.core.config import settings
from app.workers.redis_connection import get_redis_connection


def main() -> None:
    connection = get_redis_connection()
    # RQ's default Worker forks a subprocess per job, which is unsupported on
    # Windows. Fall back to SimpleWorker (runs jobs in-process) there; use the
    # regular forking Worker on POSIX deployment targets (e.g. Render).
    worker_class = SimpleWorker if os.name == "nt" else Worker
    worker = worker_class([settings.redis_queue_name], connection=connection)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
