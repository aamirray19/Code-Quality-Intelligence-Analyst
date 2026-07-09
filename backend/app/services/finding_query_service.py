"""Service for querying findings from Supabase."""

from uuid import UUID

from app.db.supabase_client import get_supabase_client
from app.schemas.finding import FindingRecord


def fetch_findings_for_scan(scan_id: str | UUID) -> list[FindingRecord]:
    """Fetch all findings for a given scan from Supabase.

    Args:
        scan_id: The scan UUID (as string or UUID object)

    Returns:
        List of FindingRecord objects. Empty list if no findings exist.

    Note:
        Maps DB's `primary_agent` column to FindingRecord's `agent` field.
    """
    client = get_supabase_client()
    result = client.table("findings").select("*").eq("scan_id", str(scan_id)).execute()

    if not result.data:
        return []

    findings = []
    for row in result.data:
        # Rename primary_agent -> agent to match FindingRecord schema
        row_copy = dict(row)
        row_copy["agent"] = row_copy.pop("primary_agent")
        findings.append(FindingRecord(**row_copy))

    return findings
