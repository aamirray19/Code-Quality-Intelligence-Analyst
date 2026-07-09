from uuid import UUID

from fastapi import APIRouter, Query

from app.core.errors import AppError
from app.schemas.repos import RepoInfoResponse, ScanStatusRepoResponse
from app.schemas.scans import (
    CreateScanRequest,
    CreateScanResponse,
    ScanEventItem,
    ScanEventsResponse,
    ScanFileItem,
    ScanFilesResponse,
    ScanProgress,
    ScanStatusResponse,
)
from app.services import queue_service, scan_file_service, scan_service
from app.services.repo_validation_service import validate_repository

router = APIRouter()


def _compute_progress(scan_id: UUID) -> ScanProgress:
    client = scan_service.get_supabase_client()

    files_result = (
        client.table("scan_files")
        .select("parse_status", count="exact")
        .eq("scan_id", str(scan_id))
        .execute()
    )
    files = files_result.data
    files_discovered = files_result.count if files_result.count is not None else len(files)
    files_indexed = sum(1 for f in files if f["parse_status"] == "parsed")
    files_skipped = sum(1 for f in files if f["parse_status"] in ("skipped", "failed"))

    symbols_result = (
        client.table("code_symbols").select("id", count="exact").eq("scan_id", str(scan_id)).execute()
    )
    chunks_result = (
        client.table("code_chunks").select("id", count="exact").eq("scan_id", str(scan_id)).execute()
    )

    return ScanProgress(
        files_discovered=files_discovered,
        files_indexed=files_indexed,
        files_skipped=files_skipped,
        symbols_extracted=symbols_result.count or 0,
        chunks_created=chunks_result.count or 0,
    )


@router.post("/scans", status_code=201, response_model=CreateScanResponse)
def create_scan(request: CreateScanRequest) -> CreateScanResponse:
    repo = validate_repository(request.github_url)
    scan = scan_service.create_scan(repo, request.github_url)
    queue_service.enqueue_scan(scan, repo)

    return CreateScanResponse(
        success=True,
        scan_id=scan.id,
        status=scan.status,
        message="Repository is valid. Scan has been started.",
        repo=RepoInfoResponse(
            owner=repo.owner,
            name=repo.name,
            full_name=repo.full_name,
            branch=repo.branch,
            default_branch=repo.default_branch,
            clone_url=repo.clone_url,
            html_url=repo.html_url,
            size_kb=repo.size_kb,
            visibility=repo.visibility,
        ),
    )


@router.get("/scans/{scan_id}", response_model=ScanStatusResponse)
def get_scan_status(scan_id: UUID) -> ScanStatusResponse:
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", "Scan not found.", 404)

    progress = _compute_progress(scan_id) if scan.phase == "phase_2" or scan.status != "queued" else None

    return ScanStatusResponse(
        scan_id=scan.id,
        status=scan.status,
        phase=scan.phase,
        repo=ScanStatusRepoResponse(
            owner=scan.repo_owner,
            name=scan.repo_name,
            full_name=scan.repo_full_name,
            branch=scan.branch,
            html_url=scan.html_url,
            commit_sha=scan.commit_sha,
        ),
        progress=progress,
        created_at=scan.created_at,
        updated_at=scan.updated_at,
        error_message=scan.error_message,
    )


@router.get("/scans/{scan_id}/files", response_model=ScanFilesResponse)
def get_scan_files(
    scan_id: UUID,
    status: str | None = Query(default=None),
    language: str | None = Query(default=None),
    limit: int = Query(default=100, le=500, ge=1),
    offset: int = Query(default=0, ge=0),
) -> ScanFilesResponse:
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", "Scan not found.", 404)

    items, total = scan_file_service.list_scan_files(
        scan_id, status=status, language=language, limit=limit, offset=offset
    )

    return ScanFilesResponse(
        scan_id=scan_id,
        items=[
            ScanFileItem(
                file_id=f.id,
                relative_path=f.relative_path,
                language=f.language,
                extension=f.extension,
                size_bytes=f.size_bytes,
                line_count=f.line_count,
                parse_status=f.parse_status,
                skip_reason=f.skip_reason,
            )
            for f in items
        ],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get("/scans/{scan_id}/events", response_model=ScanEventsResponse)
def get_scan_events(scan_id: UUID) -> ScanEventsResponse:
    scan = scan_service.get_scan(scan_id)
    if scan is None:
        raise AppError("SCAN_NOT_FOUND", "Scan not found.", 404)

    client = scan_service.get_supabase_client()
    result = (
        client.table("scan_events")
        .select("*")
        .eq("scan_id", str(scan_id))
        .order("created_at")
        .execute()
    )

    return ScanEventsResponse(
        scan_id=scan_id,
        events=[
            ScanEventItem(
                event_type=row["event_type"],
                message=row["message"],
                metadata=row.get("metadata"),
                created_at=row["created_at"],
            )
            for row in result.data
        ],
    )
