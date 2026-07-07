# backend/tests/test_build_analysis_plan.py
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.workflows.analysis.nodes.build_analysis_plan import (
    AGENT_NAMES,
    build_analysis_plan,
)

MODULE = "app.workflows.analysis.nodes.build_analysis_plan"


def _files():
    return [{"id": "f1", "relative_path": "app/main.py", "language": "python"}]


def _symbols():
    return [{"id": "sym1", "file_id": "f1", "symbol_name": "handler", "symbol_type": "function", "start_line": 1, "end_line": 20}]


def _fake_supabase_insert(row_id="task-1"):
    client = MagicMock()
    execute_result = MagicMock()
    execute_result.data = [{"id": row_id}]
    client.table.return_value.insert.return_value.execute.return_value = execute_result
    return client


@pytest.mark.asyncio
async def test_uses_llm_plan_when_valid_json_returned():
    scan_id = str(uuid4())
    llm_response = json.dumps(
        [
            {
                "agent_name": "security",
                "objective": "Check for injection risks.",
                "priority": 2,
                "target_file_ids": ["f1"],
                "target_symbol_ids": ["sym1"],
            }
        ]
    )
    fake_llm = MagicMock()

    async def fake_complete(*, system, user):
        return llm_response

    fake_llm.complete = fake_complete

    with patch(f"{MODULE}.supabase_metadata_tool.list_files", return_value=_files()), patch(
        f"{MODULE}.supabase_metadata_tool.list_symbols", return_value=_symbols()
    ), patch(f"{MODULE}.build_llm_client", return_value=fake_llm), patch(
        f"{MODULE}._persist_analysis_task", return_value={"id": "task-1"}
    ):
        result = await build_analysis_plan({"scan_id": scan_id})

    assert result["status"] == "planned"
    assert len(result["analysis_tasks"]) == 1
    assert result["analysis_tasks"][0]["agent_name"] == "security"
    assert result["analysis_tasks"][0]["task_id"] == "task-1"


@pytest.mark.asyncio
async def test_falls_back_to_deterministic_plan_when_llm_fails():
    scan_id = str(uuid4())

    async def failing_complete(*, system, user):
        raise RuntimeError("LLM down")

    fake_llm = MagicMock()
    fake_llm.complete = failing_complete

    with patch(f"{MODULE}.supabase_metadata_tool.list_files", return_value=_files()), patch(
        f"{MODULE}.supabase_metadata_tool.list_symbols", return_value=_symbols()
    ), patch(f"{MODULE}.build_llm_client", return_value=fake_llm), patch(
        f"{MODULE}._persist_analysis_task", return_value={"id": "fallback-task"}
    ), patch(f"{MODULE}.settings") as settings_mock:
        settings_mock.agent_max_retries = 0
        result = await build_analysis_plan({"scan_id": scan_id})

    assert result["status"] == "planned"
    assert len(result["analysis_tasks"]) == len(AGENT_NAMES)
    assert {t["agent_name"] for t in result["analysis_tasks"]} == set(AGENT_NAMES)
