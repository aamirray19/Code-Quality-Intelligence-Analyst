"""Service for ranking findings by severity and other criteria.

Adapted from app.workflows.analysis.nodes.rank_findings.py.
"""

from app.schemas.finding import FindingRecord

# Severity order for sorting (lower number = higher severity)
SEVERITY_ORDER = {"extreme": 0, "high": 1, "medium": 2, "low": 3}


def _sort_key(finding: FindingRecord) -> tuple:
    """Generate sort key for findings.

    Sort order:
    1. Severity (extreme > high > medium > low)
    2. Confidence (higher first, so negate)
    3. Evidence count (more first, so negate)
    4. Related agents count (more first, so negate)
    """
    return (
        SEVERITY_ORDER.get(finding.severity, 3),
        -finding.confidence,
        -len(finding.evidence or []),
        -len(finding.related_agents or []),
    )


def rank_findings(findings: list[FindingRecord]) -> list[FindingRecord]:
    """Rank findings by severity, confidence, evidence, and related agents.

    Args:
        findings: List of FindingRecord objects to rank

    Returns:
        Sorted list of FindingRecord objects (most important first)
    """
    return sorted(findings, key=_sort_key)
