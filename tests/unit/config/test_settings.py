from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict, TomlConfigSettingsSource
from egregora.config.settings import EgregoraConfig


@pytest.fixture
def sample_config_path(tmp_path: Path) -> Path:
    """Create a sample .egregora.toml file for testing (no sites)."""
    config_content = '''
[models]
writer = "google-gla:gemini-test-writer"
enricher = "google-gla:gemini-test-enricher"

[pipeline]
step_size = 10
step_unit = "messages"

[rag]
enabled = false
top_k = 3
'''
    config_path = tmp_path / ".egregora.toml"
    config_path.write_text(config_content, encoding="utf-8")
    return config_path


def test_load_egregora_config_from_file(sample_config_path: Path):
    """Verify that EgregoraConfig correctly loads settings from a TOML file."""
    # Act
    config = EgregoraConfig(toml_file=str(sample_config_path))

    # Assert
    assert isinstance(config, EgregoraConfig)
    assert config.models.writer == "google-gla:gemini-test-writer"
    assert config.models.enricher == "google-gla:gemini-test-enricher"
    assert config.pipeline.step_size == 10
    assert config.pipeline.step_unit == "messages"
    assert not config.rag.enabled
    assert config.rag.top_k == 3


def test_load_egregora_config_with_env_override(sample_config_path: Path, monkeypatch):
    """Verify that environment variables override settings from the TOML file."""
    # Arrange
    monkeypatch.setenv("EGREGORA_MODELS__WRITER", "google-gla:gemini-env-override")
    monkeypatch.setenv("EGREGORA_PIPELINE__STEP_SIZE", "25")

    # Act
    config = EgregoraConfig(toml_file=str(sample_config_path))

    # Assert
    assert config.models.writer == "google-gla:gemini-env-override"  # Overridden
    assert config.pipeline.step_size == 25  # Overridden
    assert config.models.enricher == "google-gla:gemini-test-enricher"  # From file
    assert not config.rag.enabled  # From file
