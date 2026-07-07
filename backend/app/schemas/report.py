from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ReportMetrics(BaseModel):
    total_findings: int
    by_severity: dict
    by_agent: dict
    files_affected: int


class ReportRecord(BaseModel):
    id: UUID
    scan_id: UUID
    summary_markdown: str
    metrics: ReportMetrics
    risk_score: float
    created_at: datetime
