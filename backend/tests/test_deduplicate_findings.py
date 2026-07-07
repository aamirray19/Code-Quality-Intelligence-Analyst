import pytest

from app.workflows.analysis.nodes.deduplicate_findings import deduplicate_findings


def _finding(agent, severity, fingerprint, **overrides):
    base = {
        "scan_id": "scan-1",
        "agent": agent,
        "title": "Unhandled exception",
        "description": "desc",
        "severity": severity,
        "confidence": 0.7,
        "file_id": None,
        "symbol_id": None,
        "file_path": "app/main.py",
        "symbol_name": "handler",
        "start_line": 10,
        "end_line": 20,
        "evidence": [],
        "recommendation": None,
        "fingerprint": fingerprint,
        "related_agents": [],
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_merges_same_file_symbol_line_range_and_title_across_agents():
    findings = [
        _finding("security", "high", "fp1"),
        _finding("reliability", "medium", "fp2"),
    ]
    result = await deduplicate_findings({"deduped_findings": [], "normalized_findings": findings})
    deduped = result["deduped_findings"]

    assert len(deduped) == 1
    assert deduped[0]["agent"] == "security"  # higher severity wins as primary
    assert deduped[0]["related_agents"] == ["reliability"]


@pytest.mark.asyncio
async def test_keeps_distinct_findings_separate():
    findings = [
        _finding("security", "high", "fp1", title="Issue A"),
        _finding("performance", "high", "fp2", title="Issue B", start_line=100, end_line=110),
    ]
    result = await deduplicate_findings({"normalized_findings": findings})
    assert len(result["deduped_findings"]) == 2
