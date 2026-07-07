from uuid import uuid4

import pytest

from app.schemas.finding import FindingRecord
from app.services.report_metrics_service import compute_report_metrics


def _finding_record(severity: str, agent: str = "security", file_path: str = "app/main.py", **overrides):
    """Create a FindingRecord for testing."""
    defaults = {
        "scan_id": uuid4(),
        "agent": agent,
        "title": "Issue",
        "description": "desc",
        "severity": severity,
        "confidence": 0.8,
        "file_path": file_path,
        "fingerprint": f"fp{uuid4()}",
    }
    defaults.update(overrides)
    return FindingRecord(**defaults)


def test_compute_report_metrics_empty_list():
    """Empty findings list should return zero metrics."""
    metrics = compute_report_metrics([])
    assert metrics.total_findings == 0
    assert metrics.by_severity == {}
    assert metrics.by_agent == {}
    assert metrics.files_affected == 0


def test_compute_report_metrics_total_findings():
    """Total findings should match input list length."""
    findings = [
        _finding_record("extreme"),
        _finding_record("high"),
        _finding_record("low"),
    ]
    metrics = compute_report_metrics(findings)
    assert metrics.total_findings == 3


def test_compute_report_metrics_by_severity():
    """by_severity should count findings per severity value."""
    findings = [
        _finding_record("extreme"),
        _finding_record("extreme"),
        _finding_record("high"),
        _finding_record("medium"),
        _finding_record("low"),
        _finding_record("low"),
    ]
    metrics = compute_report_metrics(findings)
    assert metrics.by_severity == {
        "extreme": 2,
        "high": 1,
        "medium": 1,
        "low": 2,
    }


def test_compute_report_metrics_by_agent():
    """by_agent should count findings per agent value."""
    findings = [
        _finding_record("extreme", agent="security"),
        _finding_record("high", agent="security"),
        _finding_record("medium", agent="performance"),
        _finding_record("low", agent="performance"),
        _finding_record("low", agent="complexity"),
    ]
    metrics = compute_report_metrics(findings)
    assert metrics.by_agent == {
        "security": 2,
        "performance": 2,
        "complexity": 1,
    }


def test_compute_report_metrics_files_affected_unique_paths():
    """files_affected should count unique non-null file_path values."""
    findings = [
        _finding_record("extreme", file_path="app/main.py"),
        _finding_record("high", file_path="app/main.py"),
        _finding_record("medium", file_path="app/utils.py"),
        _finding_record("low", file_path="app/utils.py"),
        _finding_record("low", file_path="app/helper.py"),
    ]
    metrics = compute_report_metrics(findings)
    # 3 unique paths: app/main.py, app/utils.py, app/helper.py
    assert metrics.files_affected == 3


def test_compute_report_metrics_files_affected_with_null_paths():
    """files_affected should count unique non-null paths, ignoring null values."""
    findings = [
        _finding_record("extreme", file_path="app/main.py"),
        _finding_record("high", file_path="app/main.py"),
        _finding_record("medium", file_path=None),
        _finding_record("low", file_path=None),
        _finding_record("low", file_path="app/utils.py"),
    ]
    metrics = compute_report_metrics(findings)
    # 2 unique non-null paths: app/main.py, app/utils.py
    assert metrics.files_affected == 2


def test_compute_report_metrics_all_null_file_paths():
    """If all file_paths are null, files_affected should be 0."""
    findings = [
        _finding_record("extreme", file_path=None),
        _finding_record("high", file_path=None),
    ]
    metrics = compute_report_metrics(findings)
    assert metrics.files_affected == 0


def test_compute_report_metrics_single_finding():
    """Single finding should be counted correctly."""
    findings = [_finding_record("high", agent="security", file_path="app/main.py")]
    metrics = compute_report_metrics(findings)
    assert metrics.total_findings == 1
    assert metrics.by_severity == {"high": 1}
    assert metrics.by_agent == {"security": 1}
    assert metrics.files_affected == 1


def test_compute_report_metrics_complex_scenario():
    """Complex real-world scenario."""
    findings = [
        _finding_record("extreme", agent="security", file_path="app/main.py"),
        _finding_record("extreme", agent="security", file_path="app/main.py"),
        _finding_record("high", agent="performance", file_path="app/utils.py"),
        _finding_record("high", agent="performance", file_path="app/helper.py"),
        _finding_record("medium", agent="complexity", file_path="app/main.py"),
        _finding_record("low", agent="complexity", file_path=None),
    ]
    metrics = compute_report_metrics(findings)
    assert metrics.total_findings == 6
    assert metrics.by_severity == {
        "extreme": 2,
        "high": 2,
        "medium": 1,
        "low": 1,
    }
    assert metrics.by_agent == {
        "security": 2,
        "performance": 2,
        "complexity": 2,
    }
    # 3 unique non-null paths: app/main.py, app/utils.py, app/helper.py
    assert metrics.files_affected == 3


def test_compute_report_metrics_many_findings_same_file():
    """Many findings in one file should count as one affected file."""
    findings = [_finding_record("low", file_path="app/main.py") for _ in range(10)]
    metrics = compute_report_metrics(findings)
    assert metrics.total_findings == 10
    assert metrics.by_severity == {"low": 10}
    assert metrics.files_affected == 1
