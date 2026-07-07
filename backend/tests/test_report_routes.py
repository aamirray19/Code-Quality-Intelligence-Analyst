from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.report import ReportMetrics, ReportRecord
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


def _sample_report_record(scan_id):
    now = datetime.now(timezone.utc)
    return ReportRecord(
        id=uuid4(),
        scan_id=scan_id,
        summary_markdown="# Code Quality Report\n\nSample report.",
        metrics=ReportMetrics(
            total_findings=5,
            by_severity={"critical": 1, "high": 2, "medium": 2},
            by_agent={"security": 3, "performance": 2},
            files_affected=3,
        ),
        risk_score=0.65,
        created_at=now,
    )


def test_get_report_scan_not_found():
    scan_id = uuid4()
    with patch("app.api.routes.reports.scan_service.get_scan", return_value=None):
        response = client.get(f"/scans/{scan_id}/report")

    assert response.status_code == 404
    assert response.json()["error_code"] == "SCAN_NOT_FOUND"


def test_get_report_scan_not_analyzed():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="parsing")

    with patch("app.api.routes.reports.scan_service.get_scan", return_value=scan_record):
        response = client.get(f"/scans/{scan_id}/report")

    assert response.status_code == 409
    assert response.json()["error_code"] == "SCAN_NOT_ANALYZED"


def test_get_report_report_not_found():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="analyzed")

    with patch("app.api.routes.reports.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.reports.report_service.get_report_by_scan_id", return_value=None):
        response = client.get(f"/scans/{scan_id}/report")

    assert response.status_code == 404
    assert response.json()["error_code"] == "REPORT_NOT_FOUND"


def test_get_report_success():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id, status="reported")
    report_record = _sample_report_record(scan_id)

    with patch("app.api.routes.reports.scan_service.get_scan", return_value=scan_record), \
         patch("app.api.routes.reports.report_service.get_report_by_scan_id", return_value=report_record):
        response = client.get(f"/scans/{scan_id}/report")

    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == str(scan_id)
    assert body["summary_markdown"] == "# Code Quality Report\n\nSample report."
    assert body["metrics"]["total_findings"] == 5
    assert body["risk_score"] == 0.65
