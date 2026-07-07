import asyncio

from qdrant_client import models

from app.core.config import settings
from app.core.errors import AppError
from app.db.qdrant_client import get_qdrant_client
from app.db.supabase_client import get_supabase_client
from app.services.embedding_service import embed_text


async def retrieve_relevant_docs(scan_id: str, query: str, top_k: int = 8) -> list[dict]:
    """Retrieve relevant documents from all Qdrant collections for RAG chatbot.
    
    Searches across three collections:
    - code_chunks: Existing Phase 2 code chunks (metadata only in Qdrant, fetches content from Supabase)
    - agent_findings: Phase 4 findings, file summaries, and agent summaries
    - scan_reports: Phase 4 scan report summary
    
    Args:
        scan_id: The scan UUID as a string
        query: User's question text to embed and search
        top_k: Maximum number of results to return (default: 8)
    
    Returns:
        List of dicts, each with:
        - text: The displayable/embeddable text content
        - source_type: One of "code_chunk", "finding", "file_summary", "agent_summary", "scan_report"
        - payload: The raw Qdrant point payload
        - score: The Qdrant similarity score
        
        Sorted by score descending, truncated to top_k.
    
    Raises:
        AppError: If embedding or Qdrant search fails
    """
    # Embed the query once
    try:
        vector = embed_text(query)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("EMBEDDING_FAILED", f"Failed to embed query: {exc}", 502) from exc
    
    if not vector:
        return []
    
    # Define scan_id filter (same for all collections)
    scan_filter = models.Filter(
        must=[models.FieldCondition(key="scan_id", match=models.MatchValue(value=scan_id))]
    )
    
    # Search all 3 collections in parallel using asyncio.gather with asyncio.to_thread
    # Per-collection limit: use top_k for each to balance recall vs cost
    # (will merge and re-truncate to top_k afterward)
    try:
        client = get_qdrant_client()
        
        code_chunks_results, agent_findings_results, scan_reports_results = await asyncio.gather(
            asyncio.to_thread(
                client.search,
                collection_name=settings.qdrant_collection_code_chunks,
                query_vector=vector,
                query_filter=scan_filter,
                limit=top_k,
            ),
            asyncio.to_thread(
                client.search,
                collection_name=settings.qdrant_collection_agent_findings,
                query_vector=vector,
                query_filter=scan_filter,
                limit=top_k,
            ),
            asyncio.to_thread(
                client.search,
                collection_name=settings.qdrant_collection_scan_reports,
                query_vector=vector,
                query_filter=scan_filter,
                limit=top_k,
            ),
        )
    except Exception as exc:
        raise AppError(
            "QDRANT_SEARCH_FAILED", f"Failed to search Qdrant collections: {exc}", 502
        ) from exc
    
    # Fetch chunk content from Supabase for code_chunks results
    chunk_ids = [r.payload["chunk_id"] for r in code_chunks_results if "chunk_id" in r.payload]
    chunk_content_map = {}
    if chunk_ids:
        try:
            supabase = get_supabase_client()
            result = await asyncio.to_thread(
                lambda: supabase.table("code_chunks")
                .select("id, content")
                .in_("id", chunk_ids)
                .execute()
            )
            chunk_content_map = {row["id"]: row["content"] for row in result.data if "content" in row}
        except Exception as exc:
            raise AppError(
                "SUPABASE_QUERY_FAILED", f"Failed to fetch chunk content from Supabase: {exc}", 502
            ) from exc
    
    # Build merged list of documents
    merged_docs = []
    
    # Process code_chunks results
    for r in code_chunks_results:
        chunk_id = r.payload.get("chunk_id")
        # Skip chunks that don't have content in Supabase
        if chunk_id and chunk_id in chunk_content_map:
            merged_docs.append({
                "text": chunk_content_map[chunk_id],
                "source_type": "code_chunk",
                "payload": r.payload,
                "score": r.score,
            })
    
    # Process agent_findings results
    for r in agent_findings_results:
        # source_type comes from the doc_type field in payload
        doc_type = r.payload.get("doc_type", "unknown")
        merged_docs.append({
            "text": r.payload.get("content", ""),
            "source_type": doc_type,  # "finding", "file_summary", or "agent_summary"
            "payload": r.payload,
            "score": r.score,
        })
    
    # Process scan_reports results
    for r in scan_reports_results:
        merged_docs.append({
            "text": r.payload.get("content", ""),
            "source_type": "scan_report",
            "payload": r.payload,
            "score": r.score,
        })
    
    # Sort by score descending and truncate to top_k
    merged_docs.sort(key=lambda doc: doc["score"], reverse=True)
    return merged_docs[:top_k]
