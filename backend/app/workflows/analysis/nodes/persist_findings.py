import asyncio
from datetime import datetime, timezone

from app.services import scan_event_service
from app.workflows.analysis.state import AnalysisState


def _persist(scan_id, findings: list[dict]) -> int:
    from app.db.supabase_client import get_supabase_client

    if not findings:
        return 0

    client = get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    payload = [
        {
            "scan_id": str(scan_id),
            # NB: internal in-memory findings use "agent" as the field name,
            # but the `findings` table column is `primary_agent` (phase3.md §16.3).
            "primary_agent": f["agent"],
            "title": f["title"],
            "description": f["description"],
            "severity": f["severity"],
            "confidence": f["confidence"],
            "file_id": f["file_id"],
            "symbol_id": f["symbol_id"],
            "file_path": f["file_path"],
            "symbol_name": f["symbol_name"],
            "start_line": f["start_line"],
            "end_line": f["end_line"],
            "evidence": f["evidence"],
            "recommendation": f["recommendation"],
            "fingerprint": f["fingerprint"],
            "related_agents": f["related_agents"],
            "updated_at": now,
        }
        for f in findings
    ]
    client.table("findings").upsert(payload, on_conflict="scan_id,fingerprint").execute()
    return len(payload)


async def persist_findings(state: AnalysisState) -> dict:
    scan_id = state["scan_id"]
    count = await asyncio.to_thread(_persist, scan_id, state.get("ranked_findings", []))

    await asyncio.to_thread(
        scan_event_service.create_event, scan_id, "findings_stored", f"Stored {count} findings."
    )
    return {"status": "findings_persisted"}
