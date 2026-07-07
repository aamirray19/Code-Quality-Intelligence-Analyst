from uuid import uuid4

import pytest

from app.schemas.finding import FindingRecord
from app.services.risk_scoring_service import compute_risk_score


def _finding_record(severity: str, **overrides):
    """Create a FindingRecord for testing."""
    defaults = {
        "scan_id": uuid4(),
        "agent": "security",
        "title": "Issue",
        "description": "desc",
        "severity": severity,
        "confidence": 0.8,
        "file_path": "app/main.py",
        "fingerprint": f"fp{uuid4()}",
    }
    defaults.update(overrides)
    return FindingRecord(**defaults)


def test_compute_risk_score_empty_list():
    """Empty findings list should return 0."""
    risk_score = compute_risk_score([])
    assert risk_score == 0.0


def test_compute_risk_score_with_low_severity_only():
    """Only low severity findings."""
    findings = [_finding_record("low"), _finding_record("low")]
    risk_score = compute_risk_score(findings)
    assert risk_score == 2.0  # 2 * 1


def test_compute_risk_score_with_mixed_severities():
    """Test example from brief: 2 extreme + 1 high = 2*10 + 1*5 = 25."""
    findings = [
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("high"),
    ]
    risk_score = compute_risk_score(findings)
    assert risk_score == 25.0


def test_compute_risk_score_with_all_severity_levels():
    """Test all severity levels: extreme=10, high=5, medium=2, low=1."""
    findings = [
        _finding_record("extreme"),
        _finding_record("high"),
        _finding_record("medium"),
        _finding_record("low"),
    ]
    risk_score = compute_risk_score(findings)
    # 1*10 + 1*5 + 1*2 + 1*1 = 18
    assert risk_score == 18.0


def test_compute_risk_score_caps_at_100():
    """Risk score should never exceed 100."""
    findings = [_finding_record("extreme") for _ in range(20)]
    risk_score = compute_risk_score(findings)
    # 20 * 10 = 200, but capped at 100
    assert risk_score == 100.0


def test_compute_risk_score_cap_triggering_list():
    """Test that cap is applied when sum would exceed 100."""
    findings = [
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("extreme"),  # 11 * 10 = 110 -> capped at 100
    ]
    risk_score = compute_risk_score(findings)
    assert risk_score == 100.0


def test_compute_risk_score_single_finding():
    """Single finding should work correctly."""
    findings = [_finding_record("high")]
    risk_score = compute_risk_score(findings)
    assert risk_score == 5.0


def test_compute_risk_score_complex_scenario():
    """Complex real-world scenario."""
    findings = [
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("high"),
        _finding_record("high"),
        _finding_record("high"),
        _finding_record("medium"),
        _finding_record("medium"),
        _finding_record("low"),
    ]
    risk_score = compute_risk_score(findings)
    # 2*10 + 3*5 + 2*2 + 1*1 = 20 + 15 + 4 + 1 = 40
    assert risk_score == 40.0
