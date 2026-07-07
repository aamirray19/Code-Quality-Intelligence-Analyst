from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.repos import ValidatedRepository
from app.schemas.scans import ScanRecord

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "code-quality-intelligence-backend"}


def _sample_scan_record(scan_id):
    from datetime import datetime, timezone

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
        status="queued",
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def test_create_scan_success():
    scan_id = uuid4()
    validated_repo = ValidatedRepository(
        owner="owner",
        name="repo",
        full_name="owner/repo",
        branch="main",
        default_branch="main",
        clone_url="https://github.com/owner/repo.git",
        html_url="https://github.com/owner/repo",
        size_kb=1277,
        visibility="public",
    )
    scan_record = _sample_scan_record(scan_id)

    with patch("app.api.routes.scans.validate_repository", return_value=validated_repo), \
         patch("app.api.routes.scans.scan_service.create_scan", return_value=scan_record), \
         patch("app.api.routes.scans.queue_service.enqueue_scan", return_value="job-1"):
        response = client.post("/scans", json={"github_url": "https://github.com/owner/repo"})

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["scan_id"] == str(scan_id)
    assert body["status"] == "queued"
    assert body["repo"]["full_name"] == "owner/repo"


def test_get_scan_status_not_found():
    with patch("app.api.routes.scans.scan_service.get_scan", return_value=None):
        response = client.get(f"/scans/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "SCAN_NOT_FOUND"


def test_get_scan_status_success():
    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id)

    with patch("app.api.routes.scans.scan_service.get_scan", return_value=scan_record):
        response = client.get(f"/scans/{scan_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["scan_id"] == str(scan_id)
    assert body["status"] == "queued"
    assert body["repo"]["full_name"] == "owner/repo"
