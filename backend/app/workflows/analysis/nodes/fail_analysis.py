import asyncio
from datetime import datetime, timezone

from app.services import scan_event_service, scan_service
from app.workflows.analysis.state import AnalysisState


async def fail_analysis(state: AnalysisState) -> dict:
    scan_id = state["scan_id"]
    errors = state.get("errors") or ["ANALYSIS_FAILED"]
    error_code = errors[0]

    await asyncio.to_thread(
        scan_service.update_scan,
        scan_id,
        status="analysis_failed",
        error_code=error_code,
        error_message="; ".join(errors),
        failed_at=datetime.now(timezone.utc),
    )
    await asyncio.to_thread(
        scan_event_service.create_event,
        scan_id,
        "analysis_failed",
        "Phase 3 analysis failed.",
        {"error_code": error_code},
    )
    return {"status": "failed"}
