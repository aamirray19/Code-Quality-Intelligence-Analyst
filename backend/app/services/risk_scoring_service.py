"""Service for computing risk scores from findings."""

from app.schemas.finding import FindingRecord


def compute_risk_score(findings: list[FindingRecord]) -> float:
    """Compute numeric risk score (0-100) from findings weighted by severity.

    Severity weights:
    - extreme: 10 points each
    - high: 5 points each
    - medium: 2 points each
    - low: 1 point each

    Score is capped at 100.

    Args:
        findings: List of FindingRecord objects to score.

    Returns:
        Risk score as float between 0 and 100.
    """
    severity_weights = {
        "extreme": 10,
        "high": 5,
        "medium": 2,
        "low": 1,
    }

    total_score = sum(severity_weights.get(f.severity, 0) for f in findings)
    return float(min(100, total_score))
