import hashlib
import os
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.schemas.files import DiscoveredFile
from app.services.file_filter_service import classify_file, is_ignored_directory


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def discover_files(scan_id: UUID, repo_path: Path) -> list[DiscoveredFile]:
    """Walk `repo_path`, applying directory/file filters, and return file records.

    Stops discovering additional files once `settings.max_total_files` is reached.
    """
    discovered: list[DiscoveredFile] = []
    max_total_files = settings.max_total_files
    max_file_size_bytes = settings.max_file_size_bytes

    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if not is_ignored_directory(d)]

        for filename in filenames:
            if len(discovered) >= max_total_files:
                return discovered

            absolute_path = Path(dirpath) / filename
            classification = classify_file(absolute_path, max_file_size_bytes)
            relative_path = absolute_path.relative_to(repo_path).as_posix()

            if not classification.include:
                # Still record skipped files so scan_files is a complete,
                # auditable inventory (per phase2.md 5.4).
                try:
                    size_bytes = absolute_path.stat().st_size
                except OSError:
                    size_bytes = 0
                discovered.append(
                    DiscoveredFile(
                        scan_id=scan_id,
                        relative_path=relative_path,
                        absolute_path=absolute_path,
                        file_name=filename,
                        extension=absolute_path.suffix.lower(),
                        language=None,
                        size_bytes=size_bytes,
                        line_count=0,
                        content_hash="",
                        is_supported=False,
                        parse_status="skipped",
                        skip_reason=classification.skip_reason,
                    )
                )
                continue

            size_bytes = absolute_path.stat().st_size
            line_count = _count_lines(absolute_path) if classification.is_supported else 0
            content_hash = _content_hash(absolute_path)

            discovered.append(
                DiscoveredFile(
                    scan_id=scan_id,
                    relative_path=relative_path,
                    absolute_path=absolute_path,
                    file_name=filename,
                    extension=absolute_path.suffix.lower(),
                    language=classification.language,
                    size_bytes=size_bytes,
                    line_count=line_count,
                    content_hash=content_hash,
                    is_supported=classification.is_supported,
                    parse_status="pending" if classification.is_supported else "unsupported",
                    skip_reason=None,
                )
            )

    return discovered
