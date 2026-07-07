from uuid import UUID

from fastapi import APIRouter, Query

from app.core.errors import AppError
from app.schemas.finding import FindingRecord
from app.services import finding_query_service, scan_service

router = APIRouter()


@router.get("/scans/{scan_id}/findings", response_model=list[FindingRecord])
def get_findings(
    scan_id: UUID,
    severity: str | None = Query(default=None),
    agent: str | None = Query(default=None),
    file_path: str | None = Query(default=None),
) -> list[FindingRecord]:
    """Retrieve findings for a scan, optionally filtered by severity, agent, or file path.

    Args:
        scan_id: The scan UUID
        severity: Optional exact-match filter for severity (e.g., "critical", "high", "medium", "low")
        agent: Optional exact-match filter for agent name (e.g., "security", "performance")
        file_path: Optional exact-match filter for file path (e.g., "auth.py", "src/utils.py")

    Returns:
        list[FindingRecord]: List of findings (possibly filtered)

    Raises:
        AppError: SCAN_NOT_FOUND (404) if scan doesn't exist
        AppError: SCAN_NOT_ANALYZED (409) if scan hasn't reached analyzed/reported status
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

    # Fetch all findings for the scan
    findings = finding_query_service.fetch_findings_for_scan(scan_id)

    # Apply filters if provided
    if severity is not None:
        findings = [f for f in findings if f.severity == severity]

    if agent is not None:
        findings = [f for f in findings if f.agent == agent]

    if file_path is not None:
        findings = [f for f in findings if f.file_path == file_path]

    return findings
