from unittest.mock import patch

import pytest

from app.workflows.analysis.nodes.normalize_findings import normalize_findings

MODULE = "app.workflows.analysis.nodes.normalize_findings"


def _raw_finding(**overrides):
    base = {
        "agent": "security",
        "title": "SQL injection",
        "description": "desc",
        "severity": "HIGH",
        "confidence": 1.5,
        "file_path": "./app/db.py",
        "symbol_name": "run_query",
        "start_line": 10,
        "end_line": 20,
        "evidence": ["evidence 1"],
        "recommendation": "fix it",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_normalizes_severity_clamps_confidence_and_resolves_ids():
    with patch(
        f"{MODULE}.supabase_metadata_tool.find_file_by_path", return_value={"id": "file-1"}
    ), patch(
        f"{MODULE}.supabase_metadata_tool.find_symbol_by_name", return_value={"id": "sym-1"}
    ), patch(f"{MODULE}.scan_event_service.create_event"):
        result = await normalize_findings({"scan_id": "scan-1", "raw_findings": [_raw_finding()]})

    finding = result["normalized_findings"][0]
    assert finding["severity"] == "high"
    assert finding["confidence"] == 1.0
    assert finding["file_path"] == "app/db.py"
    assert finding["file_id"] == "file-1"
    assert finding["symbol_id"] == "sym-1"
    assert finding["fingerprint"]


@pytest.mark.asyncio
async def test_drops_finding_missing_required_fields():
    bad = _raw_finding(title="")
    with patch(f"{MODULE}.scan_event_service.create_event"):
        result = await normalize_findings({"scan_id": "scan-1", "raw_findings": [bad]})
    assert result["normalized_findings"] == []


@pytest.mark.asyncio
async def test_leaves_ids_null_when_no_match_found():
    with patch(f"{MODULE}.supabase_metadata_tool.find_file_by_path", return_value=None), patch(
        f"{MODULE}.scan_event_service.create_event"
    ):
        result = await normalize_findings({"scan_id": "scan-1", "raw_findings": [_raw_finding()]})

    finding = result["normalized_findings"][0]
    assert finding["file_id"] is None
    assert finding["symbol_id"] is None
