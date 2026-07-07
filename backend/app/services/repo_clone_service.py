import subprocess
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.core.errors import AppError
from app.schemas.jobs import ClonedRepository, RepoJobInfo


def clone_repository(scan_id: UUID, repo: RepoJobInfo, workspace: Path) -> ClonedRepository:
    """Shallow-clone `repo` at `repo.branch` into `workspace` and resolve the commit SHA.

    Raises AppError(CLONE_FAILED) on any git failure or timeout.
    """
    timeout = settings.git_clone_timeout_seconds

    clone_cmd = [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        repo.branch,
        repo.clone_url,
        str(workspace),
    ]

    try:
        subprocess.run(
            clone_cmd,
            check=True,
            capture_output=True,
            timeout=timeout,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise AppError(
            "CLONE_FAILED",
            f"git clone failed: {exc.stderr.strip() if exc.stderr else exc}",
            500,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(
            "CLONE_FAILED", f"git clone timed out after {timeout}s", 500
        ) from exc
    except OSError as exc:
        raise AppError("CLONE_FAILED", f"git clone failed: {exc}", 500) from exc

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            cwd=str(workspace),
            timeout=timeout,
            text=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise AppError(
            "CLONE_FAILED", f"Failed to resolve commit SHA: {exc}", 500
        ) from exc

    commit_sha = result.stdout.strip()

    return ClonedRepository(
        scan_id=scan_id,
        repo_path=workspace,
        branch=repo.branch,
        commit_sha=commit_sha,
    )
