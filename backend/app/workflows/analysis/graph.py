# backend/app/workflows/analysis/graph.py
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.core.config import settings
from app.workflows.analysis.agents.agent_factory import reset_llm_semaphore
from app.workflows.analysis.agents.complexity_agent import complexity_agent
from app.workflows.analysis.agents.duplication_agent import duplication_agent
from app.workflows.analysis.agents.performance_agent import performance_agent
from app.workflows.analysis.agents.reliability_agent import reliability_agent
from app.workflows.analysis.agents.security_agent import security_agent
from app.workflows.analysis.nodes.build_analysis_plan import build_analysis_plan
from app.workflows.analysis.nodes.deduplicate_findings import deduplicate_findings
from app.workflows.analysis.nodes.fail_analysis import fail_analysis
from app.workflows.analysis.nodes.load_scan_context import load_scan_context
from app.workflows.analysis.nodes.mark_scan_analyzed import mark_scan_analyzed
from app.workflows.analysis.nodes.normalize_findings import normalize_findings
from app.workflows.analysis.nodes.persist_findings import persist_findings
from app.workflows.analysis.nodes.rank_findings import rank_findings
from app.workflows.analysis.nodes.validate_analysis_ready import validate_analysis_ready
from app.workflows.analysis.state import AnalysisState

AGENT_NODES = {
    "security_agent": security_agent,
    "performance_agent": performance_agent,
    "complexity_agent": complexity_agent,
    "duplication_agent": duplication_agent,
    "reliability_agent": reliability_agent,
}


def route_after_context_load(state: AnalysisState) -> str:
    return "validate_analysis_ready" if state["status"] == "context_loaded" else "fail_analysis"


def route_after_validation(state: AnalysisState) -> str:
    if state["status"] == "ready":
        return "build_analysis_plan"
    if state["status"] == "skipped":
        return END
    return "fail_analysis"


def dispatch_agent_workers(state: AnalysisState) -> list[Send]:
    """Fan-out routing function (not a graph node — 2026-07-06 decision).
    Returns one Send per planned task so LangGraph can run all 5 agent
    nodes concurrently."""
    return [
        Send(f"{task['agent_name']}_agent", {"task": task, "scan_id": state["scan_id"]})
        for task in state["analysis_tasks"]
    ]


def build_graph() -> StateGraph:
    graph = StateGraph(AnalysisState)

    graph.add_node("load_scan_context", load_scan_context)
    graph.add_node("validate_analysis_ready", validate_analysis_ready)
    graph.add_node("fail_analysis", fail_analysis)
    graph.add_node("build_analysis_plan", build_analysis_plan)
    for node_name, node_fn in AGENT_NODES.items():
        graph.add_node(node_name, node_fn)
    graph.add_node("normalize_findings", normalize_findings)
    graph.add_node("deduplicate_findings", deduplicate_findings)
    graph.add_node("rank_findings", rank_findings)
    graph.add_node("persist_findings", persist_findings)
    graph.add_node("mark_scan_analyzed", mark_scan_analyzed)

    graph.set_entry_point("load_scan_context")
    graph.add_conditional_edges(
        "load_scan_context", route_after_context_load, ["validate_analysis_ready", "fail_analysis"]
    )
    graph.add_conditional_edges(
        "validate_analysis_ready", route_after_validation, ["build_analysis_plan", "fail_analysis", END]
    )
    graph.add_conditional_edges("build_analysis_plan", dispatch_agent_workers, list(AGENT_NODES.keys()))

    for node_name in AGENT_NODES:
        graph.add_edge(node_name, "normalize_findings")
    graph.add_edge("normalize_findings", "deduplicate_findings")
    graph.add_edge("deduplicate_findings", "rank_findings")
    graph.add_edge("rank_findings", "persist_findings")
    graph.add_edge("persist_findings", "mark_scan_analyzed")
    graph.add_edge("mark_scan_analyzed", END)
    graph.add_edge("fail_analysis", END)

    return graph


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


async def run_analysis(scan_id) -> dict:
    """Single entrypoint for Phase 3, invoked by repo_scan_worker.py right
    after a scan is marked `parsed` (Option A same-worker trigger)."""
    # repo_scan_worker.py invokes this via a fresh asyncio.run() per scan, so
    # every call gets its own new event loop -- rebind the agent concurrency
    # semaphore to it before any agent touches it. See
    # agent_factory.reset_llm_semaphore for why this is required.
    reset_llm_semaphore()
    graph = get_compiled_graph()
    initial_state: AnalysisState = {"scan_id": str(scan_id), "raw_findings": [], "errors": []}
    return await graph.ainvoke(
        initial_state, config={"recursion_limit": settings.langgraph_recursion_limit}
    )
