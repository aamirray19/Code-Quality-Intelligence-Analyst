from uuid import UUID

from app.db.supabase_client import get_supabase_client
from app.schemas.symbols import CodeSymbol


def store_symbols(symbols: list[CodeSymbol]) -> dict[str, UUID]:
    """Upsert extracted symbols into `code_symbols` and resolve parent links.

    Symbols are inserted in two passes because `parent_symbol_id` must point
    at a real Supabase row id, which does not exist until after the first
    insert:

    1. Upsert all symbols (without `parent_symbol_id`), keyed on the unique
       constraint (scan_id, file_id, symbol_type, symbol_name, start_line, end_line).
    2. Build a `local_id -> real id` map from the returned rows, then update
       any symbol that had a `local_parent_id` to point at its resolved
       parent's real id.

    Returns the `local_id -> real id` map so callers (e.g. the chunk builder)
    can link chunks back to their originating symbol.
    """
    if not symbols:
        return {}

    client = get_supabase_client()

    payload = [
        {
            "scan_id": str(s.scan_id),
            "file_id": str(s.file_id),
            "symbol_type": s.symbol_type,
            "symbol_name": s.symbol_name,
            "qualified_name": s.qualified_name,
            "start_line": s.start_line,
            "end_line": s.end_line,
            "start_byte": s.start_byte,
            "end_byte": s.end_byte,
            "raw_code": s.raw_code,
            "language": s.language,
        }
        for s in symbols
    ]

    result = (
        client.table("code_symbols")
        .upsert(payload, on_conflict="scan_id,file_id,symbol_type,symbol_name,start_line,end_line")
        .execute()
    )

    def _key(row_like) -> tuple:
        return (
            str(row_like["scan_id"] if isinstance(row_like, dict) else row_like.scan_id),
            str(row_like["file_id"] if isinstance(row_like, dict) else row_like.file_id),
            row_like["symbol_type"] if isinstance(row_like, dict) else row_like.symbol_type,
            row_like["symbol_name"] if isinstance(row_like, dict) else row_like.symbol_name,
            row_like["start_line"] if isinstance(row_like, dict) else row_like.start_line,
            row_like["end_line"] if isinstance(row_like, dict) else row_like.end_line,
        )

    real_id_by_key = {_key(row): UUID(row["id"]) for row in result.data}
    local_id_to_real_id: dict[str, UUID] = {}
    for symbol in symbols:
        real_id = real_id_by_key.get(_key(symbol))
        if real_id is not None and symbol.local_id is not None:
            local_id_to_real_id[symbol.local_id] = real_id

    updates: list[dict] = []
    for symbol in symbols:
        if symbol.local_parent_id is None:
            continue
        real_id = local_id_to_real_id.get(symbol.local_id or "")
        parent_real_id = local_id_to_real_id.get(symbol.local_parent_id)
        if real_id is not None and parent_real_id is not None:
            updates.append({"id": str(real_id), "parent_symbol_id": str(parent_real_id)})

    for update in updates:
        client.table("code_symbols").update(
            {"parent_symbol_id": update["parent_symbol_id"]}
        ).eq("id", update["id"]).execute()

    return local_id_to_real_id


def store_parse_error(
    scan_id: UUID,
    file_id: UUID | None,
    error_type: str,
    error_message: str,
    metadata: dict | None = None,
) -> None:
    client = get_supabase_client()
    client.table("parse_errors").insert(
        {
            "scan_id": str(scan_id),
            "file_id": str(file_id) if file_id else None,
            "error_type": error_type,
            "error_message": error_message,
            "metadata": metadata,
        }
    ).execute()
