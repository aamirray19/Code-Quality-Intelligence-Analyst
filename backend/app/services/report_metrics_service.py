"""Service for computing report metrics from findings."""

from app.schemas.finding import FindingRecord
from app.schemas.report import ReportMetrics


def compute_report_metrics(findings: list[FindingRecord]) -> ReportMetrics:
    """Compute structured metrics from findings for report embedding.

    Populates:
    - total_findings: count of findings
    - by_severity: dict counting findings per severity value
    - by_agent: dict counting findings per agent value
    - files_affected: count of unique non-null file_path values

    Args:
        findings: List of FindingRecord objects to analyze.

    Returns:
        ReportMetrics instance with aggregated counts.
    """
    by_severity = {}
    by_agent = {}
    unique_files = set()

    for finding in findings:
        # Count by severity
        severity = finding.severity
        by_severity[severity] = by_severity.get(severity, 0) + 1

        # Count by agent
        agent = finding.agent
        by_agent[agent] = by_agent.get(agent, 0) + 1

        # Track unique non-null file paths
        if finding.file_path:
            unique_files.add(finding.file_path)

    return ReportMetrics(
        total_findings=len(findings),
        by_severity=by_severity,
        by_agent=by_agent,
        files_affected=len(unique_files),
    )
