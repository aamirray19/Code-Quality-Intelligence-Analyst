from uuid import uuid4

import pytest

from app.schemas.finding import FindingRecord
from app.services.severity_ranking_service import rank_findings


def _finding_record(severity, confidence=0.7, evidence_count=0, related_agents_count=0, **overrides):
    """Create a FindingRecord for testing."""
    defaults = {
        "scan_id": uuid4(),
        "agent": "security",
        "title": "Issue",
        "description": "desc",
        "severity": severity,
        "confidence": confidence,
        "file_path": "app/main.py",
        "symbol_name": "handler",
        "start_line": 10,
        "end_line": 20,
        "evidence": [f"evidence{i}" for i in range(evidence_count)],
        "recommendation": None,
        "fingerprint": f"fp{uuid4()}",
        "related_agents": [f"agent{i}" for i in range(related_agents_count)],
    }
    defaults.update(overrides)
    return FindingRecord(**defaults)


def test_rank_findings_sorts_by_severity_first():
    """Findings should be sorted by severity (extreme > high > medium > low)."""
    findings = [
        _finding_record("low"),
        _finding_record("extreme"),
        _finding_record("medium"),
        _finding_record("high"),
    ]
    
    ranked = rank_findings(findings)
    
    severities = [f.severity for f in ranked]
    assert severities == ["extreme", "high", "medium", "low"]


def test_rank_findings_uses_confidence_as_tiebreaker():
    """Within same severity, higher confidence should come first."""
    findings = [
        _finding_record("high", confidence=0.5),
        _finding_record("high", confidence=0.9),
        _finding_record("high", confidence=0.7),
    ]
    
    ranked = rank_findings(findings)
    
    confidences = [f.confidence for f in ranked]
    assert confidences == [0.9, 0.7, 0.5]


def test_rank_findings_uses_evidence_count_as_second_tiebreaker():
    """Within same severity and confidence, more evidence comes first."""
    findings = [
        _finding_record("high", confidence=0.8, evidence_count=1),
        _finding_record("high", confidence=0.8, evidence_count=3),
        _finding_record("high", confidence=0.8, evidence_count=2),
    ]
    
    ranked = rank_findings(findings)
    
    evidence_counts = [len(f.evidence) for f in ranked]
    assert evidence_counts == [3, 2, 1]


def test_rank_findings_uses_related_agents_count_as_third_tiebreaker():
    """Within same severity/confidence/evidence, more related agents comes first."""
    findings = [
        _finding_record("high", confidence=0.8, evidence_count=2, related_agents_count=0),
        _finding_record("high", confidence=0.8, evidence_count=2, related_agents_count=2),
        _finding_record("high", confidence=0.8, evidence_count=2, related_agents_count=1),
    ]
    
    ranked = rank_findings(findings)
    
    related_counts = [len(f.related_agents) for f in ranked]
    assert related_counts == [2, 1, 0]


def test_rank_findings_applies_all_sort_keys_together():
    """All sort keys should work together correctly."""
    findings = [
        _finding_record("medium", confidence=0.9, evidence_count=5),
        _finding_record("high", confidence=0.6, evidence_count=1),
        _finding_record("high", confidence=0.8, evidence_count=2, related_agents_count=1),
        _finding_record("extreme", confidence=0.5, evidence_count=0),
        _finding_record("high", confidence=0.8, evidence_count=2, related_agents_count=0),
    ]
    
    ranked = rank_findings(findings)
    
    # extreme first, then highs sorted by confidence/evidence/related_agents, then medium
    assert ranked[0].severity == "extreme"
    assert ranked[1].severity == "high" and ranked[1].confidence == 0.8 and len(ranked[1].related_agents) == 1
    assert ranked[2].severity == "high" and ranked[2].confidence == 0.8 and len(ranked[2].related_agents) == 0
    assert ranked[3].severity == "high" and ranked[3].confidence == 0.6
    assert ranked[4].severity == "medium"


def test_rank_findings_returns_empty_list_for_empty_input():
    """Empty input should return empty list."""
    assert rank_findings([]) == []


def test_rank_findings_handles_single_finding():
    """Single finding should pass through unchanged."""
    findings = [_finding_record("high")]
    
    ranked = rank_findings(findings)
    
    assert len(ranked) == 1
    assert ranked[0].severity == "high"
