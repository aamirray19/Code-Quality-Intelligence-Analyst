from pathlib import Path
from uuid import uuid4

from app.services.file_discovery_service import discover_files


def test_discover_files_applies_filters_and_records_skips(tmp_path: Path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_total_files", 1000)
    monkeypatch.setattr(settings, "max_file_size_bytes", 500_000)

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def foo():\n    pass\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("console.log('nope')")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "README.md").write_text("# hi\n")

    scan_id = uuid4()
    discovered = discover_files(scan_id, tmp_path)

    by_path = {d.relative_path: d for d in discovered}

    assert "src/main.py" in by_path
    assert by_path["src/main.py"].is_supported is True
    assert by_path["src/main.py"].parse_status == "pending"

    assert "README.md" in by_path
    assert by_path["README.md"].is_supported is False
    assert by_path["README.md"].parse_status == "unsupported"

    assert "logo.png" in by_path
    assert by_path["logo.png"].parse_status == "skipped"
    assert by_path["logo.png"].skip_reason == "ignored_extension"

    # node_modules directory must be pruned entirely (not just its files skipped).
    assert not any("node_modules" in path for path in by_path)


def test_discover_files_respects_max_total_files(tmp_path: Path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_total_files", 2)
    monkeypatch.setattr(settings, "max_file_size_bytes", 500_000)

    for i in range(5):
        (tmp_path / f"file_{i}.py").write_text("x = 1\n")

    discovered = discover_files(uuid4(), tmp_path)

    assert len(discovered) == 2
