# backend/tests/test_neo4j_graph_tool.py
from unittest.mock import MagicMock, patch

from app.workflows.analysis.tools import neo4j_graph_tool as tool

MODULE = "app.workflows.analysis.tools.neo4j_graph_tool"


def _mock_driver_returning(records):
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.run.return_value = [dict(r) for r in records]
    return driver


def test_get_file_imports_returns_import_names():
    driver = _mock_driver_returning([{"name": "requests"}, {"name": "os"}])
    with patch(f"{MODULE}.get_neo4j_driver", return_value=driver):
        result = tool.get_file_imports("scan-1", "file-1")
    assert result == [{"name": "requests"}, {"name": "os"}]


def test_get_call_chain_delegates_to_symbol_neighbors():
    with patch(f"{MODULE}.get_symbol_neighbors", return_value=[{"symbol_id": "s2"}]) as neighbors_mock:
        result = tool.get_call_chain("scan-1", "s1", depth=2)
    neighbors_mock.assert_called_once_with("scan-1", "s1", depth=2)
    assert result == [{"symbol_id": "s2"}]


def test_find_database_call_sites_queries_known_patterns():
    driver = _mock_driver_returning([{"file_path": "app/db.py", "import_name": "supabase"}])
    with patch(f"{MODULE}.get_neo4j_driver", return_value=driver):
        result = tool.find_database_call_sites("scan-1")
    assert {"file_path": "app/db.py", "import_name": "supabase"} in result
