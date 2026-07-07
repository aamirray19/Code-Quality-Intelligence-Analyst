# backend/tests/test_agents.py
import json
from unittest.mock import MagicMock, patch

import pytest

from app.workflows.analysis.agents.complexity_agent import complexity_agent
from app.workflows.analysis.agents.duplication_agent import duplication_agent
from app.workflows.analysis.agents.performance_agent import performance_agent
from app.workflows.analysis.agents.reliability_agent import reliability_agent
from app.workflows.analysis.agents.security_agent import security_agent

MODULE = "app.workflows.analysis.agents.agent_factory"

AGENTS = [
    ("security", security_agent),
    ("performance", performance_agent),
    ("complexity", complexity_agent),
    ("duplication", duplication_agent),
    ("reliability", reliability_agent),
]


def _worker_input():
    return {
        "scan_id": "scan-1",
        "task": {
            "task_id": "task-1",
            "agent_name": "security",
            "objective": "Check for issues.",
            "priority": 1,
            "target_file_ids": ["f1"],
            "target_chunk_ids": [],
            "target_symbol_ids": ["sym1"],
        },
    }


@pytest.mark.parametrize("agent_name,agent_fn", AGENTS)
@pytest.mark.asyncio
async def test_agent_returns_findings_on_valid_llm_response(agent_name, agent_fn):
    findings_json = json.dumps(
        [
            {
                "title": "Issue found",
                "description": "Something is wrong.",
                "severity": "high",
                "confidence": 0.8,
                "file_path": "app/main.py",
                "symbol_name": "handler",
                "start_line": 1,
                "end_line": 5,
                "evidence": ["line 3"],
                "recommendation": "Fix it.",
            }
        ]
    )

    async def fake_complete(*, system, user):
        return findings_json

    fake_llm = MagicMock()
    fake_llm.complete = fake_complete

    with patch(f"{MODULE}.build_llm_client", return_value=fake_llm), patch(
        f"{MODULE}.supabase_metadata_tool.list_chunks", return_value=[]
    ), patch(f"{MODULE}.supabase_metadata_tool.get_symbol_context", return_value=None), patch(
        f"{MODULE}.neo4j_graph_tool.get_symbol_neighbors", return_value=[]
    ), patch(f"{MODULE}._mark_task_running"), patch(f"{MODULE}._mark_task_completed"), patch(
        f"{MODULE}._record_agent_run"
    ):
        result = await agent_fn(_worker_input())

    assert len(result["raw_findings"]) == 1
    assert result["raw_findings"][0]["agent"] == agent_name
    assert result["raw_findings"][0]["title"] == "Issue found"


@pytest.mark.asyncio
async def test_agent_records_token_usage_on_success():
    findings_json = json.dumps(
        [
            {
                "title": "Issue found",
                "description": "Something is wrong.",
                "severity": "high",
                "confidence": 0.8,
                "file_path": "app/main.py",
                "symbol_name": "handler",
                "start_line": 1,
                "end_line": 5,
                "evidence": ["line 3"],
                "recommendation": "Fix it.",
            }
        ]
    )

    async def fake_complete(*, system, user):
        return findings_json

    fake_llm = MagicMock()
    fake_llm.complete = fake_complete
    fake_llm.last_usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

    with patch(f"{MODULE}.build_llm_client", return_value=fake_llm), patch(
        f"{MODULE}.supabase_metadata_tool.list_chunks", return_value=[]
    ), patch(f"{MODULE}.supabase_metadata_tool.get_symbol_context", return_value=None), patch(
        f"{MODULE}.neo4j_graph_tool.get_symbol_neighbors", return_value=[]
    ), patch(f"{MODULE}._mark_task_running"), patch(f"{MODULE}._mark_task_completed"), patch(
        f"{MODULE}._record_agent_run"
    ) as record_mock:
        await security_agent(_worker_input())

    record_mock.assert_called_once()
    kwargs = record_mock.call_args.kwargs
    assert kwargs["usage"] == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    assert kwargs["findings_count"] == 1
    assert kwargs["model_provider"] == "openrouter"


@pytest.mark.asyncio
async def test_agent_returns_empty_findings_after_exhausted_retries():
    async def failing_complete(*, system, user):
        raise RuntimeError("LLM down")

    fake_llm = MagicMock()
    fake_llm.complete = failing_complete

    with patch(f"{MODULE}.build_llm_client", return_value=fake_llm), patch(
        f"{MODULE}.supabase_metadata_tool.list_chunks", return_value=[]
    ), patch(f"{MODULE}.supabase_metadata_tool.get_symbol_context", return_value=None), patch(
        f"{MODULE}.neo4j_graph_tool.get_symbol_neighbors", return_value=[]
    ), patch(f"{MODULE}._mark_task_running"), patch(f"{MODULE}._mark_task_failed") as failed_mock, patch(
        f"{MODULE}._record_agent_run"
    ) as record_mock, patch(f"{MODULE}._log_agent_failed_event") as log_mock, patch(
        f"{MODULE}.settings"
    ) as settings_mock:
        settings_mock.agent_max_retries = 0
        settings_mock.max_agent_context_chunks = 12
        settings_mock.max_findings_per_agent = 20
        result = await security_agent(_worker_input())

    assert result == {"raw_findings": []}
    failed_mock.assert_called_once()
    record_mock.assert_called_once()
    log_mock.assert_called_once()
