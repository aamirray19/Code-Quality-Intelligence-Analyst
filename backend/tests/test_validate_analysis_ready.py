from unittest.mock import MagicMock, patch

import pytest

from app.workflows.analysis.nodes.validate_analysis_ready import validate_analysis_ready

MODULE = "app.workflows.analysis.nodes.validate_analysis_ready"


def _patches(scan, files, chunks, qdrant_count, neo4j_found):
    count_result = MagicMock()
    count_result.count = qdrant_count
    qdrant_client = MagicMock()
    qdrant_client.count.return_value = count_result

    neo4j_driver = MagicMock()
    session = neo4j_driver.session.return_value.__enter__.return_value
    session.run.return_value.single.return_value = {"s": 1} if neo4j_found else None

    return (
        patch(f"{MODULE}.supabase_metadata_tool.get_scan", return_value=scan),
        patch(f"{MODULE}.supabase_metadata_tool.list_files", return_value=files),
        patch(f"{MODULE}.supabase_metadata_tool.list_chunks", return_value=chunks),
        patch(f"{MODULE}.get_qdrant_client", return_value=qdrant_client),
        patch(f"{MODULE}.get_neo4j_driver", return_value=neo4j_driver),
    )


@pytest.mark.asyncio
async def test_ready_when_all_preconditions_met():
    scan = {"id": "s1", "status": "parsed"}
    patches = _patches(scan, [{"id": "f1"}], [{"id": "c1"}], qdrant_count=5, neo4j_found=True)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = await validate_analysis_ready({"scan_id": "s1"})
    assert result == {"status": "ready"}


@pytest.mark.asyncio
async def test_skipped_when_already_analyzed():
    scan = {"id": "s1", "status": "analyzed"}
    with patch(f"{MODULE}.supabase_metadata_tool.get_scan", return_value=scan):
        result = await validate_analysis_ready({"scan_id": "s1"})
    assert result == {"status": "skipped"}


@pytest.mark.asyncio
async def test_not_ready_when_scan_not_parsed():
    scan = {"id": "s1", "status": "cloning"}
    with patch(f"{MODULE}.supabase_metadata_tool.get_scan", return_value=scan):
        result = await validate_analysis_ready({"scan_id": "s1"})
    assert result["status"] == "not_ready"
    assert result["errors"] == ["SCAN_NOT_PARSED"]


@pytest.mark.asyncio
async def test_not_ready_when_missing_chunks_but_symbols_absent_is_fine():
    scan = {"id": "s1", "status": "parsed"}
    patches = _patches(scan, [{"id": "f1"}], [], qdrant_count=5, neo4j_found=True)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = await validate_analysis_ready({"scan_id": "s1"})
    assert result["errors"] == ["MISSING_CODE_CHUNKS"]


@pytest.mark.asyncio
async def test_not_ready_when_missing_neo4j_scan_node():
    scan = {"id": "s1", "status": "parsed"}
    patches = _patches(scan, [{"id": "f1"}], [{"id": "c1"}], qdrant_count=5, neo4j_found=False)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = await validate_analysis_ready({"scan_id": "s1"})
    assert result["errors"] == ["MISSING_NEO4J_GRAPH"]
