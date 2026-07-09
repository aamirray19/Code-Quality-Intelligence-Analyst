from unittest.mock import patch

import pytest

from app.services.graph_context_service import get_context_for_file

MODULE = "app.services.graph_context_service"


@pytest.mark.asyncio
async def test_get_context_for_file_composes_imports_and_symbols_when_file_found():
    """Happy path: file found, should compose imports and symbols into result dict."""
    with patch(
        f"{MODULE}.find_file_by_path", return_value={"id": "file-1", "relative_path": "app/main.py"}
    ), patch(
        f"{MODULE}.get_file_imports",
        return_value=[{"name": "os"}, {"name": "sys"}],
    ), patch(
        f"{MODULE}.list_symbols_for_file",
        return_value=[
            {"id": "sym-1", "symbol_name": "func_a", "symbol_type": "function"},
            {"id": "sym-2", "symbol_name": "Class_B", "symbol_type": "class"},
        ],
    ):
        result = await get_context_for_file("scan-1", "app/main.py")

    assert result["imports"] == [{"name": "os"}, {"name": "sys"}]
    assert len(result["symbols"]) == 2
    assert result["symbols"][0]["symbol_name"] == "func_a"
    assert result["symbols"][1]["symbol_name"] == "Class_B"


@pytest.mark.asyncio
async def test_get_context_for_file_returns_empty_dicts_when_file_not_found():
    """Not-found path: file not found, should return empty imports/symbols and NOT call other functions."""
    with patch(
        f"{MODULE}.find_file_by_path", return_value=None
    ) as mock_find, patch(
        f"{MODULE}.get_file_imports",
    ) as mock_imports, patch(
        f"{MODULE}.list_symbols_for_file",
    ) as mock_symbols:
        result = await get_context_for_file("scan-1", "nonexistent.py")

    assert result == {"imports": [], "symbols": []}
    # Ensure other functions were NOT called when file not found
    mock_imports.assert_not_called()
    mock_symbols.assert_not_called()


@pytest.mark.asyncio
async def test_get_context_for_file_returns_empty_lists_for_no_imports_or_symbols():
    """File found but no imports/symbols should return empty lists."""
    with patch(
        f"{MODULE}.find_file_by_path", return_value={"id": "file-1", "relative_path": "app/empty.py"}
    ), patch(
        f"{MODULE}.get_file_imports",
        return_value=[],
    ), patch(
        f"{MODULE}.list_symbols_for_file",
        return_value=[],
    ):
        result = await get_context_for_file("scan-1", "app/empty.py")

    assert result == {"imports": [], "symbols": []}
