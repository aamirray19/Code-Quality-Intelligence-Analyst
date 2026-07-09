from uuid import UUID

from app.db.supabase_client import get_supabase_client
from app.schemas.files import DiscoveredFile, ScanFileRecord


def store_discovered_files(files: list[DiscoveredFile]) -> list[ScanFileRecord]:
    """Upsert discovered file inventory rows into `scan_files`.

    Upserts on (scan_id, relative_path) so re-running a scan is idempotent.
    Returns the stored rows (with Supabase-assigned `id`s) in the same order
    as `files`.
    """
    if not files:
        return []

    client = get_supabase_client()
    payload = [
        {
            "scan_id": str(f.scan_id),
            "relative_path": f.relative_path,
            "file_name": f.file_name,
            "extension": f.extension,
            "language": f.language,
            "size_bytes": f.size_bytes,
            "line_count": f.line_count,
            "content_hash": f.content_hash,
            "is_supported": f.is_supported,
            "parse_status": f.parse_status,
            "skip_reason": f.skip_reason,
        }
        for f in files
    ]

    result = (
        client.table("scan_files")
        .upsert(payload, on_conflict="scan_id,relative_path")
        .execute()
    )
    return [ScanFileRecord(**row) for row in result.data]


def update_file_parse_status(
    file_id: UUID, parse_status: str, parse_error: str | None = None
) -> None:
    client = get_supabase_client()
    client.table("scan_files").update(
        {"parse_status": parse_status, "parse_error": parse_error}
    ).eq("id", str(file_id)).execute()


def list_scan_files(
    scan_id: UUID,
    status: str | None = None,
    language: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ScanFileRecord], int]:
    client = get_supabase_client()
    query = client.table("scan_files").select("*", count="exact").eq("scan_id", str(scan_id))
    if status is not None:
        query = query.eq("parse_status", status)
    if language is not None:
        query = query.eq("language", language)

    result = query.range(offset, offset + limit - 1).execute()
    items = [ScanFileRecord(**row) for row in result.data]
    total = result.count if result.count is not None else len(items)
    return items, total


def get_scan_files(scan_id: UUID) -> list[ScanFileRecord]:
    client = get_supabase_client()
    result = client.table("scan_files").select("*").eq("scan_id", str(scan_id)).execute()
    return [ScanFileRecord(**row) for row in result.data]
