# backend/tests/test_load_scan_context.py
from unittest.mock import patch

import pytest

from app.workflows.analysis.nodes.load_scan_context import load_scan_context

MODULE = "app.workflows.analysis.nodes.load_scan_context"


@pytest.mark.asyncio
async def test_returns_context_loaded_when_scan_exists():
    scan = {
        "id": "scan-1",
        "repo_full_name": "owner/repo",
        "default_branch": "main",
        "commit_sha": "abc123",
        "status": "parsed",
    }
    repo_stats = {"total_supported_files": 10, "symbol_count": 50, "language_breakdown": {"python": 10}}

    with patch(f"{MODULE}.supabase_metadata_tool.get_scan", return_value=scan), patch(
        f"{MODULE}.supabase_metadata_tool.get_repo_stats", return_value=repo_stats
    ):
        result = await load_scan_context({"scan_id": "scan-1"})

    assert result["status"] == "context_loaded"
    assert result["repo_context"]["repo_full_name"] == "owner/repo"
    assert result["repo_context"]["total_symbols"] == 50


@pytest.mark.asyncio
async def test_returns_failed_when_scan_missing():
    with patch(f"{MODULE}.supabase_metadata_tool.get_scan", return_value=None):
        result = await load_scan_context({"scan_id": "missing"})

    assert result["status"] == "context_load_failed"
    assert result["errors"]


@pytest.mark.asyncio
async def test_handles_missing_repo_stats_gracefully():
    scan = {
        "id": "scan-1",
        "repo_full_name": "owner/repo",
        "default_branch": "main",
        "commit_sha": None,
        "status": "parsed",
    }
    with patch(f"{MODULE}.supabase_metadata_tool.get_scan", return_value=scan), patch(
        f"{MODULE}.supabase_metadata_tool.get_repo_stats", return_value=None
    ):
        result = await load_scan_context({"scan_id": "scan-1"})

    assert result["status"] == "context_loaded"
    assert result["repo_context"]["total_files"] == 0
