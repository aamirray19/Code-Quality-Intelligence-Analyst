from pathlib import Path

from pydantic import BaseModel

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "venv",
    "env",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".cache",
    "coverage",
    "target",
    "vendor",
    ".idea",
    ".vscode",
}

# Extensions considered binary/non-source and always skipped outright.
IGNORED_EXTENSIONS = {
    # images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff",
    # videos
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    # audio
    ".mp3", ".wav", ".flac", ".ogg",
    # archives
    ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2",
    # documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # fonts
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # binaries
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".pyc", ".o", ".a",
    # lock files
    ".lock",
    # logs
    ".log",
}

IGNORED_FILE_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "poetry.lock",
    "uv.lock",
    "Cargo.lock",
    "Gemfile.lock",
}

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    # .tsx is stored/reported as "typescript" (phase2.md 6.2's documented
    # `language` filter enum only lists python|javascript|typescript), but the
    # tsx Tree-sitter grammar is still used internally, keyed off the file
    # extension rather than this language string (see
    # tree_sitter_parser_service.EXTENSION_TO_GRAMMAR).
    ".tsx": "typescript",
}


class FileClassification(BaseModel):
    include: bool
    is_supported: bool
    language: str | None = None
    skip_reason: str | None = None


def is_ignored_directory(directory_name: str) -> bool:
    return directory_name in IGNORED_DIRECTORIES


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(8192)
    except OSError:
        return True
    return b"\x00" in chunk


def classify_file(path: Path, max_file_size_bytes: int) -> FileClassification:
    """Decide whether a discovered file should be included, skipped, or unsupported."""
    if path.name in IGNORED_FILE_NAMES:
        return FileClassification(include=False, is_supported=False, skip_reason="lock_file")

    extension = path.suffix.lower()

    if extension in IGNORED_EXTENSIONS:
        return FileClassification(include=False, is_supported=False, skip_reason="ignored_extension")

    try:
        size_bytes = path.stat().st_size
    except OSError:
        return FileClassification(include=False, is_supported=False, skip_reason="unreadable_file")

    if size_bytes > max_file_size_bytes:
        return FileClassification(include=False, is_supported=False, skip_reason="file_too_large")

    if size_bytes == 0:
        return FileClassification(include=True, is_supported=False, language=None, skip_reason=None)

    if _looks_binary(path):
        return FileClassification(include=False, is_supported=False, skip_reason="binary_file")

    language = SUPPORTED_EXTENSIONS.get(extension)
    if language is not None:
        return FileClassification(include=True, is_supported=True, language=language, skip_reason=None)

    # Included but not parsed by Tree-sitter yet (e.g. .md, .json, .yaml, .java).
    return FileClassification(include=True, is_supported=False, language=None, skip_reason=None)
