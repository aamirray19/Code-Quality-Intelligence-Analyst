import asyncio
from datetime import datetime, timezone

from app.services import scan_event_service, scan_service
from app.workflows.analysis.state import AnalysisState


async def mark_scan_analyzed(state: AnalysisState) -> dict:
    scan_id = state["scan_id"]
    await asyncio.to_thread(
        scan_service.update_scan, scan_id, status="analyzed", updated_at=datetime.now(timezone.utc)
    )
    await asyncio.to_thread(
        scan_event_service.create_event, scan_id, "analysis_completed", "Phase 3 analysis completed."
    )
    return {"status": "analyzed"}
