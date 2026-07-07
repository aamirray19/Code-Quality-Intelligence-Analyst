from uuid import uuid4

import pytest

from app.schemas.finding import FindingRecord
from app.services.finding_deduplication_service import deduplicate_findings


def _finding_record(agent, severity, fingerprint, **overrides):
    """Create a FindingRecord for testing."""
    defaults = {
        "scan_id": uuid4(),
        "agent": agent,
        "title": "Unhandled exception",
        "description": "desc",
        "severity": severity,
        "confidence": 0.7,
        "file_path": "app/main.py",
        "symbol_name": "handler",
        "start_line": 10,
        "end_line": 20,
        "evidence": [],
        "recommendation": None,
        "fingerprint": fingerprint,
        "related_agents": [],
    }
    defaults.update(overrides)
    return FindingRecord(**defaults)


def test_deduplicate_merges_same_file_symbol_line_range_and_title():
    """Findings with same file/symbol/lines/title should merge."""
    findings = [
        _finding_record("security", "high", "fp1"),
        _finding_record("reliability", "medium", "fp2"),
    ]
    
    deduped = deduplicate_findings(findings)
    
    assert len(deduped) == 1
    assert deduped[0].agent == "security"  # higher severity wins
    assert deduped[0].related_agents == ["reliability"]


def test_deduplicate_keeps_distinct_findings_separate():
    """Findings with different location/title should remain separate."""
    findings = [
        _finding_record("security", "high", "fp1", title="Issue A"),
        _finding_record("performance", "high", "fp2", title="Issue B", start_line=100, end_line=110),
    ]
    
    deduped = deduplicate_findings(findings)
    
    assert len(deduped) == 2


def test_deduplicate_groups_by_fingerprint_first():
    """Findings with same fingerprint should group together first."""
    findings = [
        _finding_record("security", "high", "fp1"),
        _finding_record("security", "medium", "fp1"),  # same fingerprint
    ]
    
    deduped = deduplicate_findings(findings)
    
    assert len(deduped) == 1
    assert deduped[0].severity == "high"  # higher severity wins


def test_deduplicate_uses_severity_for_primary_selection():
    """Primary finding should be the one with highest severity."""
    findings = [
        _finding_record("reliability", "low", "fp1"),
        _finding_record("security", "extreme", "fp2"),
        _finding_record("performance", "medium", "fp3"),
    ]
    
    deduped = deduplicate_findings(findings)
    
    assert len(deduped) == 1
    assert deduped[0].agent == "security"
    assert deduped[0].severity == "extreme"
    assert set(deduped[0].related_agents) == {"performance", "reliability"}


def test_deduplicate_title_comparison_is_case_insensitive():
    """Title matching should be case-insensitive."""
    findings = [
        _finding_record("security", "high", "fp1", title="SQL Injection"),
        _finding_record("reliability", "medium", "fp2", title="sql injection"),
    ]
    
    deduped = deduplicate_findings(findings)
    
    assert len(deduped) == 1


def test_deduplicate_title_comparison_strips_whitespace():
    """Title matching should strip whitespace."""
    findings = [
        _finding_record("security", "high", "fp1", title=" Memory leak "),
        _finding_record("performance", "medium", "fp2", title="Memory leak"),
    ]
    
    deduped = deduplicate_findings(findings)
    
    assert len(deduped) == 1


def test_deduplicate_returns_empty_list_for_empty_input():
    """Empty input should return empty list."""
    assert deduplicate_findings([]) == []


def test_deduplicate_handles_single_finding():
    """Single finding should pass through unchanged."""
    findings = [_finding_record("security", "high", "fp1")]
    
    deduped = deduplicate_findings(findings)
    
    assert len(deduped) == 1
    assert deduped[0].agent == "security"
    assert deduped[0].related_agents == []
