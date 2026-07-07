from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tree_sitter_language_pack import get_parser

# Maps file extensions to tree-sitter-language-pack grammar names. Keyed by
# extension (not the stored `language` string) so that `.tsx` files can use
# the dedicated `tsx` grammar (which understands JSX-in-TS syntax) even
# though they're reported/stored with `language="typescript"` for API
# consistency with phase2.md 6.2's documented filter enum.
EXTENSION_TO_GRAMMAR = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}

_parser_cache: dict[str, Any] = {}


def _get_parser(extension: str):
    grammar = EXTENSION_TO_GRAMMAR.get(extension)
    if grammar is None:
        raise ValueError(f"Unsupported file extension: {extension}")
    if grammar not in _parser_cache:
        _parser_cache[grammar] = get_parser(grammar)
    return _parser_cache[grammar]


@dataclass
class ParsedFileResult:
    language: str
    source: str
    root_node: Any | None
    ok: bool
    error_message: str | None = None
    error_code: str | None = None


def parse_file(absolute_path: Path, language: str, extension: str) -> ParsedFileResult:
    """Read `absolute_path` and parse it with the Tree-sitter grammar for `extension`.

    `language` is the stored/API-facing language label (e.g. "typescript" for
    both .ts and .tsx); `extension` selects the actual grammar so .tsx files
    still get the tsx grammar internally.

    Never raises: parse/read failures are captured in the returned result so a
    single bad file cannot abort the rest of the scan (phase2.md 5.5). The
    `error_code` distinguishes *why* parsing failed (phase2.md 9): a missing
    grammar (`TREE_SITTER_LANGUAGE_UNSUPPORTED`), an unreadable file
    (`FILE_READ_FAILED`), or an actual grammar parse failure
    (`TREE_SITTER_PARSE_FAILED`).
    """
    try:
        source = absolute_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ParsedFileResult(
            language=language,
            source="",
            root_node=None,
            ok=False,
            error_message=str(exc),
            error_code="FILE_READ_FAILED",
        )

    try:
        parser = _get_parser(extension)
    except ValueError as exc:
        return ParsedFileResult(
            language=language,
            source=source,
            root_node=None,
            ok=False,
            error_message=str(exc),
            error_code="TREE_SITTER_LANGUAGE_UNSUPPORTED",
        )

    try:
        tree = parser.parse(source)
        root_node = tree.root_node()
    except Exception as exc:  # tree-sitter parse errors are not raised normally, but guard anyway
        return ParsedFileResult(
            language=language,
            source=source,
            root_node=None,
            ok=False,
            error_message=str(exc),
            error_code="TREE_SITTER_PARSE_FAILED",
        )

    return ParsedFileResult(language=language, source=source, root_node=root_node, ok=True)
