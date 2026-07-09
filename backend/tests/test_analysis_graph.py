# backend/tests/test_analysis_graph.py
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from app.workflows.analysis.graph import run_analysis

MODULE_LOAD = "app.workflows.analysis.nodes.load_scan_context"
MODULE_VALIDATE = "app.workflows.analysis.nodes.validate_analysis_ready"
MODULE_PLAN = "app.workflows.analysis.nodes.build_analysis_plan"
MODULE_FACTORY = "app.workflows.analysis.agents.agent_factory"
MODULE_NORMALIZE = "app.workflows.analysis.nodes.normalize_findings"
MODULE_PERSIST = "app.workflows.analysis.nodes.persist_findings"
MODULE_MARK = "app.workflows.analysis.nodes.mark_scan_analyzed"


def _scan_row():
    return {
        "id": "12345678-1234-1234-1234-123456789abc",
        "repo_full_name": "owner/repo",
        "default_branch": "main",
        "commit_sha": "abc",
        "status": "parsed",
    }


def _agent_finding(agent_name):
    return {
        "agent": agent_name,
        "title": f"{agent_name} finding",
        "description": "desc",
        "severity": "high",
        "confidence": 0.9,
        "file_path": "app/main.py",
        "symbol_name": None,
        "start_line": 1,
        "end_line": 5,
        "evidence": ["e"],
        "recommendation": "fix",
    }


@pytest.mark.asyncio
async def test_full_graph_run_reaches_analyzed_status():
    async def fake_complete(*, system, user):
        import json
        for agent_name in ["security", "performance", "complexity", "duplication", "reliability"]:
            if agent_name in system.lower():
                return json.dumps([_agent_finding(agent_name)])
        return "[]"

    fake_llm = MagicMock()
    fake_llm.complete = fake_complete

    patches = [
        patch(f"{MODULE_LOAD}.supabase_metadata_tool.get_scan", return_value=_scan_row()),
        patch(f"{MODULE_LOAD}.supabase_metadata_tool.get_repo_stats", return_value=None),
        patch(f"{MODULE_VALIDATE}.supabase_metadata_tool.get_scan", return_value=_scan_row()),
        patch(f"{MODULE_VALIDATE}.supabase_metadata_tool.list_files", return_value=[{"id": "f1"}]),
        patch(f"{MODULE_VALIDATE}.supabase_metadata_tool.list_chunks", return_value=[{"id": "c1"}]),
        patch(f"{MODULE_VALIDATE}._has_qdrant_points", return_value=True),
        patch(f"{MODULE_VALIDATE}._has_neo4j_scan_node", return_value=True),
        patch(f"{MODULE_PLAN}.supabase_metadata_tool.list_files", return_value=[{"id": "f1", "relative_path": "app/main.py", "language": "python"}]),
        patch(f"{MODULE_PLAN}.supabase_metadata_tool.list_symbols", return_value=[]),
        patch(f"{MODULE_PLAN}._persist_analysis_task", side_effect=lambda record: {"id": f"task-{record.agent_name}"}),
        patch(f"{MODULE_PLAN}._call_supervisor_llm", return_value=None),
        patch(f"{MODULE_FACTORY}._gather_context", return_value={"objective": "x", "chunks": [], "symbols": [], "related_symbols": []}),
        patch(f"{MODULE_FACTORY}._mark_task_running"),
        patch(f"{MODULE_FACTORY}._mark_task_completed"),
        patch(f"{MODULE_FACTORY}._record_agent_run"),
        patch(f"{MODULE_FACTORY}.OpenRouterClient", return_value=fake_llm),
        patch(f"{MODULE_NORMALIZE}.supabase_metadata_tool.find_file_by_path", return_value=None),
        patch(f"{MODULE_NORMALIZE}.scan_event_service.create_event"),
        patch(f"{MODULE_PERSIST}.scan_event_service.create_event"),
        patch("app.db.supabase_client.get_supabase_client"),
        patch(f"{MODULE_MARK}.scan_service.update_scan"),
        patch(f"{MODULE_MARK}.scan_event_service.create_event"),
    ]

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await run_analysis("12345678-1234-1234-1234-123456789abc")

    assert result["status"] == "analyzed"
    assert len(result["ranked_findings"]) == 5


@pytest.mark.asyncio
async def test_already_analyzed_scan_is_skipped():
    analyzed_scan = {**_scan_row(), "status": "analyzed"}
    patches = [
        patch(f"{MODULE_LOAD}.supabase_metadata_tool.get_scan", return_value=analyzed_scan),
        patch(f"{MODULE_LOAD}.supabase_metadata_tool.get_repo_stats", return_value=None),
        patch(f"{MODULE_VALIDATE}.supabase_metadata_tool.get_scan", return_value=analyzed_scan),
    ]

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        result = await run_analysis("12345678-1234-1234-1234-123456789abc")

    assert result["status"] == "skipped"


