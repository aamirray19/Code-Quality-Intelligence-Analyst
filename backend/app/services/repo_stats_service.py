from collections import Counter
from uuid import UUID

from app.db.supabase_client import get_supabase_client
from app.schemas.indexes import RepoStats


def compute_repo_stats(
    scan_id: UUID,
    qdrant_points_count: int = 0,
    neo4j_nodes_count: int = 0,
    neo4j_relationships_count: int = 0,
) -> RepoStats:
    """Aggregate scan_files/code_symbols/code_chunks rows into repo_stats and upsert them."""
    client = get_supabase_client()

    files_result = (
        client.table("scan_files")
        .select("is_supported,parse_status,language,line_count")
        .eq("scan_id", str(scan_id))
        .execute()
    )
    files = files_result.data

    total_files_found = len(files)
    total_files_skipped = sum(1 for f in files if f["parse_status"] == "skipped")
    total_supported_files = sum(1 for f in files if f["is_supported"])
    parse_success_count = sum(1 for f in files if f["parse_status"] == "parsed")
    parse_failed_count = sum(1 for f in files if f["parse_status"] == "failed")
    total_files_indexed = parse_success_count
    total_lines_of_code = sum(f["line_count"] or 0 for f in files)

    language_breakdown = dict(Counter(f["language"] for f in files if f["language"]))

    symbol_count_result = (
        client.table("code_symbols")
        .select("id", count="exact")
        .eq("scan_id", str(scan_id))
        .execute()
    )
    symbol_count = symbol_count_result.count or 0

    chunk_count_result = (
        client.table("code_chunks")
        .select("id", count="exact")
        .eq("scan_id", str(scan_id))
        .execute()
    )
    chunk_count = chunk_count_result.count or 0

    stats = RepoStats(
        scan_id=scan_id,
        total_files_found=total_files_found,
        total_files_indexed=total_files_indexed,
        total_files_skipped=total_files_skipped,
        total_supported_files=total_supported_files,
        total_lines_of_code=total_lines_of_code,
        parse_success_count=parse_success_count,
        parse_failed_count=parse_failed_count,
        symbol_count=symbol_count,
        chunk_count=chunk_count,
        qdrant_points_count=qdrant_points_count,
        neo4j_nodes_count=neo4j_nodes_count,
        neo4j_relationships_count=neo4j_relationships_count,
        language_breakdown=language_breakdown,
    )

    client.table("repo_stats").upsert(
        {
            "scan_id": str(stats.scan_id),
            "total_files_found": stats.total_files_found,
            "total_files_indexed": stats.total_files_indexed,
            "total_files_skipped": stats.total_files_skipped,
            "total_supported_files": stats.total_supported_files,
            "total_lines_of_code": stats.total_lines_of_code,
            "parse_success_count": stats.parse_success_count,
            "parse_failed_count": stats.parse_failed_count,
            "symbol_count": stats.symbol_count,
            "chunk_count": stats.chunk_count,
            "qdrant_points_count": stats.qdrant_points_count,
            "neo4j_nodes_count": stats.neo4j_nodes_count,
            "neo4j_relationships_count": stats.neo4j_relationships_count,
            "language_breakdown": stats.language_breakdown,
        },
        on_conflict="scan_id",
    ).execute()

    return stats
