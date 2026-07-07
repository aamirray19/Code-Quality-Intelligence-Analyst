import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.core.errors import AppError
from app.workflows.analysis.graph import run_analysis
from app.workflows.report.pipeline import run_report_generation
from app.schemas.chunks import CodeChunk
from app.schemas.jobs import RepoScanJob
from app.schemas.symbols import CodeSymbol
from app.services import (
    chunk_builder_service,
    code_chunk_service,
    code_symbol_service,
    embedding_service,
    neo4j_graph_service,
    qdrant_index_service,
    repo_clone_service,
    repo_stats_service,
    scan_event_service,
    scan_file_service,
    scan_service,
    tree_sitter_parser_service,
    workspace_service,
)
from app.services.file_discovery_service import discover_files
from app.services.symbol_extraction_service import extract_symbols

logger = logging.getLogger(__name__)


def process_repo_scan(job_payload: dict) -> None:
    """Phase 2 orchestration entrypoint, called by the RQ worker for jobs on
    `repo_scan_queue`. Drives the scan through cloning, file discovery,
    Tree-sitter parsing, symbol extraction, chunking, and Qdrant/Neo4j
    indexing, updating scan status/events in Supabase throughout.

    Does not return the final report — Phase 3 picks up from `status=parsed`.
    """
    try:
        job = RepoScanJob.model_validate(job_payload)
    except Exception as exc:
        raise AppError("INVALID_JOB_PAYLOAD", f"Invalid repo scan job payload: {exc}", 400) from exc

    scan_id = job.scan_id

    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", f"Scan {scan_id} not found.", 404)

    if scan.status == "parsed":
        # Scan already completed Phase 2 (e.g. a duplicate/stale job was
        # re-queued). This is not a failure, so it must not go through
        # _mark_failed and overwrite a successful scan's status — just skip
        # reprocessing and record why.
        logger.info("Scan %s is already parsed; skipping duplicate job.", scan_id)
        scan_event_service.create_event(
            scan_id, "duplicate_job_skipped", "Scan already parsed; skipping reprocessing."
        )
        return

    retryable_statuses = {
        "queued",
        "cloning",
        "discovering_files",
        "parsing",
        "chunking",
        "storing_indexes",
        "failed",
    }
    if scan.status not in retryable_statuses:
        logger.warning(
            "Scan %s has non-retryable status '%s'; processing anyway.", scan_id, scan.status
        )

    try:
        _run_scan(job, scan)
    except AppError as exc:
        _mark_failed(scan_id, exc.error_code, exc.message)
        raise
    except Exception as exc:  # noqa: BLE001 - last-resort guard so the worker never crashes silently
        _mark_failed(scan_id, "INTERNAL_WORKER_ERROR", str(exc))
        raise
    finally:
        workspace_service.cleanup_workspace(scan_id)


def _mark_failed(scan_id, error_code: str, message: str) -> None:
    try:
        scan_service.update_scan(
            scan_id,
            status="failed",
            error_code=error_code,
            error_message=message,
            failed_at=datetime.now(timezone.utc),
        )
        scan_event_service.create_event(
            scan_id, "worker_failed", message, {"error_code": error_code}
        )
    except Exception:  # noqa: BLE001 - failure reporting must not itself raise
        logger.exception("Failed to record scan failure for scan_id=%s", scan_id)


