from datetime import datetime, timezone

from rq import Queue

from app.core.config import settings
from app.core.errors import AppError
from app.db.supabase_client import get_supabase_client
from app.schemas.repos import ValidatedRepository
from app.schemas.scans import ScanRecord
from app.workers.redis_connection import get_redis_connection


def enqueue_scan(scan: ScanRecord, repo: ValidatedRepository) -> str:
    payload = {
        "job_type": "repo_scan",
        "scan_id": str(scan.id),
        "repo": {
            "owner": repo.owner,
            "name": repo.name,
            "full_name": repo.full_name,
            "branch": repo.branch,
            "default_branch": repo.default_branch,
            "clone_url": repo.clone_url,
            "html_url": repo.html_url,
            "size_kb": repo.size_kb,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        connection = get_redis_connection()
        queue = Queue(settings.redis_queue_name, connection=connection)
        # RQ's default job_timeout (180s) is far shorter than a full scan can
        # legitimately take: phase 3 alone runs up to 5 concurrent LLM agents,
        # each allowed AGENT_TIMEOUT_SECONDS * (AGENT_MAX_RETRIES + 1). RQ
        # force-kills the job at the timeout via an async exception that can
        # strike anywhere in the call stack, bypassing this app's own
        # try/except error handling and leaving the scan stuck "running"
        # forever with no recorded failure.
        job_timeout = max(
            1800, settings.agent_timeout_seconds * (settings.agent_max_retries + 1) * 6
        )
        job = queue.enqueue(
            "app.workers.jobs.process_repo_scan", payload, job_timeout=job_timeout
        )
    except Exception as exc:
        raise AppError("QUEUE_ERROR", "Failed to queue scan job.", 500) from exc

    client = get_supabase_client()
    client.table("scan_events").insert(
        {
            "scan_id": str(scan.id),
            "event_type": "job_queued",
            "message": "Scan job queued to Redis.",
            "metadata": payload,
        }
    ).execute()

    return job.id
