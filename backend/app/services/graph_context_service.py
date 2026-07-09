import asyncio

from app.db.supabase_client import get_supabase_client
from app.workflows.analysis.tools import neo4j_graph_tool, supabase_metadata_tool


def find_file_by_path(scan_id: str, file_path: str) -> dict | None:
    """Wrapper around supabase_metadata_tool.find_file_by_path for testing."""
    return supabase_metadata_tool.find_file_by_path(scan_id, file_path)


def get_file_imports(scan_id: str, file_id: str) -> list[dict]:
    """Wrapper around neo4j_graph_tool.get_file_imports for testing."""
    return neo4j_graph_tool.get_file_imports(scan_id, file_id)


def list_symbols_for_file(scan_id: str, file_id: str) -> list[dict]:
    """Fetch all non-import symbols defined in a specific file from Supabase."""
    client = get_supabase_client()
    result = (
        client.table("code_symbols")
        .select("id,symbol_name,symbol_type,qualified_name,start_line,end_line")
        .eq("scan_id", str(scan_id))
        .eq("file_id", file_id)
        .neq("symbol_type", "import")
        .execute()
    )
    return result.data


async def get_context_for_file(scan_id: str, file_path: str) -> dict:
    """Fetch graph context (imports + symbols) for a given file.

    Returns a dict with 'imports' and 'symbols' keys, each containing a list.
    If the file is not found, both lists are empty.

    Args:
        scan_id: The scan identifier.
        file_path: Relative path to the file.

    Returns:
        A dict with keys 'imports' and 'symbols', each containing a list of dicts.
    """
    # Find the file by path (wrapped in to_thread for sync I/O)
    file_row = await asyncio.to_thread(find_file_by_path, scan_id, file_path)

    # If file not found, return empty context
    if not file_row:
        return {"imports": [], "symbols": []}

    file_id = file_row["id"]

    # Fetch imports and symbols in parallel (both wrapped in to_thread)
    imports, symbols = await asyncio.gather(
        asyncio.to_thread(get_file_imports, scan_id, file_id),
        asyncio.to_thread(list_symbols_for_file, scan_id, file_id),
    )

    return {"imports": imports, "symbols": symbols}
