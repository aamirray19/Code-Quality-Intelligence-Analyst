from uuid import UUID

from app.db.supabase_client import get_supabase_client
from app.schemas.chunks import CodeChunk


def store_chunks(chunks: list[CodeChunk]) -> list[dict]:
    """Upsert chunk metadata into `code_chunks`.

    Upserts on (scan_id, file_id, chunk_type, content_hash) so re-running a
    scan does not create duplicate chunk rows. Returns the stored rows
    (including Supabase-assigned `id`s) in Supabase's response order.
    """
    if not chunks:
        return []

    client = get_supabase_client()
    payload = [
        {
            "scan_id": str(c.scan_id),
            "file_id": str(c.file_id),
            "symbol_id": str(c.symbol_id) if c.symbol_id else None,
            "chunk_type": c.chunk_type,
            "language": c.language,
            "file_path": c.file_path,
            "symbol_name": c.symbol_name,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "content": c.content,
            "content_hash": c.content_hash,
            "token_count": c.token_count,
        }
        for c in chunks
    ]

    result = (
        client.table("code_chunks")
        .upsert(payload, on_conflict="scan_id,file_id,chunk_type,content_hash")
        .execute()
    )
    return result.data


def store_chunks_with_ids(chunks: list[CodeChunk]) -> list[tuple[CodeChunk, UUID]]:
    """Like `store_chunks`, but returns (chunk, real_id) pairs in the same
    order as the input `chunks`, matched via the chunk's unique key rather
    than relying on Supabase preserving upsert response order.
    """
    rows = store_chunks(chunks)

    def _key(file_id: str, chunk_type: str, content_hash: str) -> tuple:
        return (file_id, chunk_type, content_hash)

    id_by_key = {
        _key(row["file_id"], row["chunk_type"], row["content_hash"]): UUID(row["id"])
        for row in rows
    }

    matched: list[tuple[CodeChunk, UUID]] = []
    for chunk in chunks:
        chunk_id = id_by_key.get(_key(str(chunk.file_id), chunk.chunk_type, chunk.content_hash))
        if chunk_id is not None:
            matched.append((chunk, chunk_id))
    return matched


def mark_chunks_indexed(chunk_ids: list[UUID], qdrant: bool = False, neo4j: bool = False) -> None:
    if not chunk_ids:
        return
    client = get_supabase_client()

    if qdrant:
        # qdrant_point_id is always the chunk's own id (phase2.md 5.11 point-ID
        # scheme). Must be a per-row UPDATE (not upsert): Postgres validates
        # NOT NULL constraints on the insert candidate before ON CONFLICT is
        # even considered, so a partial-column upsert fails NOT NULL checks
        # even when the row already exists.
        for chunk_id in chunk_ids:
            client.table("code_chunks").update(
                {"indexed_in_qdrant": True, "qdrant_point_id": str(chunk_id)}
            ).eq("id", str(chunk_id)).execute()

    if neo4j:
        client.table("code_chunks").update({"indexed_in_neo4j": True}).in_(
            "id", [str(i) for i in chunk_ids]
        ).execute()


def get_chunks_for_scan(scan_id: UUID) -> list[dict]:
    client = get_supabase_client()
    result = client.table("code_chunks").select("*").eq("scan_id", str(scan_id)).execute()
    return result.data
