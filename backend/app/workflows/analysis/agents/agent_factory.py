# backend/app/workflows/analysis/agents/agent_factory.py
import asyncio
import json
from datetime import datetime, timezone

from app.core.config import settings
from app.core.errors import AppError
from app.schemas.agent_output import AgentOutputList
from app.services.openrouter_client import (
    AGENT_KEY_ATTR,
    RATE_LIMIT_BACKOFF_SECONDS,
    OpenRouterClient,
)
from app.workflows.analysis.tools import neo4j_graph_tool, supabase_metadata_tool

# Optional second key per specialist agent (supervisor/chatbot excluded — no
# fallback requested for those). Tried only once the primary key exhausts its
# own rate-limit retries on both models.
FALLBACK_KEY_ATTR = {
    "security": "openrouter_api_key_security_fallback",
    "performance": "openrouter_api_key_performance_fallback",
    "complexity": "openrouter_api_key_complexity_fallback",
    "duplication": "openrouter_api_key_duplication_fallback",
    "reliability": "openrouter_api_key_reliability_fallback",
}

# _gather_context's Supabase/Neo4j reads run inside the same shared semaphore
# turn as the LLM call but aren't HTTP-retried by openrouter_client, so a
# transient WinError 10035 there needs its own small retry.
CONTEXT_READ_RETRIES = 2
CONTEXT_READ_RETRY_DELAY_SECONDS = 1

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

# All 5 agents fire concurrently via LangGraph's Send fan-out. Bursting 5
# simultaneous httpx.AsyncClient connections on Windows' default
# ProactorEventLoop reliably trips WinError 10035 (WSAEWOULDBLOCK) when a
# wait_for timeout races a live overlapped socket op. Capping concurrent
# OpenRouter calls keeps the burst small enough to avoid it; SimpleWorker
# processes one job at a time on Windows so a module-level semaphore is safe.
AGENT_LLM_CONCURRENCY_LIMIT = 2
_llm_semaphore = asyncio.Semaphore(AGENT_LLM_CONCURRENCY_LIMIT)


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


async def _run_with_retry(func, *args):
    """Run a sync function in a thread, retrying on transient errors (e.g.
    WinError 10035 from concurrent threads sharing the sync Supabase/Neo4j
    clients — see run_agent's docstring). Not HTTP-specific; any exception
    is treated as transient here since these are Supabase/Neo4j reads/writes,
    not LLM calls with their own rate-limit semantics."""
    last_exc: Exception | None = None
    for attempt in range(CONTEXT_READ_RETRIES + 1):
        try:
            return await asyncio.to_thread(func, *args)
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_exc = exc
            if attempt < CONTEXT_READ_RETRIES:
                await asyncio.sleep(CONTEXT_READ_RETRY_DELAY_SECONDS)
                continue
            raise
    raise last_exc  # pragma: no cover - unreachable, loop always returns or raises


def _llm_candidates(agent_name: str) -> list[tuple[str, str]]:
    """Ordered (api_key, model) candidates to try for this agent: primary key
    with the primary model, then the primary key with the fallback model,
    then (if a fallback key is configured) the same two models on that key."""
    primary_key = getattr(settings, AGENT_KEY_ATTR[agent_name]) or ""
    fallback_attr = FALLBACK_KEY_ATTR.get(agent_name)
    fallback_key = (getattr(settings, fallback_attr) or "") if fallback_attr else ""

    models = [settings.agent_llm_model, settings.agent_llm_model_fallback]
    keys = [k for k in (primary_key, fallback_key) if k]
    if not keys:
        keys = [""]  # still yield one candidate so the "not configured" error surfaces
    return [(key, model) for key in keys for model in models]


