from pathlib import Path
from uuid import uuid4

from app.services.symbol_extraction_service import extract_symbols
from app.services.tree_sitter_parser_service import parse_file


def test_extract_symbols_python(tmp_path: Path):
    f = tmp_path / "sample.py"
    f.write_text(
        "import os\n"
        "from typing import Any\n"
        "\n"
        "def foo(x):\n"
        "    return x + 1\n"
        "\n"
        "class Bar:\n"
        "    def method(self):\n"
        "        return foo(1)\n"
    )

    parsed = parse_file(f, "python", ".py")
    assert parsed.ok is True

    scan_id = uuid4()
    file_id = uuid4()
    symbols = extract_symbols(parsed, scan_id, file_id, "sample.py")

    by_type = {}
    for s in symbols:
        by_type.setdefault(s.symbol_type, []).append(s)

    assert len(by_type["module"]) == 1
    assert {s.symbol_name for s in by_type["import"]} == {"import os", "from typing import Any"}
    assert [s.symbol_name for s in by_type["function"]] == ["foo"]
    assert [s.symbol_name for s in by_type["class"]] == ["Bar"]
    assert [s.symbol_name for s in by_type["method"]] == ["method"]

    # Method's local_parent_id should point at the class's local_id.
    method_symbol = by_type["method"][0]
    class_symbol = by_type["class"][0]
    assert method_symbol.local_parent_id == class_symbol.local_id


def test_extract_symbols_returns_empty_for_failed_parse(tmp_path: Path):
    f = tmp_path / "sample.py"
    f.write_text("def foo(:\n")  # syntactically odd but tree-sitter is error-tolerant

    parsed = parse_file(f, "python", ".py")
    # Force a "failed" parse result to exercise the guard clause directly.
    parsed.ok = False

    symbols = extract_symbols(parsed, uuid4(), uuid4(), "sample.py")

    assert symbols == []


def test_extract_symbols_tsx_function_and_class(tmp_path: Path):
    f = tmp_path / "sample.tsx"
    f.write_text(
        "import React from 'react';\n"
        "\n"
        "export function Foo() {\n"
        "  return <div>hi</div>;\n"
        "}\n"
        "\n"
        "class Bar {\n"
        "  method() {\n"
        "    return 1;\n"
        "  }\n"
        "}\n"
    )

    parsed = parse_file(f, "typescript", ".tsx")
    assert parsed.ok is True

    symbols = extract_symbols(parsed, uuid4(), uuid4(), "sample.tsx")
    names_by_type = {}
    for s in symbols:
        names_by_type.setdefault(s.symbol_type, set()).add(s.symbol_name)

    assert "Foo" in names_by_type.get("function", set())
    assert "Bar" in names_by_type.get("class", set())
    assert "method" in names_by_type.get("method", set())
