from pathlib import Path
from uuid import UUID

from pydantic import BaseModel


class DiscoveredFile(BaseModel):
    scan_id: UUID
    relative_path: str
    absolute_path: Path
    file_name: str
    extension: str
    language: str | None
    size_bytes: int
    line_count: int
    content_hash: str
    is_supported: bool
    parse_status: str
    skip_reason: str | None = None


class ScanFileRecord(BaseModel):
    id: UUID
    scan_id: UUID
    relative_path: str
    file_name: str
    extension: str | None = None
    language: str | None = None
    size_bytes: int
    line_count: int
    content_hash: str
    is_supported: bool
    parse_status: str
    skip_reason: str | None = None
    parse_error: str | None = None
