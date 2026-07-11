# backend/app/workflows/analysis/nodes/build_analysis_plan.py
import asyncio
import json

from app.core.config import settings
from app.schemas.analysis_task import AnalysisTaskRecord
from app.services.google_ai_client import build_llm_client
from app.workflows.analysis.state import AnalysisState, AnalysisTask
from app.workflows.analysis.tools import supabase_metadata_tool

AGENT_NAMES = ["security", "performance", "complexity", "duplication", "reliability"]

SUPERVISOR_SYSTEM_PROMPT = (
    "You are the planning supervisor for a code quality analysis system. "
    "You will be given a structural summary of a repository (file list, top "
    "symbols by size) and must produce a JSON array of analysis tasks, one "
    "or more per agent from this fixed list: security, performance, "
    "complexity, duplication, reliability. Each task must have: "
    "agent_name, objective (string), priority (1-3), target_file_ids (list "
    "of file id strings taken from the input), target_symbol_ids (list of "
    "symbol id strings taken from the input). Only use ids that appear in "
    "the input. Respond with ONLY a JSON array, no prose, no markdown fences."
)


def _build_structural_summary(scan_id: str) -> dict:
    files = supabase_metadata_tool.list_files(scan_id)
    symbols = supabase_metadata_tool.list_symbols(scan_id, limit=500)
    return {
        "files": [
            {"file_id": f["id"], "path": f["relative_path"], "language": f.get("language")}
            for f in files
        ],
        "top_symbols": [
            {
                "symbol_id": s["id"],
                "file_id": s["file_id"],
                "name": s["symbol_name"],
                "type": s["symbol_type"],
                "loc": s["end_line"] - s["start_line"],
            }
            for s in symbols
        ],
    }


def _deterministic_fallback_plan(summary: dict) -> list[AnalysisTask]:
    """Heuristic scoping fallback (phase3.md 10.3) used only if the
    supervisor LLM call fails after retries, so a single LLM outage never
    fails the entire analysis."""
    all_file_ids = [f["file_id"] for f in summary["files"]]
    all_symbol_ids = [s["symbol_id"] for s in summary["top_symbols"]]
    return [
        {
            "task_id": "",
            "agent_name": agent_name,
            "objective": f"Analyze the full scoped repository for {agent_name} issues.",
            "priority": 1,
            "target_file_ids": all_file_ids,
            "target_chunk_ids": [],
            "target_symbol_ids": all_symbol_ids,
        }
        for agent_name in AGENT_NAMES
    ]


async def _call_supervisor_llm(summary: dict) -> list[AnalysisTask] | None:
    client = build_llm_client("supervisor")
    user_prompt = json.dumps(summary)

    for _ in range(settings.agent_max_retries + 1):
        try:
            raw = await client.complete(system=SUPERVISOR_SYSTEM_PROMPT, user=user_prompt)
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                continue
            tasks = [
                {
                    "task_id": "",
                    "agent_name": item["agent_name"],
                    "objective": item["objective"],
                    "priority": int(item.get("priority", 1)),
                    "target_file_ids": item.get("target_file_ids", []),
                    "target_chunk_ids": item.get("target_chunk_ids", []),
                    "target_symbol_ids": item.get("target_symbol_ids", []),
                }
                for item in parsed
                if item.get("agent_name") in AGENT_NAMES
            ]
            if tasks:
                return tasks
        except Exception:  # noqa: BLE001 - any LLM/JSON failure triggers a retry, then fallback
            continue
    return None


def _persist_analysis_task(record: AnalysisTaskRecord) -> dict:
    from app.db.supabase_client import get_supabase_client

    client = get_supabase_client()
    payload = {
        "scan_id": str(record.scan_id),
        "agent_name": record.agent_name,
        "objective": record.objective,
        "priority": record.priority,
        "target_file_ids": record.target_file_ids,
        "target_chunk_ids": record.target_chunk_ids,
        "target_symbol_ids": record.target_symbol_ids,
        "status": "pending",
    }
    result = client.table("analysis_tasks").insert(payload).execute()
    return result.data[0]


async def build_analysis_plan(state: AnalysisState) -> dict:
    scan_id = state["scan_id"]
    summary = await asyncio.to_thread(_build_structural_summary, scan_id)

    tasks = await _call_supervisor_llm(summary)
    if not tasks:
        tasks = _deterministic_fallback_plan(summary)

    persisted_tasks: list[AnalysisTask] = []
    for task in tasks:
        record = AnalysisTaskRecord(
            scan_id=scan_id,
            agent_name=task["agent_name"],
            objective=task["objective"],
            priority=task["priority"],
            target_file_ids=task["target_file_ids"],
            target_chunk_ids=task["target_chunk_ids"],
            target_symbol_ids=task["target_symbol_ids"],
        )
        row = await asyncio.to_thread(_persist_analysis_task, record)
        persisted_tasks.append({**task, "task_id": row["id"]})

    return {"analysis_tasks": persisted_tasks, "status": "planned"}
