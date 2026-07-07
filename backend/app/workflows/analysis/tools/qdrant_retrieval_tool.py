# backend/app/workflows/analysis/tools/qdrant_retrieval_tool.py
from qdrant_client import models

from app.core.config import settings
from app.db.qdrant_client import get_qdrant_client
from app.services.embedding_service import embed_text


def search_code_chunks(scan_id, query: str, limit: int = 12) -> list[dict]:
    """Semantic search over a scan's indexed chunks, always filtered by scan_id."""
    vector = embed_text(query)
    if not vector:
        return []

    client = get_qdrant_client()
    results = client.search(
        collection_name=settings.qdrant_collection_code_chunks,
        query_vector=vector,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="scan_id", match=models.MatchValue(value=str(scan_id)))]
        ),
        limit=limit,
    )
    return [{"chunk_id": r.id, "score": r.score, **r.payload} for r in results]


def find_similar_chunks(scan_id, chunk_id: str, limit: int = 5) -> list[dict]:
    """Find chunks similar to an already-indexed chunk, scoped to the same scan."""
    client = get_qdrant_client()
    results = client.recommend(
        collection_name=settings.qdrant_collection_code_chunks,
        positive=[chunk_id],
        query_filter=models.Filter(
            must=[models.FieldCondition(key="scan_id", match=models.MatchValue(value=str(scan_id)))]
        ),
        limit=limit,
    )
    return [{"chunk_id": r.id, "score": r.score, **r.payload} for r in results]
