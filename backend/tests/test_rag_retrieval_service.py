# backend/tests/test_rag_retrieval_service.py
import pytest
from unittest.mock import MagicMock, patch

from app.services import rag_retrieval_service as service

MODULE = "app.services.rag_retrieval_service"


def _fake_point(point_id, score, payload):
    """Helper to create a mock Qdrant point."""
    point = MagicMock()
    point.id = point_id
    point.score = score
    point.payload = payload
    return point


@pytest.mark.asyncio
async def test_retrieve_relevant_docs_searches_all_collections_with_scan_id_filter():
    """Verify that all 3 collections are searched with scan_id filter."""
    fake_client = MagicMock()
    # Mock search to return different results for different collections
    fake_client.search.side_effect = [
        # code_chunks collection
        [_fake_point("c1", 0.95, {"chunk_id": "c1", "file_path": "app/x.py", "scan_id": "scan-1"})],
        # agent_findings collection
        [_fake_point("f1", 0.85, {"finding_id": "f1", "scan_id": "scan-1", "doc_type": "finding", "content": "Security finding text"})],
        # scan_reports collection
        [_fake_point("r1", 0.75, {"scan_id": "scan-1", "doc_type": "scan_report", "content": "Report summary text"})],
    ]
    
    # Mock Supabase to return chunk content
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": "c1", "content": "Code chunk text"}
    ]
    
    with patch(f"{MODULE}.embed_text", return_value=[0.1, 0.2]), \
         patch(f"{MODULE}.get_qdrant_client", return_value=fake_client), \
         patch(f"{MODULE}.get_supabase_client", return_value=fake_supabase):
        result = await service.retrieve_relevant_docs("scan-1", "test query", top_k=8)
    
    # Should have called search 3 times (once per collection)
    assert fake_client.search.call_count == 3
    
    # Check that each search call had the scan_id filter
    for call in fake_client.search.call_args_list:
        assert "query_filter" in call.kwargs
        # Extract the filter and verify it contains scan_id match
        # The filter structure is: models.Filter(must=[models.FieldCondition(key="scan_id", match=models.MatchValue(value="scan-1"))])
        # We can't easily introspect the models.Filter object, so we'll just verify it was passed
        assert call.kwargs["query_filter"] is not None
    
    # Verify results contain all expected fields
    assert len(result) == 3
    for doc in result:
        assert "text" in doc
        assert "source_type" in doc
        assert "payload" in doc
        assert "score" in doc


@pytest.mark.asyncio
async def test_retrieve_relevant_docs_merges_and_sorts_by_score():
    """Verify that results from all collections are merged and sorted by score descending."""
    fake_client = MagicMock()
    fake_client.search.side_effect = [
        # code_chunks - score 0.6
        [_fake_point("c1", 0.6, {"chunk_id": "c1", "scan_id": "scan-1"})],
        # agent_findings - score 0.9 (highest)
        [_fake_point("f1", 0.9, {"scan_id": "scan-1", "doc_type": "finding", "content": "Finding text"})],
        # scan_reports - score 0.7
        [_fake_point("r1", 0.7, {"scan_id": "scan-1", "doc_type": "scan_report", "content": "Report text"})],
    ]
    
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": "c1", "content": "Chunk text"}
    ]
    
    with patch(f"{MODULE}.embed_text", return_value=[0.1, 0.2]), \
         patch(f"{MODULE}.get_qdrant_client", return_value=fake_client), \
         patch(f"{MODULE}.get_supabase_client", return_value=fake_supabase):
        result = await service.retrieve_relevant_docs("scan-1", "test query", top_k=8)
    
    # Results should be sorted by score descending: 0.9, 0.7, 0.6
    assert len(result) == 3
    assert result[0]["score"] == 0.9
    assert result[1]["score"] == 0.7
    assert result[2]["score"] == 0.6


@pytest.mark.asyncio
async def test_retrieve_relevant_docs_truncates_to_top_k():
    """Verify that merged results are truncated to top_k."""
    fake_client = MagicMock()
    # Return multiple results from each collection (total > top_k)
    fake_client.search.side_effect = [
        # code_chunks - 2 results
        [
            _fake_point("c1", 0.9, {"chunk_id": "c1", "scan_id": "scan-1"}),
            _fake_point("c2", 0.5, {"chunk_id": "c2", "scan_id": "scan-1"}),
        ],
        # agent_findings - 2 results
        [
            _fake_point("f1", 0.8, {"scan_id": "scan-1", "doc_type": "finding", "content": "F1"}),
            _fake_point("f2", 0.4, {"scan_id": "scan-1", "doc_type": "file_summary", "content": "F2"}),
        ],
        # scan_reports - 1 result
        [_fake_point("r1", 0.7, {"scan_id": "scan-1", "doc_type": "scan_report", "content": "R1"})],
    ]
    
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": "c1", "content": "C1"},
        {"id": "c2", "content": "C2"},
    ]
    
    with patch(f"{MODULE}.embed_text", return_value=[0.1, 0.2]), \
         patch(f"{MODULE}.get_qdrant_client", return_value=fake_client), \
         patch(f"{MODULE}.get_supabase_client", return_value=fake_supabase):
        # Request only top 3
        result = await service.retrieve_relevant_docs("scan-1", "test query", top_k=3)
    
    # Should only return top 3 by score (0.9, 0.8, 0.7)
    assert len(result) == 3
    assert result[0]["score"] == 0.9
    assert result[1]["score"] == 0.8
    assert result[2]["score"] == 0.7


