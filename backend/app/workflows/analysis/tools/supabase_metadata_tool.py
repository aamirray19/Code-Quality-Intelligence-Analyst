# backend/app/workflows/analysis/tools/supabase_metadata_tool.py
from app.db.supabase_client import get_supabase_client


def get_scan(scan_id) -> dict | None:
    client = get_supabase_client()
    result = client.table("scans").select("*").eq("id", str(scan_id)).limit(1).execute()
    return result.data[0] if result.data else None


def get_repo_stats(scan_id) -> dict | None:
    client = get_supabase_client()
    result = client.table("repo_stats").select("*").eq("scan_id", str(scan_id)).limit(1).execute()
    return result.data[0] if result.data else None


def list_files(scan_id, limit: int = 5000) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("scan_files")
        .select("id,relative_path,language,extension,is_supported,line_count")
        .eq("scan_id", str(scan_id))
        .limit(limit)
        .execute()
    )
    return result.data


def list_symbols(scan_id, limit: int = 500) -> list[dict]:
    """Return up to `limit` non-import symbols for a scan, sorted by size
    (end_line - start_line) descending so the top-N-by-LOC cap (2026-07-06
    decision) is applied consistently regardless of caller."""
    client = get_supabase_client()
    result = (
        client.table("code_symbols")
        .select("id,file_id,symbol_type,symbol_name,qualified_name,start_line,end_line")
        .eq("scan_id", str(scan_id))
        .neq("symbol_type", "import")
        .execute()
    )
    rows = result.data
    rows.sort(key=lambda r: (r["end_line"] - r["start_line"]), reverse=True)
    return rows[:limit]


def list_chunks(scan_id, file_ids: list[str] | None = None, limit: int = 200) -> list[dict]:
    client = get_supabase_client()
    query = client.table("code_chunks").select("*").eq("scan_id", str(scan_id))
    if file_ids:
        query = query.in_("file_id", file_ids)
    result = query.limit(limit).execute()
    return result.data


def get_chunk_metadata(chunk_id: str) -> dict | None:
    client = get_supabase_client()
    result = client.table("code_chunks").select("*").eq("id", chunk_id).limit(1).execute()
    return result.data[0] if result.data else None


def get_symbol_context(symbol_id: str) -> dict | None:
    client = get_supabase_client()
    result = client.table("code_symbols").select("*").eq("id", symbol_id).limit(1).execute()
    return result.data[0] if result.data else None


def find_file_by_path(scan_id, file_path: str) -> dict | None:
    client = get_supabase_client()
    result = (
        client.table("scan_files")
        .select("id,relative_path")
        .eq("scan_id", str(scan_id))
        .eq("relative_path", file_path)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def find_symbol_by_name(scan_id, file_id: str, symbol_name: str) -> dict | None:
    client = get_supabase_client()
    result = (
        client.table("code_symbols")
        .select("id,symbol_name")
        .eq("scan_id", str(scan_id))
        .eq("file_id", file_id)
        .eq("symbol_name", symbol_name)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
