from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.repos import RepoInfoResponse, ScanStatusRepoResponse


class ScanRecord(BaseModel):
    id: UUID
    github_url: str
    repo_owner: str
    repo_name: str
    repo_full_name: str
    branch: str
    default_branch: str
    clone_url: str
    html_url: str
    repo_size_kb: int
    status: str
    error_message: str | None = None
    commit_sha: str | None = None
    phase: str | None = None
    started_at: datetime | None = None
    parsed_at: datetime | None = None
    reported_at: datetime | None = None
    failed_at: datetime | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateScanRequest(BaseModel):
    github_url: str = Field(..., min_length=10, max_length=500)


class CreateScanResponse(BaseModel):
    success: bool
    scan_id: UUID
    status: str
    message: str
    repo: RepoInfoResponse


class ScanProgress(BaseModel):
    files_discovered: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    symbols_extracted: int = 0
    chunks_created: int = 0


class ScanStatusResponse(BaseModel):
    scan_id: UUID
    status: str
    phase: str | None = None
    repo: ScanStatusRepoResponse
    progress: ScanProgress | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class ScanFileItem(BaseModel):
    file_id: UUID
    relative_path: str
    language: str | None = None
    extension: str | None = None
    size_bytes: int
    line_count: int
    parse_status: str
    skip_reason: str | None = None


class ScanFilesResponse(BaseModel):
    scan_id: UUID
    items: list[ScanFileItem]
    limit: int
    offset: int
    total: int


class ScanEventItem(BaseModel):
    event_type: str
    message: str
    metadata: dict | None = None
    created_at: datetime


class ScanEventsResponse(BaseModel):
    scan_id: UUID
    events: list[ScanEventItem]
