"""Service for deduplicating findings.

Adapted from app.workflows.analysis.nodes.deduplicate_findings.py.
Uses two-pass grouping: first by fingerprint, then by loose merge key.
"""

from app.schemas.finding import FindingRecord

# Severity order for tie-breaking (lower number = higher severity)
SEVERITY_ORDER = {"extreme": 0, "high": 1, "medium": 2, "low": 3}


def _merge_key(finding: FindingRecord) -> tuple:
    """Generate a loose merge key for cross-agent deduplication."""
    return (
        finding.file_path,
        finding.symbol_name,
        finding.start_line,
        finding.end_line,
        finding.title.strip().lower(),
    )


def deduplicate_findings(findings: list[FindingRecord]) -> list[FindingRecord]:
    """Deduplicate findings using fingerprint-based grouping.

    Two-pass approach:
    1. Group by exact fingerprint
    2. Merge groups sharing (file_path, symbol_name, start_line, end_line, title)

    Within each merged group:
    - Pick the finding with highest severity as primary
    - Record other agents in related_agents

    Args:
        findings: List of FindingRecord objects to deduplicate

    Returns:
        List of deduplicated FindingRecord objects with related_agents populated
    """
    if not findings:
        return []

    # First pass: group by fingerprint
    groups: dict[str, list[FindingRecord]] = {}
    for finding in findings:
        groups.setdefault(finding.fingerprint, []).append(finding)

    # Second pass: merge across agents using the loose cross-agent key
    merged_by_loose_key: dict[tuple, list[FindingRecord]] = {}
    for group in groups.values():
        loose_key = _merge_key(group[0])
        merged_by_loose_key.setdefault(loose_key, []).extend(group)

    # For each merged group, pick primary and record related agents
    deduped: list[FindingRecord] = []
    for group in merged_by_loose_key.values():
        # Sort by severity (most severe first) for primary selection
        group_sorted = sorted(group, key=lambda f: SEVERITY_ORDER.get(f.severity, 3))
        primary = group_sorted[0]

        # Collect related agents (excluding the primary's agent)
        related_agents = sorted({f.agent for f in group if f.agent != primary.agent})

        # Create new FindingRecord with updated related_agents
        deduped_finding = FindingRecord(
            id=primary.id,
            scan_id=primary.scan_id,
            agent=primary.agent,
            title=primary.title,
            description=primary.description,
            severity=primary.severity,
            confidence=primary.confidence,
            file_id=primary.file_id,
            symbol_id=primary.symbol_id,
            file_path=primary.file_path,
            symbol_name=primary.symbol_name,
            start_line=primary.start_line,
            end_line=primary.end_line,
            evidence=primary.evidence,
            recommendation=primary.recommendation,
            fingerprint=primary.fingerprint,
            related_agents=related_agents,
            created_at=primary.created_at,
        )
        deduped.append(deduped_finding)

    return deduped
