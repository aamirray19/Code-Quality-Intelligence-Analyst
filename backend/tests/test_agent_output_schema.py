import pytest
from pydantic import ValidationError

from app.schemas.agent_output import AgentFindingOutput, AgentOutputList


def test_valid_finding_normalizes_severity_case():
    finding = AgentFindingOutput(
        title="SQL injection in query builder",
        description="User input concatenated directly into SQL.",
        severity="HIGH",
        confidence=0.9,
        file_path="app/db.py",
        symbol_name="run_query",
        start_line=10,
        end_line=20,
        evidence=["string concatenation on line 15"],
        recommendation="Use parameterized queries.",
    )
    assert finding.severity == "high"


def test_invalid_severity_rejected():
    with pytest.raises(ValidationError):
        AgentFindingOutput(
            title="x", description="y", severity="critical-ish", confidence=0.5
        )


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        AgentFindingOutput(title="x", description="y", severity="low", confidence=1.5)


def test_output_list_wraps_findings():
    data = AgentOutputList(
        findings=[
            {"title": "x", "description": "y", "severity": "low", "confidence": 0.1}
        ]
    )
    assert len(data.findings) == 1
