from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChatSessionRecord(BaseModel):
    id: UUID
    scan_id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatMessageRecord(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    sources: list
    created_at: datetime


class ChatMessageCreate(BaseModel):
    content: str
