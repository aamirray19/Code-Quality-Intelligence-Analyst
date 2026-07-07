from pydantic import BaseModel, Field, field_validator

ALLOWED_SEVERITIES = {"extreme", "high", "medium", "low"}


class AgentFindingOutput(BaseModel):
    title: str
    description: str
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    file_path: str | None = None
    symbol_name: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    evidence: list[str] = Field(default_factory=list)
    recommendation: str | None = None

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ALLOWED_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(ALLOWED_SEVERITIES)}, got '{v}'")
        return normalized


class AgentOutputList(BaseModel):
    findings: list[AgentFindingOutput]
