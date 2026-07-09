from uuid import UUID

from app.db.supabase_client import get_supabase_client


def create_event(
    scan_id: UUID, event_type: str, message: str, metadata: dict | None = None
) -> None:
    client = get_supabase_client()
    client.table("scan_events").insert(
        {
            "scan_id": str(scan_id),
            "event_type": event_type,
            "message": message,
            "metadata": metadata,
        }
    ).execute()
