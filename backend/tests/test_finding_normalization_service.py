from uuid import uuid4

import pytest

from app.schemas.finding import FindingRecord
from app.services.finding_normalization_service import normalize_findings


def _finding_record(**overrides):
    """Create a FindingRecord for testing."""
    defaults = {
        "scan_id": uuid4(),
        "agent": "security",
        "title": "SQL injection",
        "description": "Potential vulnerability",
        "severity": "high",
        "confidence": 0.85,
        "file_path": "app/db.py",
        "symbol_name": "run_query",
        "start_line": 10,
        "end_line": 20,
        "evidence": ["evidence"],
        "recommendation": "Fix it",
        "fingerprint": "abc123",
    }
    defaults.update(overrides)
    return FindingRecord(**defaults)


def test_normalize_findings_clamps_confidence_to_valid_range():
    """Confidence values should be clamped to [0, 1]."""
    findings = [
        _finding_record(confidence=1.5),
        _finding_record(confidence=-0.2),
        _finding_record(confidence=0.5),
    ]
    
    normalized = normalize_findings(findings)
    
    assert normalized[0].confidence == 1.0
    assert normalized[1].confidence == 0.0
    assert normalized[2].confidence == 0.5


def test_normalize_findings_ensures_forward_slashes_in_file_paths():
    """File paths should use forward slashes."""
    findings = [
        _finding_record(file_path="app\\db.py"),
        _finding_record(file_path="src\\utils\\helper.ts"),
    ]
    
    normalized = normalize_findings(findings)
    
    assert normalized[0].file_path == "app/db.py"
    assert normalized[1].file_path == "src/utils/helper.ts"


def test_normalize_findings_strips_leading_dot_slash():
    """Leading ./ should be stripped from file paths."""
    findings = [_finding_record(file_path="./app/main.py")]
    
    normalized = normalize_findings(findings)
    
    assert normalized[0].file_path == "app/main.py"


def test_normalize_findings_is_idempotent():
    """Calling normalize_findings twice should produce same result."""
    findings = [_finding_record(confidence=0.75, file_path="app/db.py")]
    
    normalized_once = normalize_findings(findings)
    normalized_twice = normalize_findings(normalized_once)
    
    assert normalized_once[0].confidence == normalized_twice[0].confidence
    assert normalized_once[0].file_path == normalized_twice[0].file_path


def test_normalize_findings_returns_empty_list_for_empty_input():
    """Empty input should return empty list."""
    assert normalize_findings([]) == []


def test_normalize_findings_preserves_all_other_fields():
    """Non-normalized fields should remain unchanged."""
    scan_id = uuid4()
    findings = [
        _finding_record(
            scan_id=scan_id,
            agent="performance",
            title="Slow query",
            severity="medium",
            evidence=["evidence1", "evidence2"],
            related_agents=["reliability"],
        )
    ]
    
    normalized = normalize_findings(findings)
    
    assert normalized[0].scan_id == scan_id
    assert normalized[0].agent == "performance"
    assert normalized[0].title == "Slow query"
    assert normalized[0].severity == "medium"
    assert normalized[0].evidence == ["evidence1", "evidence2"]
    assert normalized[0].related_agents == ["reliability"]
