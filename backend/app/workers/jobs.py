from app.workers.repo_scan_worker import process_repo_scan as _process_repo_scan


def process_repo_scan(payload: dict) -> None:
    """Phase 2 job target for the repo_scan_queue.

    Enqueued by Phase 1 (`queue_service.enqueue_scan`) and consumed by the RQ
    worker started via `run_worker.py`. Delegates to the actual Phase 2
    orchestration in `app.workers.repo_scan_worker`.
    """
    _process_repo_scan(payload)