async def run_agent(agent_name: str, worker_input: dict) -> dict:
    """Shared implementation for all 5 specialist agent nodes. Each thin
    per-agent module (security_agent.py etc.) calls this with its own name
    so analysis_tasks/agent_runs rows are attributed correctly.

    The whole turn (Supabase/Neo4j reads, the LLM call, and bookkeeping
    writes) runs under a shared semaphore: all 5 agents fire concurrently via
    LangGraph's Send fan-out, and bursting 5 agents' worth of unthrottled
    concurrent I/O (async OpenRouter connections *and* threaded calls into
    the single shared synchronous Supabase client) reliably trips WinError
    10035 (WSAEWOULDBLOCK) on Windows' default ProactorEventLoop. Capping how
    many agents are ever mid-turn at once keeps the burst small enough to
    avoid it; SimpleWorker processes one job at a time on Windows so a
    module-level semaphore is safe.
    """
    scan_id = worker_input["scan_id"]
    task = worker_input["task"]
    last_error: str | None = None
    client: OpenRouterClient | None = None

    async with _llm_semaphore:
        try:
            await _run_with_retry(_mark_task_running, task["task_id"])

            context = await _run_with_retry(_gather_context, scan_id, task)
            system_prompt = f"{AGENT_PROMPTS[agent_name]}\n\n{RESPONSE_FORMAT_INSTRUCTIONS}"
            base_user_prompt = json.dumps(context)
            user_prompt = base_user_prompt

            for key, model in _llm_candidates(agent_name):
                client = OpenRouterClient(
                    api_key=key, model=model, timeout_seconds=settings.agent_timeout_seconds
                )
                user_prompt = base_user_prompt

                for attempt in range(settings.agent_max_retries + 1):
                    try:
                        raw = await client.complete(system=system_prompt, user=user_prompt)
                        parsed = json.loads(raw)
                        validated = AgentOutputList(findings=parsed if isinstance(parsed, list) else [])
                        findings = [
                            f.model_dump() for f in validated.findings
                        ][: settings.max_findings_per_agent]
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
                            model_name=model,
                            usage=client.last_usage,
                            findings_count=len(findings),
                        )
                        await asyncio.to_thread(_mark_task_completed, task["task_id"])
                        return {"raw_findings": findings}
                    except AppError as exc:
                        last_error = str(exc)
                        if exc.error_code == "LLM_RATE_LIMITED" and attempt < settings.agent_max_retries:
                            backoff = RATE_LIMIT_BACKOFF_SECONDS[
                                min(attempt, len(RATE_LIMIT_BACKOFF_SECONDS) - 1)
                            ]
                            await asyncio.sleep(backoff)
                            continue
                        # Non-rate-limit AppError, or retries exhausted on this
                        # candidate: stop retrying this (key, model) and move on.
                        break
                    except Exception as exc:  # noqa: BLE001 - malformed JSON etc.; retry
                        # the same candidate with a stricter prompt before giving up on it.
                        last_error = str(exc)
                        user_prompt = base_user_prompt + "\n\nReturn ONLY a valid JSON array, nothing else."
                        continue
        except Exception as exc:  # noqa: BLE001 - setup/context failures (e.g. a transient
            # Supabase/Neo4j read) must not escape run_agent: LangGraph aborts the *entire*
            # Send fan-out step on any unhandled exception from a single dispatched node,
            # which would silently kill all 5 concurrent agents rather than just this one.
            last_error = str(exc)

        try:
            # Bookkeeping only at this point (the agent has already failed on every
            # candidate). A failure here must not escape run_agent either, for the
            # same reason as above.
            await asyncio.to_thread(
                _record_agent_run,
                scan_id,
                agent_name,
                task,
                "failed",
                last_error,
                model_provider="openrouter",
                model_name=getattr(client, "_model", settings.agent_llm_model),
                usage=getattr(client, "last_usage", None),
            )
            await asyncio.to_thread(_mark_task_failed, task["task_id"], last_error)
            await asyncio.to_thread(_log_agent_failed_event, scan_id, agent_name, last_error)
        except Exception:  # noqa: BLE001 - see comment above
            pass
        return {"raw_findings": []}
