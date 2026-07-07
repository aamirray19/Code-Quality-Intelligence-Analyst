from uuid import UUID

from fastapi import APIRouter

from app.core.errors import AppError
from app.schemas.report import ReportRecord
from app.services import report_service, scan_service

router = APIRouter()


@router.get("/scans/{scan_id}/report", response_model=ReportRecord)
def get_report(scan_id: UUID) -> ReportRecord:
    """Retrieve the code quality report for a scan.

    Args:
        scan_id: The scan UUID

    Returns:
        ReportRecord: The report with summary, metrics, and risk score

    Raises:
        AppError: SCAN_NOT_FOUND (404) if scan doesn't exist
        AppError: SCAN_NOT_ANALYZED (409) if scan hasn't reached analyzed/reported status
        AppError: REPORT_NOT_FOUND (404) if report doesn't exist yet
    """
    # Check scan exists
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", "Scan not found.", 404)

    # Check scan has been analyzed
    if scan.status not in ("analyzed", "reported"):
        raise AppError(
            "SCAN_NOT_ANALYZED",
            "Scan has not been analyzed yet.",
            409,
        )

    # Retrieve the report
    report = report_service.get_report_by_scan_id(scan_id)
    if report is None:
        raise AppError("REPORT_NOT_FOUND", "Report not found.", 404)

    return report