def _run_scan(job: RepoScanJob, scan) -> None:
    scan_id = job.scan_id
    repo = job.repo

    scan_service.update_scan(
        scan_id, status="cloning", phase="phase_2", started_at=datetime.now(timezone.utc)
    )
    scan_event_service.create_event(scan_id, "worker_started", "Phase 2 worker started.")

    repo_path = workspace_service.create_workspace(scan_id)

    cloned = repo_clone_service.clone_repository(scan_id, repo, repo_path)
    scan_service.update_scan(scan_id, commit_sha=cloned.commit_sha, status="discovering_files")
    scan_event_service.create_event(
        scan_id, "clone_completed", "Repository clone completed.", {"commit_sha": cloned.commit_sha}
    )

    discovered = discover_files(scan_id, repo_path)
    stored_files = scan_file_service.store_discovered_files(discovered)
    absolute_path_by_relative_path = {d.relative_path: d.absolute_path for d in discovered}

    supported_files = [f for f in stored_files if f.is_supported]
    scan_service.update_scan(scan_id, status="parsing")
    scan_event_service.create_event(
        scan_id,
        "parsing_started",
        "Tree-sitter parsing started.",
        {"supported_files": len(supported_files)},
    )

    all_symbols: list[CodeSymbol] = []
    sources_by_file_id: dict = {}
    parsed_ok_by_file_id: dict = {}

    for file_record in stored_files:
        if not file_record.is_supported:
            continue

        absolute_path = absolute_path_by_relative_path[file_record.relative_path]
        parsed = tree_sitter_parser_service.parse_file(
            absolute_path, file_record.language, file_record.extension or ""
        )

        if not parsed.ok:
            scan_file_service.update_file_parse_status(file_record.id, "failed", parsed.error_message)
            code_symbol_service.store_parse_error(
                scan_id,
                file_record.id,
                parsed.error_code or "TREE_SITTER_PARSE_FAILED",
                parsed.error_message or "unknown error",
            )
            continue

        try:
            symbols = extract_symbols(parsed, scan_id, file_record.id, file_record.relative_path)
        except Exception as exc:  # noqa: BLE001 - a single file must not fail the whole scan
            scan_file_service.update_file_parse_status(file_record.id, "failed", str(exc))
            code_symbol_service.store_parse_error(
                scan_id, file_record.id, "SYMBOL_EXTRACTION_FAILED", str(exc)
            )
            continue

        all_symbols.extend(symbols)
        sources_by_file_id[file_record.id] = parsed.source
        parsed_ok_by_file_id[file_record.id] = True
        scan_file_service.update_file_parse_status(file_record.id, "parsed")

    scan_service.update_scan(scan_id, status="chunking")
    local_id_to_real_id = code_symbol_service.store_symbols(all_symbols)

    symbols_by_file_id: dict = {}
    for symbol in all_symbols:
        symbols_by_file_id.setdefault(symbol.file_id, []).append(symbol)

    all_chunks: list[CodeChunk] = []
    for file_record in supported_files:
        file_symbols = symbols_by_file_id.get(file_record.id, [])
        source = sources_by_file_id.get(file_record.id, "")
        parsed_ok = parsed_ok_by_file_id.get(file_record.id, False)
        try:
            chunks = chunk_builder_service.build_chunks(
                scan_id=scan_id,
                file_id=file_record.id,
                file_path=file_record.relative_path,
                language=file_record.language,
                symbols=file_symbols,
                symbol_id_map=local_id_to_real_id,
                source=source,
                parsed_ok=parsed_ok,
            )
        except Exception as exc:  # noqa: BLE001 - a single file must not fail the whole scan
            code_symbol_service.store_parse_error(
                scan_id, file_record.id, "CHUNKING_FAILED", str(exc)
            )
            continue
        all_chunks.extend(chunks)

    chunk_id_pairs = code_chunk_service.store_chunks_with_ids(all_chunks)

    scan_service.update_scan(scan_id, status="storing_indexes")
    scan_event_service.create_event(
        scan_id, "storing_indexes_started", "Storing vector and graph indexes.", {"chunks": len(chunk_id_pairs)}
    )

    qdrant_result = None
    neo4j_result = None

    if chunk_id_pairs:
        chunks_only = [pair[0] for pair in chunk_id_pairs]
        chunk_ids_only = [str(pair[1]) for pair in chunk_id_pairs]

        stored_symbol_rows = _fetch_stored_symbol_rows(scan_id)
        stored_file_rows = [
            {"id": str(f.id), "relative_path": f.relative_path, "language": f.language}
            for f in stored_files
        ]

        with ThreadPoolExecutor(max_workers=2) as executor:
            embed_future = executor.submit(
                _embed_and_store_qdrant, scan_id, chunks_only, chunk_ids_only, job, cloned
            )
            neo4j_future = executor.submit(
                neo4j_graph_service.upsert_code_graph,
                scan_id,
                repo.full_name,
                repo.html_url,
                cloned.branch,
                cloned.commit_sha,
                stored_file_rows,
                stored_symbol_rows,
            )
            qdrant_result = embed_future.result()
            neo4j_result = neo4j_future.result()

        code_chunk_service.mark_chunks_indexed(
            [pair[1] for pair in chunk_id_pairs], qdrant=True, neo4j=True
        )

    repo_stats_service.compute_repo_stats(
        scan_id,
        qdrant_points_count=qdrant_result.points_upserted if qdrant_result else 0,
        neo4j_nodes_count=neo4j_result.nodes_upserted if neo4j_result else 0,
        neo4j_relationships_count=neo4j_result.relationships_upserted if neo4j_result else 0,
    )

    scan_service.update_scan(
        scan_id, status="parsed", phase="phase_2_complete", parsed_at=datetime.now(timezone.utc)
    )
    scan_event_service.create_event(scan_id, "scan_parsed", "Scan parsed successfully.")

    # Phase 3: same-worker trigger (Option A) — run the analysis graph
    # immediately after Phase 2 completes. A Phase 3 failure must not
    # re-raise and undo the already-successful Phase 2 result; the graph's
    # own fail_analysis node records the failure in Supabase.
    try:
        asyncio.run(run_analysis(scan_id))
    except Exception:  # noqa: BLE001 - Phase 3 failures are self-contained in the graph
        logger.exception("Phase 3 analysis failed for scan_id=%s", scan_id)
    else:
        # Phase 4: Report generation — runs only if Phase 3 succeeded.
        # A Phase 4 failure must not affect Phase 3's already-successful status;
        # run_report_generation swallows its own exceptions after marking
        # status="report_failed" in Supabase.
        try:
            asyncio.run(run_report_generation(scan_id))
        except Exception:  # noqa: BLE001 - Belt-and-suspenders guard; pipeline should swallow
            logger.exception("Phase 4 report generation failed for scan_id=%s", scan_id)


def _embed_and_store_qdrant(scan_id, chunks, chunk_ids, job, cloned):
    embedded = embedding_service.embed_chunks(chunks, chunk_ids)
    return qdrant_index_service.upsert_chunks(
        scan_id, embedded, job.repo.full_name, cloned.branch, cloned.commit_sha
    )


def _fetch_stored_symbol_rows(scan_id) -> list[dict]:
    from app.db.supabase_client import get_supabase_client

    client = get_supabase_client()
    result = client.table("code_symbols").select("*").eq("scan_id", str(scan_id)).execute()
    return result.data
