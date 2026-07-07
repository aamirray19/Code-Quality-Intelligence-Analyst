"""Tests for the report generation pipeline orchestrator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.finding import FindingRecord
from app.schemas.report import ReportMetrics, ReportRecord
from app.schemas.scans import ScanRecord

MODULE = "app.workflows.report.pipeline"


def _sample_scan_record(scan_id, github_url="https://github.com/owner/repo"):
    now = datetime.now(timezone.utc)
    return ScanRecord(
        id=scan_id,
        github_url=github_url,
        repo_owner="owner",
        repo_name="repo",
        repo_full_name="owner/repo",
        branch="main",
        default_branch="main",
        clone_url="https://github.com/owner/repo.git",
        html_url=github_url,
        repo_size_kb=1277,
        status="analyzed",
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def _sample_finding(scan_id, title="Test Finding"):
    now = datetime.now(timezone.utc)
    return FindingRecord(
        id=uuid4(),
        scan_id=scan_id,
        agent="security",
        title=title,
        description="Test description",
        severity="high",
        confidence=0.85,
        file_id=uuid4(),
        symbol_id=None,
        file_path="src/main.py",
        symbol_name=None,
        start_line=10,
        end_line=20,
        evidence=["Evidence 1"],
        recommendation="Fix this issue",
        fingerprint=f"fingerprint-{title}",
        related_agents=[],
        created_at=now,
    )


def _sample_metrics():
    return ReportMetrics(
        total_findings=5,
        by_severity={"high": 3, "medium": 2},
        by_agent={"security": 3, "performance": 2},
        files_affected=3,
    )


def _sample_report_record(scan_id):
    now = datetime.now(timezone.utc)
    return ReportRecord(
        id=uuid4(),
        scan_id=scan_id,
        summary_markdown="# Report\n\nTest report",
        metrics=_sample_metrics(),
        risk_score=45.0,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_run_report_generation_success_path():
    """Test that run_report_generation calls all services in correct order."""
    from app.workflows.report.pipeline import run_report_generation

    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id)
    findings = [_sample_finding(scan_id, f"Finding {i}") for i in range(3)]
    metrics = _sample_metrics()
    report = _sample_report_record(scan_id)

    # Track call order
    call_order = []

    def make_mock(name, return_value=None):
        def side_effect(*args, **kwargs):
            call_order.append(name)
            return return_value
        mock = MagicMock(side_effect=side_effect)
        return mock

    def make_async_mock(name, return_value=None):
        async def side_effect(*args, **kwargs):
            call_order.append(name)
            return return_value
        mock = AsyncMock(side_effect=side_effect)
        return mock

    with patch(f"{MODULE}.fetch_findings_for_scan", make_mock("fetch", findings)), \
         patch(f"{MODULE}.normalize_findings", make_mock("normalize", findings)), \
         patch(f"{MODULE}.deduplicate_findings", make_mock("dedupe", findings)), \
         patch(f"{MODULE}.rank_findings", make_mock("rank", findings)), \
         patch(f"{MODULE}.compute_risk_score", make_mock("risk_score", 45.0)), \
         patch(f"{MODULE}.compute_report_metrics", make_mock("metrics", metrics)), \
         patch(f"{MODULE}.scan_service.get_scan", make_mock("get_scan", scan_record)), \
         patch(f"{MODULE}.build_report_markdown", make_async_mock("build_markdown", "# Report")), \
         patch(f"{MODULE}.save_report", make_mock("save_report", report)), \
         patch(f"{MODULE}.embed_and_index_report", make_async_mock("embed_index")), \
         patch(f"{MODULE}.scan_service.update_scan") as update_scan_mock, \
         patch(f"{MODULE}.scan_event_service.create_event") as create_event_mock:

        await run_report_generation(str(scan_id))

    # Verify call order
    expected_order = [
        "fetch",
        "normalize",
        "dedupe",
        "rank",
        "risk_score",
        "metrics",
        "get_scan",
        "build_markdown",
        "save_report",
        "embed_index",
    ]
    assert call_order == expected_order, f"Expected {expected_order}, got {call_order}"

    # Verify update_scan was called with status="reported"
    reported_calls = [
        c for c in update_scan_mock.call_args_list
        if c.kwargs.get("status") == "reported"
    ]
    assert len(reported_calls) == 1

    # Verify success event was logged
    success_events = [
        c for c in create_event_mock.call_args_list
        if c.args[1] == "report_generated"
    ]
    assert len(success_events) == 1


@pytest.mark.asyncio
async def test_run_report_generation_failure_path_swallows_exception():
    """Test that run_report_generation calls _mark_report_failed on error and swallows exception."""
    from app.workflows.report.pipeline import run_report_generation

    scan_id = uuid4()
    findings = [_sample_finding(scan_id)]

    with patch(f"{MODULE}.fetch_findings_for_scan", return_value=findings), \
         patch(f"{MODULE}.normalize_findings", return_value=findings), \
         patch(f"{MODULE}.deduplicate_findings", return_value=findings), \
         patch(f"{MODULE}.rank_findings", return_value=findings), \
         patch(f"{MODULE}.compute_risk_score", side_effect=ValueError("boom")), \
         patch(f"{MODULE}.scan_service.update_scan") as update_scan_mock, \
         patch(f"{MODULE}.scan_event_service.create_event") as create_event_mock:

        # Must NOT raise - exception should be swallowed
        await run_report_generation(str(scan_id))

    # Verify update_scan was called with status="report_failed"
    failed_calls = [
        c for c in update_scan_mock.call_args_list
        if c.kwargs.get("status") == "report_failed"
    ]
    assert len(failed_calls) == 1
    assert failed_calls[0].kwargs.get("error_code") is not None
    assert "boom" in failed_calls[0].kwargs.get("error_message", "")

    # Verify failure event was logged
    failure_events = [
        c for c in create_event_mock.call_args_list
        if c.args[1] == "report_generation_failed"
    ]
    assert len(failure_events) == 1


@pytest.mark.asyncio
async def test_run_report_generation_failure_in_async_step():
    """Test failure handling when an async service step raises."""
    from app.workflows.report.pipeline import run_report_generation

    scan_id = uuid4()
    scan_record = _sample_scan_record(scan_id)
    findings = [_sample_finding(scan_id)]
    metrics = _sample_metrics()

    with patch(f"{MODULE}.fetch_findings_for_scan", return_value=findings), \
         patch(f"{MODULE}.normalize_findings", return_value=findings), \
         patch(f"{MODULE}.deduplicate_findings", return_value=findings), \
         patch(f"{MODULE}.rank_findings", return_value=findings), \
         patch(f"{MODULE}.compute_risk_score", return_value=45.0), \
         patch(f"{MODULE}.compute_report_metrics", return_value=metrics), \
         patch(f"{MODULE}.scan_service.get_scan", return_value=scan_record), \
         patch(f"{MODULE}.build_report_markdown", side_effect=RuntimeError("LLM failed")), \
         patch(f"{MODULE}.scan_service.update_scan") as update_scan_mock, \
         patch(f"{MODULE}.scan_event_service.create_event") as create_event_mock:

        # Must NOT raise
        await run_report_generation(str(scan_id))

    # Verify failure was recorded
    failed_calls = [
        c for c in update_scan_mock.call_args_list
        if c.kwargs.get("status") == "report_failed"
    ]
    assert len(failed_calls) == 1
    assert "LLM failed" in failed_calls[0].kwargs.get("error_message", "")


@pytest.mark.asyncio
async def test_run_report_generation_mark_failed_itself_fails_gracefully():
    """Test that if _mark_report_failed itself raises, we still don't propagate the exception."""
    from app.workflows.report.pipeline import run_report_generation

    scan_id = uuid4()
    findings = [_sample_finding(scan_id)]

    with patch(f"{MODULE}.fetch_findings_for_scan", return_value=findings), \
         patch(f"{MODULE}.normalize_findings", side_effect=ValueError("original error")), \
         patch(f"{MODULE}.scan_service.update_scan", side_effect=RuntimeError("db down")), \
         patch(f"{MODULE}.scan_event_service.create_event"):

        # Must NOT raise even if _mark_report_failed fails
        await run_report_generation(str(scan_id))
