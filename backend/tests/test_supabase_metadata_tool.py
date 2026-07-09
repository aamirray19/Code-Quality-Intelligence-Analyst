# backend/tests/test_supabase_metadata_tool.py
from unittest.mock import MagicMock, patch

from app.workflows.analysis.tools import supabase_metadata_tool as tool

MODULE = "app.workflows.analysis.tools.supabase_metadata_tool"


def _mock_client_returning(data):
    client = MagicMock()
    execute_result = MagicMock()
    execute_result.data = data
    chain = client.table.return_value
    for method in ("select", "eq", "neq", "in_", "limit"):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = execute_result
    return client


def test_get_scan_returns_first_row():
    client = _mock_client_returning([{"id": "s1", "status": "parsed"}])
    with patch(f"{MODULE}.get_supabase_client", return_value=client):
        result = tool.get_scan("s1")
    assert result == {"id": "s1", "status": "parsed"}


def test_get_scan_returns_none_when_missing():
    client = _mock_client_returning([])
    with patch(f"{MODULE}.get_supabase_client", return_value=client):
        assert tool.get_scan("missing") is None


def test_list_symbols_sorts_by_loc_descending_and_caps():
    rows = [
        {"id": "a", "file_id": "f1", "symbol_type": "function", "symbol_name": "small", "start_line": 1, "end_line": 3},
        {"id": "b", "file_id": "f1", "symbol_type": "function", "symbol_name": "big", "start_line": 1, "end_line": 100},
    ]
    client = _mock_client_returning(rows)
    with patch(f"{MODULE}.get_supabase_client", return_value=client):
        result = tool.list_symbols("s1", limit=1)
    assert len(result) == 1
    assert result[0]["symbol_name"] == "big"


def test_find_file_by_path_returns_none_when_missing():
    client = _mock_client_returning([])
    with patch(f"{MODULE}.get_supabase_client", return_value=client):
        assert tool.find_file_by_path("s1", "app/missing.py") is None
