from datetime import datetime, timezone
from uuid import UUID

from app.db.supabase_client import get_supabase_client
from app.schemas.repos import ValidatedRepository
from app.schemas.scans import ScanRecord


def create_scan(repo: ValidatedRepository, github_url: str) -> ScanRecord:
    client = get_supabase_client()
    payload = {
        "github_url": github_url,
        "repo_owner": repo.owner,
        "repo_name": repo.name,
        "repo_full_name": repo.full_name,
        "branch": repo.branch,
        "default_branch": repo.default_branch,
        "clone_url": repo.clone_url,
        "html_url": repo.html_url,
        "repo_size_kb": repo.size_kb,
        "status": "queued",
    }
    result = client.table("scans").insert(payload).execute()
    row = result.data[0]

    client.table("scan_events").insert(
        {
            "scan_id": row["id"],
            "event_type": "scan_created",
            "message": "Scan record created.",
        }
    ).execute()

    return ScanRecord(**row)


def get_scan(scan_id: UUID) -> ScanRecord | None:
    client = get_supabase_client()
    result = client.table("scans").select("*").eq("id", str(scan_id)).limit(1).execute()
    if not result.data:
        return None
    return ScanRecord(**result.data[0])


def update_scan_status(scan_id: UUID, status: str, error_message: str | None = None) -> None:
    client = get_supabase_client()
    client.table("scans").update(
        {
            "status": status,
            "error_message": error_message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", str(scan_id)).execute()


def update_scan(scan_id: UUID, **fields) -> None:
    """Generic partial update of a scan row (Phase 2 status/phase/timestamps).

    Example: update_scan(scan_id, status="cloning", phase="phase_2", started_at=now)
    """
    if not fields:
        return
    payload = dict(fields)
    for key in ("started_at", "parsed_at", "reported_at", "failed_at"):
        value = payload.get(key)
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    client = get_supabase_client()
    client.table("scans").update(payload).eq("id", str(scan_id)).execute()
