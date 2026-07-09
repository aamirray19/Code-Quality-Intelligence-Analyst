from uuid import uuid4

from app.schemas.symbols import CodeSymbol
from app.services.chunk_builder_service import build_chunks


def _symbol(scan_id, file_id, **overrides) -> CodeSymbol:
    defaults = dict(
        scan_id=scan_id,
        file_id=file_id,
        symbol_type="function",
        symbol_name="foo",
        qualified_name="foo",
        start_line=1,
        end_line=2,
        raw_code="def foo():\n    pass\n",
        language="python",
        local_id="local-1",
        local_parent_id=None,
    )
    defaults.update(overrides)
    return CodeSymbol(**defaults)


def test_build_chunks_creates_function_chunk():
    scan_id, file_id = uuid4(), uuid4()
    symbol_id = uuid4()
    symbol = _symbol(scan_id, file_id, local_id="fn-1")

    chunks = build_chunks(
        scan_id=scan_id,
        file_id=file_id,
        file_path="sample.py",
        language="python",
        symbols=[symbol],
        symbol_id_map={"fn-1": symbol_id},
        source="def foo():\n    pass\n",
        parsed_ok=True,
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == "function_chunk"
    assert chunk.symbol_id == symbol_id
    assert chunk.symbol_name == "foo"


def test_build_chunks_creates_method_and_class_chunks():
    scan_id, file_id = uuid4(), uuid4()
    class_symbol = _symbol(
        scan_id, file_id, symbol_type="class", symbol_name="Bar", local_id="class-1",
        raw_code="class Bar:\n    def method(self):\n        pass\n", start_line=1, end_line=3,
    )
    method_symbol = _symbol(
        scan_id, file_id, symbol_type="method", symbol_name="method", local_id="method-1",
        local_parent_id="class-1", raw_code="def method(self):\n    pass\n", start_line=2, end_line=3,
    )

    chunks = build_chunks(
        scan_id=scan_id,
        file_id=file_id,
        file_path="sample.py",
        language="python",
        symbols=[class_symbol, method_symbol],
        symbol_id_map={},
        source="class Bar:\n    def method(self):\n        pass\n",
        parsed_ok=True,
    )

    chunk_types = {c.chunk_type for c in chunks}
    assert chunk_types == {"class_chunk", "method_chunk"}


def test_build_chunks_creates_import_chunk():
    scan_id, file_id = uuid4(), uuid4()
    import_symbol = _symbol(
        scan_id, file_id, symbol_type="import", symbol_name="import os",
        raw_code="import os", start_line=1, end_line=1, local_id="imp-1",
    )
    fn_symbol = _symbol(scan_id, file_id, local_id="fn-1")

    chunks = build_chunks(
        scan_id=scan_id,
        file_id=file_id,
        file_path="sample.py",
        language="python",
        symbols=[import_symbol, fn_symbol],
        symbol_id_map={},
        source="import os\ndef foo():\n    pass\n",
        parsed_ok=True,
    )

    import_chunks = [c for c in chunks if c.chunk_type == "import_chunk"]
    assert len(import_chunks) == 1
    assert "import os" in import_chunks[0].content


def test_build_chunks_falls_back_to_file_chunk_when_no_symbols():
    scan_id, file_id = uuid4(), uuid4()
    source = "x = 1\ny = 2\n"

    chunks = build_chunks(
        scan_id=scan_id,
        file_id=file_id,
        file_path="config.py",
        language="python",
        symbols=[],
        symbol_id_map={},
        source=source,
        parsed_ok=True,
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_type == "file_chunk"
    assert chunks[0].content == source


def test_build_chunks_uses_line_fallback_for_failed_parse():
    scan_id, file_id = uuid4(), uuid4()
    source = "\n".join(f"line {i}" for i in range(250))

    chunks = build_chunks(
        scan_id=scan_id,
        file_id=file_id,
        file_path="broken.py",
        language="python",
        symbols=[],
        symbol_id_map={},
        source=source,
        parsed_ok=False,
    )

    assert all(c.chunk_type == "fallback_chunk" for c in chunks)
    assert len(chunks) > 1


def test_build_chunks_returns_empty_for_empty_source():
    scan_id, file_id = uuid4(), uuid4()

    chunks = build_chunks(
        scan_id=scan_id,
        file_id=file_id,
        file_path="empty.py",
        language="python",
        symbols=[],
        symbol_id_map={},
        source="",
        parsed_ok=True,
    )

    assert chunks == []
