import hashlib
from uuid import UUID

from app.schemas.chunks import CodeChunk
from app.schemas.symbols import CodeSymbol

FALLBACK_CHUNK_LINES = 100
FILE_CHUNK_MAX_LINES = 200


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def _token_count(content: str) -> int:
    # Cheap approximation (no extra tokenizer dependency): whitespace-split word count.
    return len(content.split())


def build_chunks(
    scan_id: UUID,
    file_id: UUID,
    file_path: str,
    language: str | None,
    symbols: list[CodeSymbol],
    symbol_id_map: dict[str, UUID],
    source: str,
    parsed_ok: bool,
) -> list[CodeChunk]:
    """Build retrieval chunks for a file, following the priority order in
    phase2.md 5.8: function > method > class > file fallback > line fallback.
    """
    chunks: list[CodeChunk] = []

    functions_and_methods = [s for s in symbols if s.symbol_type in ("function", "method")]
    classes = [s for s in symbols if s.symbol_type == "class"]
    imports = [s for s in symbols if s.symbol_type == "import"]

    for symbol in functions_and_methods:
        content = symbol.raw_code or ""
        if not content:
            continue
        symbol_id = symbol_id_map.get(symbol.local_id or "")
        chunks.append(
            CodeChunk(
                scan_id=scan_id,
                file_id=file_id,
                symbol_id=symbol_id,
                chunk_type="function_chunk" if symbol.symbol_type == "function" else "method_chunk",
                language=language,
                file_path=file_path,
                symbol_name=symbol.symbol_name,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                content=content,
                content_hash=_hash(content),
                token_count=_token_count(content),
            )
        )

    for symbol in classes:
        content = symbol.raw_code or ""
        if not content:
            continue
        symbol_id = symbol_id_map.get(symbol.local_id or "")
        chunks.append(
            CodeChunk(
                scan_id=scan_id,
                file_id=file_id,
                symbol_id=symbol_id,
                chunk_type="class_chunk",
                language=language,
                file_path=file_path,
                symbol_name=symbol.symbol_name,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                content=content,
                content_hash=_hash(content),
                token_count=_token_count(content),
            )
        )

    if imports:
        import_content = "\n".join(s.raw_code or s.symbol_name for s in imports)
        first, last = imports[0], imports[-1]
        chunks.append(
            CodeChunk(
                scan_id=scan_id,
                file_id=file_id,
                symbol_id=None,
                chunk_type="import_chunk",
                language=language,
                file_path=file_path,
                symbol_name=None,
                start_line=first.start_line,
                end_line=last.end_line,
                content=import_content,
                content_hash=_hash(import_content),
                token_count=_token_count(import_content),
            )
        )

    if chunks:
        return chunks

    # Fallback: no symbol-level chunks were created, either because the file
    # failed to parse or has no recognizable symbols (e.g. a config file).
    if not source:
        return []

    lines = source.splitlines()
    if not parsed_ok or len(lines) > FILE_CHUNK_MAX_LINES:
        for start in range(0, len(lines), FALLBACK_CHUNK_LINES):
            end = min(start + FALLBACK_CHUNK_LINES, len(lines))
            content = "\n".join(lines[start:end])
            if not content.strip():
                continue
            chunks.append(
                CodeChunk(
                    scan_id=scan_id,
                    file_id=file_id,
                    symbol_id=None,
                    chunk_type="fallback_chunk",
                    language=language,
                    file_path=file_path,
                    symbol_name=None,
                    start_line=start + 1,
                    end_line=end,
                    content=content,
                    content_hash=_hash(content),
                    token_count=_token_count(content),
                )
            )
        return chunks

    chunks.append(
        CodeChunk(
            scan_id=scan_id,
            file_id=file_id,
            symbol_id=None,
            chunk_type="file_chunk",
            language=language,
            file_path=file_path,
            symbol_name=None,
            start_line=1,
            end_line=len(lines),
            content=source,
            content_hash=_hash(source),
            token_count=_token_count(source),
        )
    )
    return chunks
