import logging
import shutil
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _scan_root(scan_id: UUID) -> Path:
    return Path(settings.repo_workspace_root) / str(scan_id)


def create_workspace(scan_id: UUID) -> Path:
    """Create (or reset) the temporary workspace directory for a scan.

    Returns the path where the repository should be cloned into, i.e.
    `{REPO_WORKSPACE_ROOT}/{scan_id}/repo`.
    """
    root = _scan_root(scan_id)
    repo_path = root / "repo"
    try:
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(
            "WORKSPACE_CREATE_FAILED", f"Failed to create workspace: {exc}", 500
        ) from exc
    return repo_path


def cleanup_workspace(scan_id: UUID) -> None:
    """Best-effort removal of the temporary workspace directory for a scan."""
    root = _scan_root(scan_id)
    try:
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
    except OSError as exc:
        # Cleanup must never fail the scan; log-and-continue so the failure
        # is at least observable (phase2.md's WORKSPACE_CLEANUP_FAILED code
        # is informational here since we deliberately don't raise/mark the
        # scan failed from a `finally` block).
        logger.warning("Failed to cleanup workspace for scan %s: %s", scan_id, exc)
