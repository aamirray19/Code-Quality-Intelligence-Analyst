# backend/tests/test_report_embedding_service.py
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.schemas.finding import FindingRecord
from app.schemas.report import ReportMetrics, ReportRecord
from app.services import report_embedding_service as service

MODULE = "app.services.report_embedding_service"


@pytest.fixture
def sample_report():
    return ReportRecord(
        id=uuid4(),
        scan_id=UUID("12345678-1234-5678-1234-567812345678"),
        summary_markdown="# Code Quality Report\n\nThis repo has 3 findings across 2 files.",
        metrics=ReportMetrics(
            total_findings=3,
            by_severity={"HIGH": 2, "MEDIUM": 1},
            by_agent={"security": 2, "performance": 1},
            files_affected=2,
        ),
        risk_score=7.5,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_findings():
    scan_id = UUID("12345678-1234-5678-1234-567812345678")
    return [
        FindingRecord(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            scan_id=scan_id,
            agent="security",
            title="SQL Injection Risk",
            description="User input not sanitized before query",
            severity="HIGH",
            confidence=0.9,
            file_path="app/db.py",
            symbol_name="query_users",
            start_line=10,
            end_line=15,
            fingerprint="hash1",
        ),
        FindingRecord(
            id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            scan_id=scan_id,
            agent="security",
            title="Hardcoded Secret",
            description="API key found in code",
            severity="HIGH",
            confidence=0.95,
            file_path="app/config.py",
            symbol_name="Settings",
            start_line=5,
            end_line=5,
            fingerprint="hash2",
        ),
        FindingRecord(
            id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            scan_id=scan_id,
            agent="performance",
            title="N+1 Query Pattern",
            description="Loop fetching data individually",
            severity="MEDIUM",
            confidence=0.8,
            file_path="app/db.py",
            symbol_name="get_all_users",
            start_line=20,
            end_line=25,
            fingerprint="hash3",
        ),
    ]


@pytest.mark.asyncio
async def test_embed_and_index_report_calls_upsert_on_both_collections(
    sample_report, sample_findings
):
    """Test that embed_and_index_report upserts points to both agent_findings and scan_reports."""
    fake_client = MagicMock()
    fake_client.collection_exists.return_value = True  # Pretend collections already exist
    fake_vectors = [[0.1] * 768] * 8  # Mock 8 embeddings (1 report + 3 findings + 2 files + 2 agents)

    with patch(f"{MODULE}.embed_texts", return_value=fake_vectors), patch(
        f"{MODULE}.get_qdrant_client", return_value=fake_client
    ), patch(
        "app.services.qdrant_index_service.get_qdrant_client", return_value=fake_client
    ):
        await service.embed_and_index_report(
            scan_id=str(sample_report.scan_id),
            report=sample_report,
            findings=sample_findings,
        )

    # Should call upsert twice: once for agent_findings, once for scan_reports
    assert fake_client.upsert.call_count == 2

    # Check that both collections were called
    collections_called = {call.kwargs["collection_name"] for call in fake_client.upsert.call_args_list}
    assert "agent_findings" in collections_called
    assert "scan_reports" in collections_called


@pytest.mark.asyncio
async def test_embed_and_index_report_creates_correct_point_counts(sample_report, sample_findings):
    """Test that the correct number of points are created for each collection."""
    fake_client = MagicMock()
    fake_client.collection_exists.return_value = True
    # Need vectors for:
    # - 1 report summary
    # - 3 individual findings
    # - 2 file summaries (app/db.py, app/config.py)
    # - 2 agent summaries (security, performance)
    # Total: 8 vectors
    fake_vectors = [[0.1] * 768] * 8

    with patch(f"{MODULE}.embed_texts", return_value=fake_vectors), patch(
        f"{MODULE}.get_qdrant_client", return_value=fake_client
    ), patch(
        "app.services.qdrant_index_service.get_qdrant_client", return_value=fake_client
    ):
        await service.embed_and_index_report(
            scan_id=str(sample_report.scan_id),
            report=sample_report,
            findings=sample_findings,
        )

    # Get the upsert calls
    upsert_calls = fake_client.upsert.call_args_list

    # Find the call for agent_findings
    agent_findings_call = next(
        call for call in upsert_calls if call.kwargs["collection_name"] == "agent_findings"
    )
    agent_findings_points = agent_findings_call.kwargs["points"]

    # Should have: 3 findings + 2 file summaries + 2 agent summaries = 7 points
    assert len(agent_findings_points) == 7

    # Find the call for scan_reports
    scan_reports_call = next(
        call for call in upsert_calls if call.kwargs["collection_name"] == "scan_reports"
    )
    scan_reports_points = scan_reports_call.kwargs["points"]

    # Should have: 1 report summary
    assert len(scan_reports_points) == 1


@pytest.mark.asyncio
async def test_embed_and_index_report_finding_payloads_have_required_fields(
    sample_report, sample_findings
):
    """Test that finding points have the required payload fields."""
    fake_client = MagicMock()
    fake_client.collection_exists.return_value = True
    fake_vectors = [[0.1] * 768] * 8

    with patch(f"{MODULE}.embed_texts", return_value=fake_vectors), patch(
        f"{MODULE}.get_qdrant_client", return_value=fake_client
    ), patch(
        "app.services.qdrant_index_service.get_qdrant_client", return_value=fake_client
    ):
        await service.embed_and_index_report(
            scan_id=str(sample_report.scan_id),
            report=sample_report,
            findings=sample_findings,
        )

    # Get agent_findings points
    agent_findings_call = next(
        call
        for call in fake_client.upsert.call_args_list
        if call.kwargs["collection_name"] == "agent_findings"
    )
    points = agent_findings_call.kwargs["points"]

    # Find the finding points (those with doc_type = "finding")
    finding_points = [p for p in points if p.payload.get("doc_type") == "finding"]
    assert len(finding_points) == 3

    # Check required fields in finding payloads
    required_fields = {"finding_id", "scan_id", "severity", "agent", "file_path", "title"}
    for point in finding_points:
        assert required_fields.issubset(point.payload.keys())
        assert point.payload["scan_id"] == str(sample_report.scan_id)


@pytest.mark.asyncio
async def test_embed_and_index_report_uses_finding_id_for_point_id(sample_report, sample_findings):
    """Test that finding points use the finding's UUID as the point ID."""
    fake_client = MagicMock()
    fake_client.collection_exists.return_value = True
    fake_vectors = [[0.1] * 768] * 8

    with patch(f"{MODULE}.embed_texts", return_value=fake_vectors), patch(
        f"{MODULE}.get_qdrant_client", return_value=fake_client
    ), patch(
        "app.services.qdrant_index_service.get_qdrant_client", return_value=fake_client
    ):
        await service.embed_and_index_report(
            scan_id=str(sample_report.scan_id),
            report=sample_report,
            findings=sample_findings,
        )

    # Get agent_findings points
    agent_findings_call = next(
        call
        for call in fake_client.upsert.call_args_list
        if call.kwargs["collection_name"] == "agent_findings"
    )
    points = agent_findings_call.kwargs["points"]

    # Find the finding points
    finding_points = [p for p in points if p.payload.get("doc_type") == "finding"]

    # Check that point IDs match finding IDs
    finding_ids = {str(f.id) for f in sample_findings}
    point_ids = {p.id for p in finding_points}
    assert finding_ids == point_ids


@pytest.mark.asyncio
async def test_embed_and_index_report_batches_all_embeddings_in_one_call(
    sample_report, sample_findings
):
    """Test that all documents are embedded in a single batch call."""
    fake_client = MagicMock()
    fake_client.collection_exists.return_value = True
    fake_vectors = [[0.1] * 768] * 8

    with patch(f"{MODULE}.embed_texts", return_value=fake_vectors) as mock_embed, patch(
        f"{MODULE}.get_qdrant_client", return_value=fake_client
    ), patch(
        "app.services.qdrant_index_service.get_qdrant_client", return_value=fake_client
    ):
        await service.embed_and_index_report(
            scan_id=str(sample_report.scan_id),
            report=sample_report,
            findings=sample_findings,
        )

    # Should call embed_texts exactly once with 8 texts
    assert mock_embed.call_count == 1
    texts = mock_embed.call_args[0][0]
    assert len(texts) == 8


@pytest.mark.asyncio
async def test_embed_and_index_report_handles_empty_findings(sample_report):
    """Test that the function handles a report with no findings."""
    fake_client = MagicMock()
    fake_client.collection_exists.return_value = True
    # Only need vectors for: 1 report summary
    fake_vectors = [[0.1] * 768] * 1

    with patch(f"{MODULE}.embed_texts", return_value=fake_vectors), patch(
        f"{MODULE}.get_qdrant_client", return_value=fake_client
    ), patch(
        "app.services.qdrant_index_service.get_qdrant_client", return_value=fake_client
    ):
        await service.embed_and_index_report(
            scan_id=str(sample_report.scan_id), report=sample_report, findings=[]
        )

    # Should still create the report summary point
    scan_reports_call = next(
        call
        for call in fake_client.upsert.call_args_list
        if call.kwargs["collection_name"] == "scan_reports"
    )
    assert len(scan_reports_call.kwargs["points"]) == 1
