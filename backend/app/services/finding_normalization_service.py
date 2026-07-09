"""Service for normalizing FindingRecord objects.

This is a light idempotent normalization pass for Phase 4 report generation.
Input findings are already FindingRecord objects (normalized once in Phase 3),
so this re-applies basic normalization: clamping confidence, normalizing paths.
"""

from app.schemas.finding import FindingRecord


def normalize_findings(findings: list[FindingRecord]) -> list[FindingRecord]:
    """Normalize a list of findings for report generation.

    This is an idempotent normalization pass that:
    - Clamps confidence to [0, 1]
    - Normalizes file paths (forward slashes, strip leading ./)

    Args:
        findings: List of FindingRecord objects to normalize

    Returns:
        List of normalized FindingRecord objects (new instances)
    """
    normalized = []

    for finding in findings:
        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, finding.confidence))

        # Normalize file_path: forward slashes, strip leading ./
        file_path = finding.file_path
        if file_path:
            file_path = file_path.replace("\\", "/")
            file_path = file_path.lstrip("./")

        # Create new FindingRecord with normalized values
        normalized_finding = FindingRecord(
            id=finding.id,
            scan_id=finding.scan_id,
            agent=finding.agent,
            title=finding.title,
            description=finding.description,
            severity=finding.severity,
            confidence=confidence,
            file_id=finding.file_id,
            symbol_id=finding.symbol_id,
            file_path=file_path,
            symbol_name=finding.symbol_name,
            start_line=finding.start_line,
            end_line=finding.end_line,
            evidence=finding.evidence,
            recommendation=finding.recommendation,
            fingerprint=finding.fingerprint,
            related_agents=finding.related_agents,
            created_at=finding.created_at,
        )
        normalized.append(normalized_finding)

    return normalized
