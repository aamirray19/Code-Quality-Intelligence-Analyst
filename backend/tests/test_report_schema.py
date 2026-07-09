import pytest
from datetime import datetime
from uuid import UUID
from pydantic import ValidationError

from app.schemas.report import ReportMetrics, ReportRecord


def test_report_metrics_valid():
    """Test creating a valid ReportMetrics instance."""
    metrics = ReportMetrics(
        total_findings=5,
        by_severity={"high": 2, "medium": 3},
        by_agent={"security": 3, "performance": 2},
        files_affected=10,
    )
    assert metrics.total_findings == 5
    assert metrics.by_severity == {"high": 2, "medium": 3}
    assert metrics.by_agent == {"security": 3, "performance": 2}
    assert metrics.files_affected == 10


def test_report_metrics_missing_required_field():
    """Test that missing a required field raises ValidationError."""
    with pytest.raises(ValidationError):
        ReportMetrics(
            total_findings=5,
            by_severity={"high": 2},
            # missing by_agent
            files_affected=10,
        )


def test_report_record_valid():
    """Test creating a valid ReportRecord instance."""
    scan_id = UUID("12345678-1234-5678-1234-567812345678")
    created_at = datetime.now()
    
    record = ReportRecord(
        id=UUID("87654321-4321-8765-4321-876543218765"),
        scan_id=scan_id,
        summary_markdown="# Report\n\nFindings summary.",
        metrics=ReportMetrics(
            total_findings=5,
            by_severity={"high": 2, "medium": 3},
            by_agent={"security": 3, "performance": 2},
            files_affected=10,
        ),
        risk_score=7.5,
        created_at=created_at,
    )
    
    assert record.id == UUID("87654321-4321-8765-4321-876543218765")
    assert record.scan_id == scan_id
    assert record.summary_markdown == "# Report\n\nFindings summary."
    assert record.risk_score == 7.5
    assert record.created_at == created_at


def test_report_record_missing_scan_id():
    """Test that missing scan_id raises ValidationError."""
    with pytest.raises(ValidationError):
        ReportRecord(
            id=UUID("87654321-4321-8765-4321-876543218765"),
            # missing scan_id
            summary_markdown="# Report\n\nFindings summary.",
            metrics=ReportMetrics(
                total_findings=5,
                by_severity={"high": 2, "medium": 3},
                by_agent={"security": 3, "performance": 2},
                files_affected=10,
            ),
            risk_score=7.5,
            created_at=datetime.now(),
        )


def test_report_record_missing_required_field():
    """Test that missing summary_markdown raises ValidationError."""
    with pytest.raises(ValidationError):
        ReportRecord(
            id=UUID("87654321-4321-8765-4321-876543218765"),
            scan_id=UUID("12345678-1234-5678-1234-567812345678"),
            # missing summary_markdown
            metrics=ReportMetrics(
                total_findings=5,
                by_severity={"high": 2, "medium": 3},
                by_agent={"security": 3, "performance": 2},
                files_affected=10,
            ),
            risk_score=7.5,
            created_at=datetime.now(),
        )
