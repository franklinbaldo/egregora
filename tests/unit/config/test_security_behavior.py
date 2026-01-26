"""Tests for configuration security and behavioral overrides."""

from datetime import date

import pytest
from pydantic import ValidationError

from egregora.config.settings import (
    EgregoraConfig,
    PathsSettings,
)


def test_paths_settings_prevents_traversal():
    """Verify that PathsSettings blocks path traversal attempts."""
    # Valid relative path
    settings = PathsSettings(docs_dir="docs/safe")
    assert settings.docs_dir == "docs/safe"

    # Valid absolute path (currently allowed if no traversal)
    settings = PathsSettings(docs_dir="/tmp/safe")
    assert settings.docs_dir == "/tmp/safe"

    # Invalid traversal attempt
    with pytest.raises(ValidationError) as exc:
        PathsSettings(docs_dir="../unsafe")
    assert "Path must not contain traversal sequences" in str(exc.value)

    # Invalid traversal attempt nested
    with pytest.raises(ValidationError) as exc:
        PathsSettings(docs_dir="docs/../unsafe")
    assert "Path must not contain traversal sequences" in str(exc.value)

    # Check that other path fields also validate
    with pytest.raises(ValidationError):
        PathsSettings(rag_dir="../rag")


def test_config_from_cli_overrides_pipeline(minimal_config):
    """Verify CLI overrides correctly update nested pipeline settings."""
    base_config = minimal_config

    # Defaults
    assert base_config.pipeline.step_size != 999
    assert base_config.pipeline.max_prompt_tokens != 123456

    overrides = {
        "step_size": 999,
        "max_prompt_tokens": 123456,
        "use_full_context_window": True,
    }

    new_config = EgregoraConfig.from_cli_overrides(base_config, **overrides)

    assert new_config.pipeline.step_size == 999
    assert new_config.pipeline.max_prompt_tokens == 123456
    assert new_config.pipeline.use_full_context_window is True

    # Base config should remain unchanged
    assert base_config.pipeline.step_size != 999


def test_config_from_cli_overrides_enrichment(minimal_config):
    """Verify CLI overrides update enrichment settings."""
    base_config = minimal_config
    # Default is usually True
    base_config.enrichment.enabled = True

    overrides = {"enable_enrichment": False}
    new_config = EgregoraConfig.from_cli_overrides(base_config, **overrides)

    assert new_config.enrichment.enabled is False


def test_config_from_cli_overrides_dates_and_timezone(minimal_config):
    """Verify CLI overrides handle dates and timezone strings."""
    base_config = minimal_config

    overrides = {
        "from_date": date(2023, 1, 1),
        "to_date": date(2023, 1, 31),
        "timezone": "Europe/Paris",
    }

    new_config = EgregoraConfig.from_cli_overrides(base_config, **overrides)

    assert new_config.pipeline.from_date == "2023-01-01"
    assert new_config.pipeline.to_date == "2023-01-31"
    assert new_config.pipeline.timezone == "Europe/Paris"


def test_config_from_cli_overrides_model(minimal_config):
    """Verify CLI overrides update all model fields."""
    base_config = minimal_config

    overrides = {"model": "google-gla:gemini-test"}
    new_config = EgregoraConfig.from_cli_overrides(base_config, **overrides)

    assert new_config.models.writer == "google-gla:gemini-test"
    assert new_config.models.enricher == "google-gla:gemini-test"
    assert new_config.models.ranking == "google-gla:gemini-test"
    # Embedding uses a different format, so it should NOT be updated by this generic override
    # logic in from_cli_overrides, OR from_cli_overrides only updates pydantic models.
    # Let's check implementation:
    # if cli_args.get("model"):
    #     model = cli_args["model"]
    #     model_overrides = { "writer": model, "enricher": model, ... }
    # It does NOT update embedding.
    assert new_config.models.embedding != "google-gla:gemini-test"
