from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import AppError
from app.schemas.scans import ScanRecord
from app.workers.repo_scan_worker import process_repo_scan

MODULE = "app.workers.repo_scan_worker"


def _sample_scan_record(scan_id, status="queued"):
    now = datetime.now(timezone.utc)
    return ScanRecord(
        id=scan_id,
        github_url="https://github.com/owner/repo",
        repo_owner="owner",
        repo_name="repo",
        repo_full_name="owner/repo",
        branch="main",
        default_branch="main",
        clone_url="https://github.com/owner/repo.git",
        html_url="https://github.com/owner/repo",
        repo_size_kb=1277,
        status=status,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def _sample_payload(scan_id):
    return {
        "job_type": "repo_scan",
        "scan_id": str(scan_id),
        "repo": {
            "owner": "owner",
            "name": "repo",
            "full_name": "owner/repo",
            "branch": "main",
            "default_branch": "main",
            "clone_url": "https://github.com/owner/repo.git",
            "html_url": "https://github.com/owner/repo",
            "size_kb": 1277,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_process_repo_scan_skips_already_parsed_scan():
    scan_id = uuid4()
    payload = _sample_payload(scan_id)
    scan_record = _sample_scan_record(scan_id, status="parsed")

    with patch(f"{MODULE}.scan_service.get_scan", return_value=scan_record), \
         patch(f"{MODULE}.scan_service.update_scan") as update_scan_mock, \
         patch(f"{MODULE}.scan_event_service.create_event") as create_event_mock, \
         patch(f"{MODULE}.workspace_service.cleanup_workspace") as cleanup_mock, \
         patch(f"{MODULE}.repo_clone_service.clone_repository") as clone_mock:
        process_repo_scan(payload)

    # Must not reprocess (no clone call) and must not touch scan status.
    clone_mock.assert_not_called()
    update_scan_mock.assert_not_called()

    skip_events = [
        call for call in create_event_mock.call_args_list if call.args[1] == "duplicate_job_skipped"
    ]
    assert len(skip_events) == 1

    # cleanup_workspace still runs via the outer finally in the normal path,
    # but the early-return skip path exits before reaching try/finally.
    cleanup_mock.assert_not_called()


def test_process_repo_scan_rejects_invalid_payload():
    with pytest.raises(AppError) as exc_info:
        process_repo_scan({"not": "a valid payload"})

    assert exc_info.value.error_code == "INVALID_JOB_PAYLOAD"


def test_process_repo_scan_raises_scan_not_found():
    scan_id = uuid4()
    payload = _sample_payload(scan_id)

    with patch(f"{MODULE}.scan_service.get_scan", return_value=None):
        with pytest.raises(AppError) as exc_info:
            process_repo_scan(payload)

    assert exc_info.value.error_code == "SCAN_NOT_FOUND"


def test_process_repo_scan_marks_failed_on_clone_error():
    scan_id = uuid4()
    payload = _sample_payload(scan_id)
    scan_record = _sample_scan_record(scan_id)

    with patch(f"{MODULE}.scan_service.get_scan", return_value=scan_record), \
         patch(f"{MODULE}.scan_service.update_scan") as update_scan_mock, \
         patch(f"{MODULE}.scan_event_service.create_event") as create_event_mock, \
         patch(f"{MODULE}.workspace_service.create_workspace", return_value="/tmp/fake/repo"), \
         patch(f"{MODULE}.workspace_service.cleanup_workspace") as cleanup_mock, \
         patch(
             f"{MODULE}.repo_clone_service.clone_repository",
             side_effect=AppError("CLONE_FAILED", "git clone failed: boom", 500),
         ):
        with pytest.raises(AppError) as exc_info:
            process_repo_scan(payload)

    assert exc_info.value.error_code == "CLONE_FAILED"
    cleanup_mock.assert_called_once_with(scan_id)

    failed_calls = [
        call for call in update_scan_mock.call_args_list if call.kwargs.get("status") == "failed"
    ]
    assert len(failed_calls) == 1
    assert failed_calls[0].kwargs["error_code"] == "CLONE_FAILED"

    failure_events = [
        call for call in create_event_mock.call_args_list if call.args[1] == "worker_failed"
    ]
    assert len(failure_events) == 1


def test_process_repo_scan_happy_path_marks_parsed():
    scan_id = uuid4()
    payload = _sample_payload(scan_id)
    scan_record = _sample_scan_record(scan_id)

    fake_cloned = MagicMock(branch="main", commit_sha="abc123", repo_path="/tmp/fake/repo")

    with patch(f"{MODULE}.scan_service.get_scan", return_value=scan_record), \
         patch(f"{MODULE}.scan_service.update_scan") as update_scan_mock, \
         patch(f"{MODULE}.scan_event_service.create_event"), \
         patch(f"{MODULE}.workspace_service.create_workspace", return_value="/tmp/fake/repo"), \
         patch(f"{MODULE}.workspace_service.cleanup_workspace") as cleanup_mock, \
         patch(f"{MODULE}.repo_clone_service.clone_repository", return_value=fake_cloned), \
         patch(f"{MODULE}.discover_files", return_value=[]), \
         patch(f"{MODULE}.scan_file_service.store_discovered_files", return_value=[]), \
         patch(f"{MODULE}.code_symbol_service.store_symbols", return_value={}), \
         patch(f"{MODULE}.code_chunk_service.store_chunks_with_ids", return_value=[]), \
         patch(f"{MODULE}.repo_stats_service.compute_repo_stats") as compute_stats_mock:
        process_repo_scan(payload)

    cleanup_mock.assert_called_once_with(scan_id)
    compute_stats_mock.assert_called_once()

    parsed_calls = [
        call for call in update_scan_mock.call_args_list if call.kwargs.get("status") == "parsed"
    ]
    assert len(parsed_calls) == 1


def test_process_repo_scan_triggers_analysis_after_parsing():
    scan_id = uuid4()
    payload = _sample_payload(scan_id)
    scan_record = _sample_scan_record(scan_id, status="queued")

    with patch(f"{MODULE}.scan_service.get_scan", return_value=scan_record), \
         patch(f"{MODULE}.scan_service.update_scan"), \
         patch(f"{MODULE}.scan_event_service.create_event"), \
         patch(f"{MODULE}.workspace_service.create_workspace", return_value="/tmp/x"), \
         patch(f"{MODULE}.workspace_service.cleanup_workspace"), \
         patch(f"{MODULE}.repo_clone_service.clone_repository") as clone_mock, \
         patch(f"{MODULE}.discover_files", return_value=[]), \
         patch(f"{MODULE}.scan_file_service.store_discovered_files", return_value=[]), \
         patch(f"{MODULE}.code_symbol_service.store_symbols", return_value={}), \
         patch(f"{MODULE}.code_chunk_service.store_chunks_with_ids", return_value=[]), \
         patch(f"{MODULE}.repo_stats_service.compute_repo_stats"), \
         patch(f"{MODULE}.run_analysis") as run_analysis_mock, \
         patch(f"{MODULE}.run_report_generation") as run_report_mock:
        clone_mock.return_value.commit_sha = "abc123"
        clone_mock.return_value.branch = "main"
        process_repo_scan(payload)

    run_analysis_mock.assert_called_once_with(scan_id)
    # Phase 4 should also be triggered after successful Phase 3
    run_report_mock.assert_called_once_with(scan_id)


def test_analysis_trigger_failure_does_not_raise_out_of_worker():
    scan_id = uuid4()
    payload = _sample_payload(scan_id)
    scan_record = _sample_scan_record(scan_id, status="queued")

    with patch(f"{MODULE}.scan_service.get_scan", return_value=scan_record), \
         patch(f"{MODULE}.scan_service.update_scan"), \
         patch(f"{MODULE}.scan_event_service.create_event"), \
         patch(f"{MODULE}.workspace_service.create_workspace", return_value="/tmp/x"), \
         patch(f"{MODULE}.workspace_service.cleanup_workspace"), \
         patch(f"{MODULE}.repo_clone_service.clone_repository") as clone_mock, \
         patch(f"{MODULE}.discover_files", return_value=[]), \
         patch(f"{MODULE}.scan_file_service.store_discovered_files", return_value=[]), \
         patch(f"{MODULE}.code_symbol_service.store_symbols", return_value={}), \
         patch(f"{MODULE}.code_chunk_service.store_chunks_with_ids", return_value=[]), \
         patch(f"{MODULE}.repo_stats_service.compute_repo_stats"), \
         patch(f"{MODULE}.run_analysis", side_effect=RuntimeError("graph exploded")), \
         patch(f"{MODULE}.run_report_generation") as run_report_mock:
        clone_mock.return_value.commit_sha = "abc123"
        clone_mock.return_value.branch = "main"
        # Must not raise even though run_analysis blew up.
        process_repo_scan(payload)

    # Phase 4 must NOT be called when Phase 3 failed
    run_report_mock.assert_not_called()


def test_report_generation_trigger_failure_does_not_raise_out_of_worker():
    """Test that Phase 4 failure does not propagate out of the worker."""
    scan_id = uuid4()
    payload = _sample_payload(scan_id)
    scan_record = _sample_scan_record(scan_id, status="queued")

    with patch(f"{MODULE}.scan_service.get_scan", return_value=scan_record), \
         patch(f"{MODULE}.scan_service.update_scan"), \
         patch(f"{MODULE}.scan_event_service.create_event"), \
         patch(f"{MODULE}.workspace_service.create_workspace", return_value="/tmp/x"), \
         patch(f"{MODULE}.workspace_service.cleanup_workspace"), \
         patch(f"{MODULE}.repo_clone_service.clone_repository") as clone_mock, \
         patch(f"{MODULE}.discover_files", return_value=[]), \
         patch(f"{MODULE}.scan_file_service.store_discovered_files", return_value=[]), \
         patch(f"{MODULE}.code_symbol_service.store_symbols", return_value={}), \
         patch(f"{MODULE}.code_chunk_service.store_chunks_with_ids", return_value=[]), \
         patch(f"{MODULE}.repo_stats_service.compute_repo_stats"), \
         patch(f"{MODULE}.run_analysis") as run_analysis_mock, \
         patch(f"{MODULE}.run_report_generation", side_effect=RuntimeError("report exploded")):
        clone_mock.return_value.commit_sha = "abc123"
        clone_mock.return_value.branch = "main"
        # Must not raise even though run_report_generation blew up.
        process_repo_scan(payload)

    # Phase 3 should have been called and succeeded
    run_analysis_mock.assert_called_once_with(scan_id)
