from uuid import UUID

from app.db.supabase_client import get_supabase_client
from app.schemas.report import ReportMetrics, ReportRecord


def save_report(
    scan_id: str | UUID, summary_markdown: str, metrics: ReportMetrics, risk_score: float
) -> ReportRecord:
    """Persist a generated report to the reports table.

    Args:
        scan_id: The scan UUID (accepts str or UUID)
        summary_markdown: The report markdown content
        metrics: ReportMetrics instance with findings summary
        risk_score: Overall risk score (0-1)

    Returns:
        ReportRecord: The persisted report record
    """
    client = get_supabase_client()
    payload = {
        "scan_id": str(scan_id),
        "summary_markdown": summary_markdown,
        "metrics": metrics.model_dump(),
        "risk_score": risk_score,
    }
    result = client.table("reports").insert(payload).execute()
    row = result.data[0]
    return ReportRecord(**row)


def get_report_by_scan_id(scan_id: str | UUID) -> ReportRecord | None:
    """Retrieve a report by scan_id.

    Args:
        scan_id: The scan UUID to look up (accepts str or UUID)

    Returns:
        ReportRecord | None: The report if found, None otherwise
    """
    client = get_supabase_client()
    result = client.table("reports").select("*").eq("scan_id", str(scan_id)).execute()
    if not result.data:
        return None
    return ReportRecord(**result.data[0])
