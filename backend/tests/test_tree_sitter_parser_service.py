from pathlib import Path

from app.services.tree_sitter_parser_service import parse_file


def test_parse_file_ok_python(tmp_path: Path):
    f = tmp_path / "sample.py"
    f.write_text("def foo():\n    return 1\n")

    result = parse_file(f, "python", ".py")

    assert result.ok is True
    assert result.error_code is None
    assert result.root_node is not None


def test_parse_file_unsupported_extension_sets_language_unsupported_code(tmp_path: Path):
    f = tmp_path / "sample.rb"
    f.write_text("def foo; end\n")

    result = parse_file(f, "ruby", ".rb")

    assert result.ok is False
    assert result.error_code == "TREE_SITTER_LANGUAGE_UNSUPPORTED"


def test_parse_file_missing_file_sets_file_read_failed_code(tmp_path: Path):
    missing = tmp_path / "does_not_exist.py"

    result = parse_file(missing, "python", ".py")

    assert result.ok is False
    assert result.error_code == "FILE_READ_FAILED"


def test_parse_file_tsx_uses_tsx_grammar_but_reports_typescript_language(tmp_path: Path):
    f = tmp_path / "sample.tsx"
    f.write_text("export function Foo() {\n  return <div>hi</div>;\n}\n")

    result = parse_file(f, "typescript", ".tsx")

    assert result.ok is True
    assert result.language == "typescript"