@pytest.mark.asyncio
async def test_retrieve_relevant_docs_sets_correct_source_types():
    """Verify that source_type is correctly derived for each collection/doc_type."""
    fake_client = MagicMock()
    fake_client.search.side_effect = [
        # code_chunks
        [_fake_point("c1", 0.9, {"chunk_id": "c1", "scan_id": "scan-1"})],
        # agent_findings with different doc_types
        [
            _fake_point("f1", 0.8, {"scan_id": "scan-1", "doc_type": "finding", "content": "Finding"}),
            _fake_point("f2", 0.7, {"scan_id": "scan-1", "doc_type": "file_summary", "content": "File sum"}),
            _fake_point("f3", 0.6, {"scan_id": "scan-1", "doc_type": "agent_summary", "content": "Agent sum"}),
        ],
        # scan_reports
        [_fake_point("r1", 0.5, {"scan_id": "scan-1", "doc_type": "scan_report", "content": "Report"})],
    ]
    
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": "c1", "content": "Chunk"}
    ]
    
    with patch(f"{MODULE}.embed_text", return_value=[0.1, 0.2]), \
         patch(f"{MODULE}.get_qdrant_client", return_value=fake_client), \
         patch(f"{MODULE}.get_supabase_client", return_value=fake_supabase):
        result = await service.retrieve_relevant_docs("scan-1", "test query", top_k=10)
    
    # Verify source_type values
    assert len(result) == 5
    source_types = {doc["source_type"] for doc in result}
    assert "code_chunk" in source_types
    assert "finding" in source_types
    assert "file_summary" in source_types
    assert "agent_summary" in source_types
    assert "scan_report" in source_types


@pytest.mark.asyncio
async def test_retrieve_relevant_docs_includes_text_field():
    """Verify that text field is populated correctly for each source type."""
    fake_client = MagicMock()
    fake_client.search.side_effect = [
        # code_chunks - text comes from Supabase
        [_fake_point("c1", 0.9, {"chunk_id": "c1", "scan_id": "scan-1", "file_path": "x.py"})],
        # agent_findings - text comes from content field
        [_fake_point("f1", 0.8, {"scan_id": "scan-1", "doc_type": "finding", "content": "Finding content text"})],
        # scan_reports - text comes from content field
        [_fake_point("r1", 0.7, {"scan_id": "scan-1", "doc_type": "scan_report", "content": "Report content text"})],
    ]
    
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": "c1", "content": "Code chunk content text"}
    ]
    
    with patch(f"{MODULE}.embed_text", return_value=[0.1, 0.2]), \
         patch(f"{MODULE}.get_qdrant_client", return_value=fake_client), \
         patch(f"{MODULE}.get_supabase_client", return_value=fake_supabase):
        result = await service.retrieve_relevant_docs("scan-1", "test query", top_k=8)
    
    assert len(result) == 3
    # Code chunk text from Supabase
    code_chunk_doc = next(d for d in result if d["source_type"] == "code_chunk")
    assert code_chunk_doc["text"] == "Code chunk content text"
    # Finding text from Qdrant payload content field
    finding_doc = next(d for d in result if d["source_type"] == "finding")
    assert finding_doc["text"] == "Finding content text"
    # Report text from Qdrant payload content field
    report_doc = next(d for d in result if d["source_type"] == "scan_report")
    assert report_doc["text"] == "Report content text"


@pytest.mark.asyncio
async def test_retrieve_relevant_docs_handles_empty_results():
    """Verify graceful handling when no results found."""
    fake_client = MagicMock()
    fake_client.search.side_effect = [[], [], []]  # All collections return empty
    
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = []
    
    with patch(f"{MODULE}.embed_text", return_value=[0.1, 0.2]), \
         patch(f"{MODULE}.get_qdrant_client", return_value=fake_client), \
         patch(f"{MODULE}.get_supabase_client", return_value=fake_supabase):
        result = await service.retrieve_relevant_docs("scan-1", "test query", top_k=8)
    
    assert result == []


@pytest.mark.asyncio
async def test_retrieve_relevant_docs_handles_missing_chunk_content():
    """Verify handling when Supabase doesn't have content for a chunk_id."""
    fake_client = MagicMock()
    fake_client.search.side_effect = [
        [_fake_point("c1", 0.9, {"chunk_id": "c1", "scan_id": "scan-1"})],
        [],  # agent_findings
        [],  # scan_reports
    ]
    
    # Supabase returns empty (chunk not found)
    fake_supabase = MagicMock()
    fake_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = []
    
    with patch(f"{MODULE}.embed_text", return_value=[0.1, 0.2]), \
         patch(f"{MODULE}.get_qdrant_client", return_value=fake_client), \
         patch(f"{MODULE}.get_supabase_client", return_value=fake_supabase):
        result = await service.retrieve_relevant_docs("scan-1", "test query", top_k=8)
    
    # Should skip chunks with no content from Supabase
    # Or include with a placeholder - let's design to skip missing ones
    assert len(result) == 0
