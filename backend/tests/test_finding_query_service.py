from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.finding import FindingRecord
from app.services.finding_query_service import fetch_findings_for_scan


def _db_row(**overrides):
    """Create a mock DB row matching findings table schema."""
    base = {
        "id": str(uuid4()),
        "scan_id": str(uuid4()),
        "primary_agent": "security",
        "title": "SQL injection",
        "description": "Potential SQL injection vulnerability",
        "severity": "high",
        "confidence": 0.85,
        "file_id": str(uuid4()),
        "symbol_id": None,
        "file_path": "app/db.py",
        "symbol_name": "run_query",
        "start_line": 10,
        "end_line": 20,
        "evidence": ["unsanitized input"],
        "recommendation": "Use parameterized queries",
        "fingerprint": "abc123",
        "related_agents": ["reliability"],
        "created_at": "2024-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_fetch_findings_for_scan_returns_list_of_finding_records():
    """Fetches findings from Supabase and maps to FindingRecord objects."""
    scan_id = str(uuid4())
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.data = [_db_row(scan_id=scan_id), _db_row(scan_id=scan_id)]
    fake_client.table.return_value.select.return_value.eq.return_value.execute.return_value = fake_response

    with patch("app.services.finding_query_service.get_supabase_client", return_value=fake_client):
        findings = fetch_findings_for_scan(scan_id)

    assert len(findings) == 2
    assert all(isinstance(f, FindingRecord) for f in findings)
    assert findings[0].agent == "security"
    assert str(findings[0].scan_id) == scan_id  # FindingRecord converts to UUID
    fake_client.table.assert_called_with("findings")


def test_fetch_findings_for_scan_maps_primary_agent_to_agent_field():
    """DB column primary_agent must be renamed to agent for FindingRecord."""
    scan_id = str(uuid4())
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.data = [_db_row(scan_id=scan_id, primary_agent="complexity")]
    fake_client.table.return_value.select.return_value.eq.return_value.execute.return_value = fake_response

    with patch("app.services.finding_query_service.get_supabase_client", return_value=fake_client):
        findings = fetch_findings_for_scan(scan_id)

    assert findings[0].agent == "complexity"


def test_fetch_findings_for_scan_returns_empty_list_when_no_findings():
    """Returns empty list when no findings exist for scan."""
    scan_id = str(uuid4())
    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.data = []
    fake_client.table.return_value.select.return_value.eq.return_value.execute.return_value = fake_response

    with patch("app.services.finding_query_service.get_supabase_client", return_value=fake_client):
        findings = fetch_findings_for_scan(scan_id)

    assert findings == []
