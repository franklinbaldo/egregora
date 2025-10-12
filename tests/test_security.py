import zipfile
from datetime import date

import pytest

from egregora.config import PipelineConfig, _ensure_safe_directory
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


def test_pipeline_config_validates_merges():
    """Test that PipelineConfig validates merge configurations."""
    from egregora.models import MergeConfig
    
    # Test invalid merge config structure
    with pytest.raises(Exception):  # Validation will fail
        PipelineConfig(
            merges={"bad": "not-a-merge-config"}  # type: ignore[dict-item]
        )


def test_pipeline_config_direct_initialization():
    """Test that PipelineConfig can be initialized directly."""
    config = PipelineConfig()
    assert config.posts_dir is not None
    assert config.model == "gemini-flash-lite-latest"


def test_pipeline_config_validates_paths():
    """Test that PipelineConfig validates path fields."""
    from pathlib import Path
    config = PipelineConfig(posts_dir=Path("/tmp/test"))
    assert config.posts_dir == Path("/tmp/test")


def test_ensure_safe_directory_rejects_parent_escape():
    with pytest.raises(ValueError):
        _ensure_safe_directory("../outside")
