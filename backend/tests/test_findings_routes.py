from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.finding import FindingRecord
from app.schemas.scans import ScanRecord

client = TestClient(app)


def _sample_scan_record(scan_id, status="analyzed"):
    now = datetime.now(timezone.utc)
    return ScanRecord(
        id=scan_id,
        github_url="https://github.com/owner/repo",
        repo_owner="owner",
        repo_name="repo",
        repo_full_name="owner/repo",
        branch="main",
        default_branch="main",
        clone_url="https://github.com/owner/repo.git",
        html_url="https://github.com/owner/repo",
        repo_size_kb=1277,
        status=status,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def _sample_finding_record(scan_id, agent="security", severity="high", file_path="auth.py"):
    now = datetime.now(timezone.utc)
    return FindingRecord(
        id=uuid4(),
        scan_id=scan_id,
        agent=agent,
        title="Sample finding",
        description="Sample description",
        severity=severity,
        confidence=0.9,
        file_path=file_path,
        fingerprint="abc123",
        created_at=now,
    )


def test_get_findings_scan_not_found():
    scan_id = uuid4()
    with patch("app.api.routes.findings.scan_service.get_scan", return_value=None):
        response = client.get(f"/scans/{scan_id}/findings")

    assert response.status_code == 404
    assert response.json()["error_code"] == "SCAN_NOT_FOUND"


def test_get_findings_scan_not_analyzed():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="parsing")

    with patch("app.api.routes.findings.scan_service.get_scan", return_value=scan_record):
        response = client.get(f"/scans/{scan_id}/findings")

    assert response.status_code == 409
    assert response.json()["error_code"] == "SCAN_NOT_ANALYZED"


def test_get_findings_success_no_filters():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    findings = [
        _sample_finding_record(scan_id, agent="security", severity="high", file_path="auth.py"),
        _sample_finding_record(scan_id, agent="performance", severity="medium", file_path="utils.py"),
    ]

    with patch("app.api.routes.findings.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.findings.finding_query_service.fetch_findings_for_scan", return_value=findings):
        response = client.get(f"/scans/{scan_id}/findings")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["agent"] == "security"
    assert body[1]["agent"] == "performance"


def test_get_findings_filter_by_severity():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    findings = [
        _sample_finding_record(scan_id, agent="security", severity="high", file_path="auth.py"),
        _sample_finding_record(scan_id, agent="performance", severity="medium", file_path="utils.py"),
    ]

    with patch("app.api.routes.findings.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.findings.finding_query_service.fetch_findings_for_scan", return_value=findings):
        response = client.get(f"/scans/{scan_id}/findings?severity=high")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["severity"] == "high"


def test_get_findings_filter_by_agent():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    findings = [
        _sample_finding_record(scan_id, agent="security", severity="high", file_path="auth.py"),
        _sample_finding_record(scan_id, agent="performance", severity="medium", file_path="utils.py"),
    ]

    with patch("app.api.routes.findings.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.findings.finding_query_service.fetch_findings_for_scan", return_value=findings):
        response = client.get(f"/scans/{scan_id}/findings?agent=security")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["agent"] == "security"


def test_get_findings_filter_by_file_path():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    findings = [
        _sample_finding_record(scan_id, agent="security", severity="high", file_path="auth.py"),
        _sample_finding_record(scan_id, agent="performance", severity="medium", file_path="utils.py"),
    ]

    with patch("app.api.routes.findings.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.findings.finding_query_service.fetch_findings_for_scan", return_value=findings):
        response = client.get(f"/scans/{scan_id}/findings?file_path=auth.py")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["file_path"] == "auth.py"


def test_get_findings_filter_multiple():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")
    findings = [
        _sample_finding_record(scan_id, agent="security", severity="high", file_path="auth.py"),
        _sample_finding_record(scan_id, agent="security", severity="medium", file_path="auth.py"),
        _sample_finding_record(scan_id, agent="performance", severity="medium", file_path="utils.py"),
    ]

    with patch("app.api.routes.findings.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.findings.finding_query_service.fetch_findings_for_scan", return_value=findings):
        response = client.get(f"/scans/{scan_id}/findings?agent=security&severity=high")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["agent"] == "security"
    assert body[0]["severity"] == "high"
