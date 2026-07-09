from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.schemas.report import ReportMetrics, ReportRecord
from app.services.report_service import get_report_by_scan_id, save_report


@pytest.fixture
def sample_metrics():
    return ReportMetrics(
        total_findings=10,
        by_severity={"critical": 2, "high": 3, "medium": 5},
        by_agent={"security": 4, "performance": 3, "reliability": 3},
        files_affected=7,
    )


@pytest.fixture
def sample_scan_id():
    return uuid4()


def test_save_report_inserts_into_table(sample_scan_id, sample_metrics):
    """Test that save_report inserts a row into the reports table with correct payload."""
    fake_client = MagicMock()
    created_at = datetime.now(timezone.utc)
    report_id = uuid4()

    fake_client.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": str(report_id),
            "scan_id": str(sample_scan_id),
            "summary_markdown": "# Report",
            "metrics": {
                "total_findings": 10,
                "by_severity": {"critical": 2, "high": 3, "medium": 5},
                "by_agent": {"security": 4, "performance": 3, "reliability": 3},
                "files_affected": 7,
            },
            "risk_score": 0.75,
            "created_at": created_at.isoformat(),
        }
    ]

    with patch("app.services.report_service.get_supabase_client", return_value=fake_client):
        result = save_report(
            scan_id=sample_scan_id,
            summary_markdown="# Report",
            metrics=sample_metrics,
            risk_score=0.75,
        )

    # Verify the insert call
    fake_client.table.assert_called_with("reports")
    insert_mock = fake_client.table.return_value.insert
    insert_mock.assert_called_once()

    # Check payload
    payload = insert_mock.call_args[0][0]
    assert payload["scan_id"] == str(sample_scan_id)
    assert payload["summary_markdown"] == "# Report"
    assert payload["risk_score"] == 0.75
    assert payload["metrics"] == {
        "total_findings": 10,
        "by_severity": {"critical": 2, "high": 3, "medium": 5},
        "by_agent": {"security": 4, "performance": 3, "reliability": 3},
        "files_affected": 7,
    }

    # Check result
    assert isinstance(result, ReportRecord)
    assert result.id == report_id
    assert result.scan_id == sample_scan_id
    assert result.summary_markdown == "# Report"
    assert result.risk_score == 0.75
    assert isinstance(result.metrics, ReportMetrics)
    assert result.metrics.total_findings == 10


def test_get_report_by_scan_id_returns_record(sample_scan_id, sample_metrics):
    """Test that get_report_by_scan_id queries correctly and returns a ReportRecord."""
    fake_client = MagicMock()
    report_id = uuid4()
    created_at = datetime.now(timezone.utc)

    fake_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": str(report_id),
            "scan_id": str(sample_scan_id),
            "summary_markdown": "# Report",
            "metrics": {
                "total_findings": 10,
                "by_severity": {"critical": 2, "high": 3, "medium": 5},
                "by_agent": {"security": 4, "performance": 3, "reliability": 3},
                "files_affected": 7,
            },
            "risk_score": 0.75,
            "created_at": created_at.isoformat(),
        }
    ]

    with patch("app.services.report_service.get_supabase_client", return_value=fake_client):
        result = get_report_by_scan_id(sample_scan_id)

    # Verify the query chain
    fake_client.table.assert_called_with("reports")
    fake_client.table.return_value.select.assert_called_with("*")
    fake_client.table.return_value.select.return_value.eq.assert_called_with("scan_id", str(sample_scan_id))

    # Check result
    assert isinstance(result, ReportRecord)
    assert result.id == report_id
    assert result.scan_id == sample_scan_id
    assert result.summary_markdown == "# Report"
    assert isinstance(result.metrics, ReportMetrics)


def test_get_report_by_scan_id_returns_none_when_not_found(sample_scan_id):
    """Test that get_report_by_scan_id returns None when no row is found."""
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("app.services.report_service.get_supabase_client", return_value=fake_client):
        result = get_report_by_scan_id(sample_scan_id)

    assert result is None
