from uuid import UUID

from pydantic import BaseModel


class AnalysisTaskRecord(BaseModel):
    id: UUID | None = None
    scan_id: UUID
    agent_name: str
    objective: str
    priority: int = 1
    target_file_ids: list[str] = []
    target_chunk_ids: list[str] = []
    target_symbol_ids: list[str] = []
    status: str = "pending"
    error_message: str | None = None
