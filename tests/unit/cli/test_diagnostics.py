"""Unit tests for diagnostic utilities."""

from pathlib import Path

from egregora.config.settings import DEFAULT_MODEL
from egregora.cli.diagnostics import HealthStatus, check_egregora_config


def test_check_egregora_config_detects_toml(tmp_path: Path, monkeypatch):
    """Ensure diagnostics detect and validate existing .egregora.toml files."""
    config_file = tmp_path / ".egregora.toml"
    config_file.write_text(
        f"""
[models]
writer = "{DEFAULT_MODEL}"

[rag]
enabled = true
""".lstrip()
    )

    monkeypatch.chdir(tmp_path)

    result = check_egregora_config()

    assert result.status is HealthStatus.OK
    assert ".egregora.toml" in result.message
    assert result.details is not None
    assert result.details["writer_model"] == DEFAULT_MODEL
