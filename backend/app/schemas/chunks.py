from uuid import UUID

from pydantic import BaseModel


class CodeChunk(BaseModel):
    scan_id: UUID
    file_id: UUID
    symbol_id: UUID | None = None
    chunk_type: str
    language: str | None = None
    file_path: str
    symbol_name: str | None = None
    start_line: int
    end_line: int
    content: str
    content_hash: str
    token_count: int | None = None


class EmbeddedChunk(BaseModel):
    chunk_id: UUID
    vector: list[float]
    payload: dict
