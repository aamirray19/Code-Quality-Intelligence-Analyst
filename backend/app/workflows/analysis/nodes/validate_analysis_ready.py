import asyncio

from qdrant_client import models

from app.core.config import settings
from app.db.neo4j_client import get_neo4j_driver
from app.db.qdrant_client import get_qdrant_client
from app.workflows.analysis.state import AnalysisState
from app.workflows.analysis.tools import supabase_metadata_tool


def _has_qdrant_points(scan_id: str) -> bool:
    client = get_qdrant_client()
    count_result = client.count(
        collection_name=settings.qdrant_collection_code_chunks,
        count_filter=models.Filter(
            must=[models.FieldCondition(key="scan_id", match=models.MatchValue(value=str(scan_id)))]
        ),
    )
    return count_result.count > 0


def _has_neo4j_scan_node(scan_id: str) -> bool:
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run("MATCH (s:Scan {scan_id: $scan_id}) RETURN s LIMIT 1", scan_id=str(scan_id))
        return result.single() is not None


async def validate_analysis_ready(state: AnalysisState) -> dict:
    scan_id = state["scan_id"]
    scan = await asyncio.to_thread(supabase_metadata_tool.get_scan, scan_id)

    if scan is not None and scan["status"] == "analyzed":
        return {"status": "skipped"}

    if scan is None or scan["status"] != "parsed":
        return {"status": "not_ready", "errors": ["SCAN_NOT_PARSED"]}

    files = await asyncio.to_thread(supabase_metadata_tool.list_files, scan_id)
    if not files:
        return {"status": "not_ready", "errors": ["MISSING_SCAN_FILES"]}

    # code_symbols rows are intentionally NOT required here (2026-07-06
    # decision) — a repo of only unsupported-language files can have 0
    # symbols but still be analyzable via chunks.
    chunks = await asyncio.to_thread(supabase_metadata_tool.list_chunks, scan_id, None, 1)
    if not chunks:
        return {"status": "not_ready", "errors": ["MISSING_CODE_CHUNKS"]}

    has_points = await asyncio.to_thread(_has_qdrant_points, scan_id)
    if not has_points:
        return {"status": "not_ready", "errors": ["MISSING_QDRANT_POINTS"]}

    has_scan_node = await asyncio.to_thread(_has_neo4j_scan_node, scan_id)
    if not has_scan_node:
        return {"status": "not_ready", "errors": ["MISSING_NEO4J_GRAPH"]}

    return {"status": "ready"}
