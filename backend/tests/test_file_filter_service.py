from pathlib import Path

from app.services.file_filter_service import classify_file


def test_classify_supported_python_file(tmp_path: Path):
    f = tmp_path / "main.py"
    f.write_text("print('hi')\n")

    result = classify_file(f, max_file_size_bytes=500_000)

    assert result.include is True
    assert result.is_supported is True
    assert result.language == "python"
    assert result.skip_reason is None


def test_classify_unsupported_extension_still_included(tmp_path: Path):
    f = tmp_path / "README.md"
    f.write_text("# hello\n")

    result = classify_file(f, max_file_size_bytes=500_000)

    assert result.include is True
    assert result.is_supported is False
    assert result.language is None


def test_classify_ignored_extension_skipped(tmp_path: Path):
    f = tmp_path / "logo.png"
    f.write_bytes(b"\x89PNG\r\n")

    result = classify_file(f, max_file_size_bytes=500_000)

    assert result.include is False
    assert result.skip_reason == "ignored_extension"


def test_classify_lock_file_skipped(tmp_path: Path):
    f = tmp_path / "package-lock.json"
    f.write_text("{}")

    result = classify_file(f, max_file_size_bytes=500_000)

    assert result.include is False
    assert result.skip_reason == "lock_file"


def test_classify_oversized_file_skipped(tmp_path: Path):
    f = tmp_path / "big.py"
    f.write_text("x = 1\n" * 100)

    result = classify_file(f, max_file_size_bytes=10)

    assert result.include is False
    assert result.skip_reason == "file_too_large"


def test_classify_binary_file_skipped(tmp_path: Path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"\x00\x01\x02binary\x00data")
    # Use an extension that isn't in IGNORED_EXTENSIONS so we exercise the
    # binary-sniffing branch specifically.
    f = f.rename(tmp_path / "data.unknownext")

    result = classify_file(f, max_file_size_bytes=500_000)

    assert result.include is False
    assert result.skip_reason == "binary_file"
