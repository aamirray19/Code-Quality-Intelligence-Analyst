from uuid import UUID

from pydantic import BaseModel


class QdrantIndexResult(BaseModel):
    scan_id: UUID
    points_upserted: int


class Neo4jIndexResult(BaseModel):
    scan_id: UUID
    nodes_upserted: int
    relationships_upserted: int


class RepoStats(BaseModel):
    scan_id: UUID
    total_files_found: int = 0
    total_files_indexed: int = 0
    total_files_skipped: int = 0
    total_supported_files: int = 0
    total_lines_of_code: int = 0
    parse_success_count: int = 0
    parse_failed_count: int = 0
    symbol_count: int = 0
    chunk_count: int = 0
    qdrant_points_count: int = 0
    neo4j_nodes_count: int = 0
    neo4j_relationships_count: int = 0
    language_breakdown: dict[str, int] = {}
