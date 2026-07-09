from uuid import UUID

from pydantic import BaseModel


class CodeSymbol(BaseModel):
    scan_id: UUID
    file_id: UUID
    symbol_type: str
    symbol_name: str
    qualified_name: str | None = None
    parent_symbol_id: UUID | None = None
    start_line: int
    end_line: int
    start_byte: int | None = None
    end_byte: int | None = None
    raw_code: str | None = None
    language: str

    # Local id used only within a single file's extraction pass, so that
    # nested symbols (e.g. methods inside a class) can reference their
    # parent before either has a real Supabase-assigned UUID.
    local_id: str | None = None
    local_parent_id: str | None = None
