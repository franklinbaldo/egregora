import io
import zipfile
from datetime import date

import pytest

from egregora import config as config_module
from egregora.config import PipelineConfig, _ensure_safe_directory, _load_toml_data
from egregora.group_discovery import _iter_preview_lines, discover_groups
from egregora.models import WhatsAppExport
from egregora.zip_utils import ZipValidationError, validate_zip_contents

try:  # pragma: no cover - defensive import for optional dependency
    from egregora.parser import parse_export
except ModuleNotFoundError as exc:  # pragma: no cover - executed only when polars missing
    PARSER_IMPORT_ERROR = exc
    parse_export = None  # type: ignore[assignment]
else:
    PARSER_IMPORT_ERROR = None


def make_export(zip_path, chat_file: str) -> WhatsAppExport:
    return WhatsAppExport(
        zip_path=zip_path,
        group_name="Test Group",
        group_slug="test-group",
        export_date=date(2024, 1, 1),
        chat_file=chat_file,
        media_files=[],
    )


def test_validate_zip_contents_rejects_path_traversal(tmp_path):
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", "data")

    with zipfile.ZipFile(zip_path) as zf:
        with pytest.raises(ZipValidationError):
            validate_zip_contents(zf)


def test_discover_groups_rejects_symlink(tmp_path, caplog):
    real_zip = tmp_path / "real.zip"
    with zipfile.ZipFile(real_zip, "w") as zf:
        zf.writestr(
            "WhatsApp Chat with Test.txt",
            b"[01/01/2024, 00:00] Test: message\n",
        )

    zips_dir = tmp_path / "zips"
    zips_dir.mkdir()

    symlink_path = zips_dir / "link.zip"
    try:
        symlink_path.symlink_to(real_zip)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")

    with caplog.at_level("WARNING"):
        groups = discover_groups(zips_dir)

    assert groups == {}
    assert any("refusing to follow symlink" in message for message in caplog.messages)


def test_iter_preview_lines_rejects_long_lines():
    long_line = b"x" * 16_385 + b"\n"

    with pytest.raises(ZipValidationError):
        list(_iter_preview_lines(io.BytesIO(long_line), limit=1))


def test_parse_export_rejects_invalid_utf8(tmp_path):
    if parse_export is None:  # pragma: no cover - depends on optional dependency
        pytest.skip(f"parser import failed: {PARSER_IMPORT_ERROR}")

    chat_file = "WhatsApp Chat with Test.txt"
    zip_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(chat_file, b"\xff\xfe\x00bad")

    export = make_export(zip_path, chat_file)

    with pytest.raises(ZipValidationError):
        parse_export(export)


def test_load_toml_data_rejects_large_file(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text('value = "123456"\n', encoding="utf-8")

    monkeypatch.setattr(config_module, "_MAX_TOML_BYTES", 4)

    with pytest.raises(ValueError):
        _load_toml_data(config_path)


def test_load_toml_data_requires_top_level_table(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("42\n", encoding="utf-8")

    with pytest.raises(ValueError):
        _load_toml_data(config_path)


def test_pipeline_config_from_toml_validates_merges(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [merges.bad]
        name = "Bad"
        groups = "not-a-list"
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        PipelineConfig.from_toml(config_path)


def test_ensure_safe_directory_rejects_parent_escape():
    with pytest.raises(ValueError):
        _ensure_safe_directory("../outside")
