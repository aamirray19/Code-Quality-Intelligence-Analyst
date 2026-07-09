# backend/tests/test_qdrant_retrieval_tool.py
from unittest.mock import MagicMock, patch

from app.workflows.analysis.tools import qdrant_retrieval_tool as tool

MODULE = "app.workflows.analysis.tools.qdrant_retrieval_tool"


def _fake_point(point_id, score, payload):
    point = MagicMock()
    point.id = point_id
    point.score = score
    point.payload = payload
    return point


def test_search_code_chunks_returns_empty_when_no_vector():
    with patch(f"{MODULE}.embed_text", return_value=[]):
        result = tool.search_code_chunks("scan-1", "some query")
    assert result == []


def test_search_code_chunks_filters_by_scan_id_and_maps_results():
    fake_client = MagicMock()
    fake_client.search.return_value = [
        _fake_point("c1", 0.9, {"file_path": "app/x.py", "scan_id": "scan-1"})
    ]
    with patch(f"{MODULE}.embed_text", return_value=[0.1, 0.2]), patch(
        f"{MODULE}.get_qdrant_client", return_value=fake_client
    ):
        result = tool.search_code_chunks("scan-1", "some query", limit=5)

    assert result == [{"chunk_id": "c1", "score": 0.9, "file_path": "app/x.py", "scan_id": "scan-1"}]
    call_kwargs = fake_client.search.call_args.kwargs
    assert call_kwargs["query_vector"] == [0.1, 0.2]
    assert call_kwargs["limit"] == 5


def test_find_similar_chunks_maps_results():
    fake_client = MagicMock()
    fake_client.recommend.return_value = [
        _fake_point("c2", 0.8, {"file_path": "app/y.py"})
    ]
    with patch(f"{MODULE}.get_qdrant_client", return_value=fake_client):
        result = tool.find_similar_chunks("scan-1", "c1", limit=3)

    assert result == [{"chunk_id": "c2", "score": 0.8, "file_path": "app/y.py"}]
    assert fake_client.recommend.call_args.kwargs["positive"] == ["c1"]
