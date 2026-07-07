from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FindingRecord(BaseModel):
    id: UUID | None = None
    scan_id: UUID
    agent: str
    title: str
    description: str
    severity: str
    confidence: float
    file_id: UUID | None = None
    symbol_id: UUID | None = None
    file_path: str | None = None
    symbol_name: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    evidence: list[str] = []
    recommendation: str | None = None
    fingerprint: str
    related_agents: list[str] = []
    created_at: datetime | None = None
