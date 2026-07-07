# backend/tests/test_rank_findings.py
import pytest

from app.workflows.analysis.nodes.rank_findings import rank_findings


def _finding(severity, confidence, evidence_count=0, related_agent_count=0, title="t"):
    return {
        "scan_id": "scan-1",
        "agent": "security",
        "title": title,
        "description": "d",
        "severity": severity,
        "confidence": confidence,
        "file_id": None,
        "symbol_id": None,
        "file_path": "f.py",
        "symbol_name": None,
        "start_line": None,
        "end_line": None,
        "evidence": ["e"] * evidence_count,
        "recommendation": None,
        "fingerprint": title,
        "related_agents": ["a"] * related_agent_count,
    }


@pytest.mark.asyncio
async def test_sorts_by_severity_then_confidence_then_evidence_then_related_agents():
    findings = [
        _finding("low", 0.9, title="low-sev"),
        _finding("extreme", 0.5, title="extreme-sev"),
        _finding("high", 0.9, evidence_count=1, title="high-more-evidence"),
        _finding("high", 0.9, evidence_count=0, title="high-less-evidence"),
    ]
    result = await rank_findings({"deduped_findings": findings})
    titles = [f["title"] for f in result["ranked_findings"]]
    assert titles == ["extreme-sev", "high-more-evidence", "high-less-evidence", "low-sev"]
