# backend/app/workflows/analysis/agents/agent_factory.py
import asyncio
import json
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.agent_output import AgentOutputList
from app.services.openrouter_client import build_llm_client
from app.workflows.analysis.tools import neo4j_graph_tool, supabase_metadata_tool

AGENT_PROMPTS = {
    "security": (
        "You are the Security specialist agent in a code quality analysis "
        "system. Review the provided code context for security "
        "vulnerabilities (injection, auth flaws, secrets, unsafe "
        "deserialization, etc.)."
    ),
    "performance": (
        "You are the Performance specialist agent. Review the provided "
        "code context for performance issues (N+1 queries, unbounded "
        "loops, blocking I/O, inefficient algorithms)."
    ),
    "complexity": (
        "You are the Complexity specialist agent. Review the provided code "
        "context (including symbol metadata such as line ranges) for "
        "excessive complexity, deep nesting, and poor structure. You do not "
        "have deterministic branch/nesting counts — judge complexity from "
        "the code and metadata given."
    ),
    "duplication": (
        "You are the Duplication specialist agent. Review the provided "
        "code context for duplicated or near-duplicated logic across "
        "files/symbols."
    ),
    "reliability": (
        "You are the Reliability specialist agent. Review the provided "
        "code context for error-handling gaps, unhandled edge cases, and "
        "reliability risks."
    ),
}

RESPONSE_FORMAT_INSTRUCTIONS = (
    "Respond with ONLY a JSON array of finding objects (no prose, no "
    "markdown fences). Each object must have: title, description, "
    "severity (one of extreme/high/medium/low), confidence (0.0-1.0), "
    "file_path, symbol_name, start_line, end_line, evidence (list of "
    "strings), recommendation."
)


def _gather_context(scan_id: str, task: dict) -> dict:
    file_ids = task.get("target_file_ids") or []
    symbol_ids = task.get("target_symbol_ids") or []

    chunks = supabase_metadata_tool.list_chunks(
        scan_id, file_ids=file_ids or None, limit=settings.max_agent_context_chunks
    )
    symbol_context = [supabase_metadata_tool.get_symbol_context(sid) for sid in symbol_ids[:20]]
    related: list[dict] = []
    for sid in symbol_ids[:5]:
        related.extend(neo4j_graph_tool.get_symbol_neighbors(scan_id, sid))

    return {
        "objective": task["objective"],
        "chunks": [
            {"file_path": c["file_path"], "symbol_name": c.get("symbol_name"), "content": c["content"]}
            for c in chunks
        ],
        "symbols": [s for s in symbol_context if s is not None],
        "related_symbols": related,
    }


def _mark_task_running(task_id: str) -> None:
    from app.db.supabase_client import get_supabase_client

    client = get_supabase_client()
    client.table("analysis_tasks").update(
        {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", task_id).execute()


def _mark_task_completed(task_id: str) -> None:
    from app.db.supabase_client import get_supabase_client

    client = get_supabase_client()
    client.table("analysis_tasks").update(
        {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", task_id).execute()


def _mark_task_failed(task_id: str, error_message: str | None) -> None:
    from app.db.supabase_client import get_supabase_client

    client = get_supabase_client()
    client.table("analysis_tasks").update(
        {
            "status": "failed",
            "error_message": error_message,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", task_id).execute()


def _record_agent_run(
    scan_id: str,
    agent_name: str,
    task: dict,
    status: str,
    error_message: str | None,
    model_provider: str | None = None,
    model_name: str | None = None,
    usage: dict | None = None,
    findings_count: int | None = None,
) -> None:
    from app.db.supabase_client import get_supabase_client

    usage = usage or {}
    if status == "completed":
        output_summary = {"findings_count": findings_count or 0}
    elif error_message:
        output_summary = {"error": error_message}
    else:
        output_summary = None

    client = get_supabase_client()
    client.table("agent_runs").insert(
        {
            "scan_id": str(scan_id),
            "agent_name": agent_name,
            "analysis_task_id": task["task_id"],
            "status": status,
            "model_provider": model_provider,
            "model_name": model_name,
            "input_task": {"objective": task.get("objective")},
            "output_summary": output_summary,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "error_message": error_message,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()


def _log_agent_failed_event(scan_id: str, agent_name: str, error_message: str | None) -> None:
    from app.services import scan_event_service

    scan_event_service.create_event(
        scan_id, "agent_failed", f"{agent_name} agent failed.", {"error_message": error_message}
    )


async def run_agent(agent_name: str, worker_input: dict) -> dict:
    """Shared implementation for all 5 specialist agent nodes. Each thin
    per-agent module (security_agent.py etc.) calls this with its own name
    so analysis_tasks/agent_runs rows are attributed correctly."""
    scan_id = worker_input["scan_id"]
    task = worker_input["task"]
    last_error: str | None = None
    client = None

    try:
        await asyncio.to_thread(_mark_task_running, task["task_id"])

        context = await asyncio.to_thread(_gather_context, scan_id, task)
        system_prompt = f"{AGENT_PROMPTS[agent_name]}\n\n{RESPONSE_FORMAT_INSTRUCTIONS}"
        user_prompt = json.dumps(context)

        client = build_llm_client(agent_name)

        for _ in range(settings.agent_max_retries + 1):
            try:
                raw = await client.complete(system=system_prompt, user=user_prompt)
                parsed = json.loads(raw)
                validated = AgentOutputList(findings=parsed if isinstance(parsed, list) else [])
                findings = [f.model_dump() for f in validated.findings][: settings.max_findings_per_agent]
                for finding in findings:
                    finding["agent"] = agent_name

                await asyncio.to_thread(
                    _record_agent_run,
                    scan_id,
                    agent_name,
                    task,
                    "completed",
                    None,
                    model_provider="openrouter",
                    model_name=settings.agent_llm_model,
                    usage=client.last_usage,
                    findings_count=len(findings),
                )
                await asyncio.to_thread(_mark_task_completed, task["task_id"])
                return {"raw_findings": findings}
            except Exception as exc:  # noqa: BLE001 - any failure triggers a retry then a graceful skip
                last_error = str(exc)
                user_prompt = json.dumps(context) + "\n\nReturn ONLY a valid JSON array, nothing else."
                continue
    except Exception as exc:  # noqa: BLE001 - setup/context failures (e.g. a transient
        # Supabase/Neo4j read) must not escape run_agent: LangGraph aborts the *entire*
        # Send fan-out step on any unhandled exception from a single dispatched node,
        # which would silently kill all 5 concurrent agents rather than just this one.
        last_error = str(exc)

    await asyncio.to_thread(
        _record_agent_run,
        scan_id,
        agent_name,
        task,
        "failed",
        last_error,
        model_provider="openrouter",
        model_name=settings.agent_llm_model,
        usage=getattr(client, "last_usage", None),
    )
    await asyncio.to_thread(_mark_task_failed, task["task_id"], last_error)
    await asyncio.to_thread(_log_agent_failed_event, scan_id, agent_name, last_error)
    return {"raw_findings": []}
