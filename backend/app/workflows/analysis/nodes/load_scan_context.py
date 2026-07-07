# backend/app/workflows/analysis/nodes/load_scan_context.py
import asyncio

from app.workflows.analysis.state import AnalysisState, RepoContext
from app.workflows.analysis.tools import supabase_metadata_tool


async def load_scan_context(state: AnalysisState) -> dict:
    scan_id = state["scan_id"]
    scan = await asyncio.to_thread(supabase_metadata_tool.get_scan, scan_id)
    if scan is None:
        return {"status": "context_load_failed", "errors": [f"Scan {scan_id} not found."]}

    repo_stats = await asyncio.to_thread(supabase_metadata_tool.get_repo_stats, scan_id)

    repo_context: RepoContext = {
        "scan_id": scan_id,
        "repo_full_name": scan["repo_full_name"],
        "default_branch": scan["default_branch"],
        "commit_sha": scan.get("commit_sha"),
        "total_files": (repo_stats or {}).get("total_supported_files", 0),
        "total_symbols": (repo_stats or {}).get("symbol_count", 0),
        "language_breakdown": (repo_stats or {}).get("language_breakdown") or {},
    }
    return {"repo_context": repo_context, "status": "context_loaded"}
