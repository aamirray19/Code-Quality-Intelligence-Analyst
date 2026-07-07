from uuid import UUID

from qdrant_client import models

from app.core.config import settings
from app.core.errors import AppError
from app.db.qdrant_client import get_qdrant_client
from app.schemas.chunks import EmbeddedChunk
from app.schemas.indexes import QdrantIndexResult

PAYLOAD_INDEX_FIELDS: dict[str, models.PayloadSchemaType] = {
    "scan_id": models.PayloadSchemaType.KEYWORD,
    "repo_full_name": models.PayloadSchemaType.KEYWORD,
    "language": models.PayloadSchemaType.KEYWORD,
    "chunk_type": models.PayloadSchemaType.KEYWORD,
    "file_path": models.PayloadSchemaType.KEYWORD,
}

# Payload indexes for agent_findings and scan_reports collections
FINDINGS_PAYLOAD_INDEX_FIELDS: dict[str, models.PayloadSchemaType] = {
    "scan_id": models.PayloadSchemaType.KEYWORD,
    "severity": models.PayloadSchemaType.KEYWORD,
    "agent": models.PayloadSchemaType.KEYWORD,
    "file_path": models.PayloadSchemaType.KEYWORD,
}

REPORTS_PAYLOAD_INDEX_FIELDS: dict[str, models.PayloadSchemaType] = {
    "scan_id": models.PayloadSchemaType.KEYWORD,
}


def _ensure_collection(vector_size: int) -> None:
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection_code_chunks

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        for field_name, schema_type in PAYLOAD_INDEX_FIELDS.items():
            client.create_payload_index(
                collection_name=collection_name, field_name=field_name, field_schema=schema_type
            )


def _ensure_findings_collection(vector_size: int) -> None:
    """Ensure agent_findings collection exists with required payload indexes."""
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection_agent_findings

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        for field_name, schema_type in FINDINGS_PAYLOAD_INDEX_FIELDS.items():
            client.create_payload_index(
                collection_name=collection_name, field_name=field_name, field_schema=schema_type
            )


def _ensure_reports_collection(vector_size: int) -> None:
    """Ensure scan_reports collection exists with required payload indexes."""
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection_scan_reports

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        for field_name, schema_type in REPORTS_PAYLOAD_INDEX_FIELDS.items():
            client.create_payload_index(
                collection_name=collection_name, field_name=field_name, field_schema=schema_type
            )


def upsert_chunks(
    scan_id: UUID,
    embedded_chunks: list[EmbeddedChunk],
    repo_full_name: str,
    branch: str,
    commit_sha: str,
) -> QdrantIndexResult:
    """Upsert embedded chunks into Qdrant, keyed by `chunk_id` (idempotent)."""
    if not embedded_chunks:
        return QdrantIndexResult(scan_id=scan_id, points_upserted=0)

    try:
        _ensure_collection(vector_size=len(embedded_chunks[0].vector))

        points = [
            models.PointStruct(
                id=str(chunk.chunk_id),
                vector=chunk.vector,
                payload={
                    **chunk.payload,
                    "repo_full_name": repo_full_name,
                    "branch": branch,
                    "commit_sha": commit_sha,
                },
            )
            for chunk in embedded_chunks
        ]

        client = get_qdrant_client()
        client.upsert(collection_name=settings.qdrant_collection_code_chunks, points=points)
    except Exception as exc:  # qdrant-client raises various transport/API errors
        raise AppError("QDRANT_UPSERT_FAILED", f"Failed to upsert chunks into Qdrant: {exc}", 502) from exc

    return QdrantIndexResult(scan_id=scan_id, points_upserted=len(points))
