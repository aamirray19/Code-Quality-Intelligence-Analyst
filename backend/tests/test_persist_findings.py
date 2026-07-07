from unittest.mock import MagicMock, patch

import pytest

from app.workflows.analysis.nodes.persist_findings import persist_findings

MODULE = "app.workflows.analysis.nodes.persist_findings"


def _finding(fingerprint="fp1"):
    return {
        "agent": "security",
        "title": "t",
        "description": "d",
        "severity": "high",
        "confidence": 0.9,
        "file_id": None,
        "symbol_id": None,
        "file_path": "f.py",
        "symbol_name": None,
        "start_line": None,
        "end_line": None,
        "evidence": [],
        "recommendation": None,
        "fingerprint": fingerprint,
        "related_agents": [],
    }


@pytest.mark.asyncio
async def test_upserts_ranked_findings_and_logs_event():
    fake_client = MagicMock()
    with patch("app.db.supabase_client.get_supabase_client", return_value=fake_client), patch(
        f"{MODULE}.scan_event_service.create_event"
    ) as event_mock:
        result = await persist_findings(
            {"scan_id": "scan-1", "ranked_findings": [_finding("fp1"), _finding("fp2")]}
        )

    assert result == {"status": "findings_persisted"}
    upsert_call = fake_client.table.return_value.upsert
    upsert_call.assert_called_once()
    assert upsert_call.call_args.kwargs["on_conflict"] == "scan_id,fingerprint"
    assert len(upsert_call.call_args.args[0]) == 2
    event_mock.assert_called_once()


@pytest.mark.asyncio
async def test_no_upsert_when_no_findings():
    fake_client = MagicMock()
    with patch("app.db.supabase_client.get_supabase_client", return_value=fake_client), patch(
        f"{MODULE}.scan_event_service.create_event"
    ):
        await persist_findings({"scan_id": "scan-1", "ranked_findings": []})

    fake_client.table.return_value.upsert.assert_not_called()
