"""Unit tests for .egregora/config.yml loading and validation.

Tests cover:
- EgregoraConfig defaults
- Pydantic validation
- Config file loading
- Upward directory search
- Error handling
"""

import pytest
from pydantic import ValidationError

from egregora.config.settings import (
    EgregoraConfig,
    create_default_config,
    find_egregora_config,
    load_egregora_config,
)


def test_egregora_config_defaults():
    """Test EgregoraConfig has sensible defaults."""
    config = EgregoraConfig()

    # Models defaults
    assert config.models.writer == "google-gla:gemini-flash-latest"
    assert config.models.enricher == "google-gla:gemini-flash-latest"
    assert config.models.embedding == "models/gemini-embedding-001"
    assert config.models.banner == "models/gemini-2.5-flash-image"

    # RAG defaults
    assert config.rag.enabled is True
    assert config.rag.top_k == 5
    assert config.rag.min_similarity_threshold == 0.7
    assert config.rag.mode == "ann"

    # Writer defaults
    assert config.writer.custom_instructions is None

    # Enrichment defaults
    assert config.enrichment.enabled is True
    assert config.enrichment.enable_url is True
    assert config.enrichment.enable_media is True

    # Pipeline defaults
    assert config.pipeline.step_size == 1
    assert config.pipeline.step_unit == "days"
    assert config.pipeline.overlap_ratio == 0.2
    assert config.pipeline.max_prompt_tokens == 100_000

    # Features defaults
    assert config.features.ranking_enabled is False
    assert config.features.annotations_enabled is True


def test_rag_config_validation_invalid_mode():
    """Test RAGSettings validation rejects invalid mode."""
    with pytest.raises(ValidationError) as exc_info:
        EgregoraConfig(rag={"mode": "invalid"})

    error = exc_info.value
    assert "mode" in str(error)


def test_rag_config_validation_top_k_out_of_range():
    """Test RAGSettings validation rejects top_k out of range."""
    # Too low
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"top_k": 0})

    # Too high
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"top_k": 21})


def test_rag_config_validation_min_similarity_out_of_range():
    """Test RAGSettings validation rejects min_similarity_threshold out of range."""
    # Too low
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"min_similarity_threshold": -0.1})

    # Too high
    with pytest.raises(ValidationError):
        EgregoraConfig(rag={"min_similarity_threshold": 1.5})


def test_pipeline_config_validation_step_unit():
    """Test PipelineSettings validation for step_unit."""
    # Valid units
    for unit in ["messages", "hours", "days", "bytes"]:
        config = EgregoraConfig(pipeline={"step_unit": unit})
        assert config.pipeline.step_unit == unit

    # Invalid unit
    with pytest.raises(ValidationError):
        EgregoraConfig(pipeline={"step_unit": "invalid"})


def test_pipeline_config_validation_overlap_ratio():
    """Test PipelineSettings validation for overlap_ratio."""
    # Too low
    with pytest.raises(ValidationError):
        EgregoraConfig(pipeline={"overlap_ratio": -0.1})

    # Too high
    with pytest.raises(ValidationError):
        EgregoraConfig(pipeline={"overlap_ratio": 0.6})

    # Valid
    config = EgregoraConfig(pipeline={"overlap_ratio": 0.25})
    assert config.pipeline.overlap_ratio == 0.25


def test_egregora_config_forbids_extra_fields():
    """Test that EgregoraConfig rejects unknown fields."""
    with pytest.raises(ValidationError) as exc_info:
        EgregoraConfig(unknown_field="value")

    error = exc_info.value
    assert "unknown_field" in str(error)


def test_find_egregora_config_upward_search(tmp_path):
    """Test upward search for .egregora/config.yml."""
    # Create directory structure (MODERN: posts at root level)
    site_root = tmp_path / "site"
    egregora_dir = site_root / ".egregora"
    nested = site_root / "posts" / "journal" / "deep"

    egregora_dir.mkdir(parents=True)
    (egregora_dir / "config.yml").write_text("models: {}")
    nested.mkdir(parents=True)

    # Should find .egregora/config.yml from nested directory
    found = find_egregora_config(nested)
    assert found == egregora_dir / "config.yml"


def test_find_egregora_config_not_found(tmp_path):
    """Test find_egregora_config returns None when not found."""
    assert find_egregora_config(tmp_path) is None


def test_load_egregora_config_creates_default_if_missing(tmp_path):
    """Test that load_egregora_config creates default config if missing."""
    config = load_egregora_config(tmp_path)

    # Should have defaults
    assert config.models.writer == "google-gla:gemini-flash-latest"
    assert config.rag.enabled is True

    # Should have created config file
    config_path = tmp_path / ".egregora" / "config.yml"
    assert config_path.exists()


def test_load_egregora_config_parses_yaml(tmp_path):
    """Test loading and parsing config.yml."""
    egregora_dir = tmp_path / ".egregora"
    egregora_dir.mkdir()

    config_content = """
models:
  writer: google-gla:gemini-2.0-flash-exp
  embedding: models/text-embedding-004
rag:
  enabled: true
  top_k: 10
  min_similarity_threshold: 0.8
writer:
  custom_instructions: "Write in a casual tone"
"""
    (egregora_dir / "config.yml").write_text(config_content)

    config = load_egregora_config(tmp_path)
    assert config.models.writer == "google-gla:gemini-2.0-flash-exp"
    assert config.models.embedding == "models/text-embedding-004"
    assert config.rag.top_k == 10
    assert config.rag.min_similarity_threshold == 0.8
    assert config.writer.custom_instructions == "Write in a casual tone"


def test_load_egregora_config_handles_yaml_error(tmp_path):
    """Test that load_egregora_config handles YAML parsing errors gracefully."""
    egregora_dir = tmp_path / ".egregora"
    egregora_dir.mkdir()

    # Invalid YAML
    (egregora_dir / "config.yml").write_text("{ invalid yaml")

    # Should fall back to default config
    config = load_egregora_config(tmp_path)
    assert config.models.writer == "google-gla:gemini-flash-latest"


def test_load_egregora_config_handles_validation_error(tmp_path):
    """Test that load_egregora_config handles validation errors gracefully."""
    egregora_dir = tmp_path / ".egregora"
    egregora_dir.mkdir()

    # Valid YAML but invalid config
    config_content = """
rag:
  top_k: 999  # Out of range
"""
    (egregora_dir / "config.yml").write_text(config_content)

    # Should fall back to default config
    config = load_egregora_config(tmp_path)
    assert config.rag.top_k == 5  # Default


def test_create_default_config(tmp_path):
    """Test creating default config file."""
    config = create_default_config(tmp_path)

    # Should return config with defaults
    assert config.models.writer == "google-gla:gemini-flash-latest"

    # Should create .egregora/ directory
    egregora_dir = tmp_path / ".egregora"
    assert egregora_dir.exists()

    # Should create config.yml file
    config_path = egregora_dir / "config.yml"
    assert config_path.exists()

    # Should be valid YAML
    import yaml

    with config_path.open() as f:
        data = yaml.safe_load(f)
    assert "models" in data
    assert "rag" in data


def test_config_roundtrip(tmp_path):
    """Test that config can be saved and loaded without loss."""
    from egregora.config.settings import save_egregora_config

    # Create custom config
    custom_config = EgregoraConfig(
        models={"writer": "google-gla:custom-model"},
        rag={"top_k": 15, "min_similarity_threshold": 0.9},
        writer={"custom_instructions": "Test instructions"},
    )

    # Save
    save_egregora_config(custom_config, tmp_path)

    # Load
    loaded_config = load_egregora_config(tmp_path)

    # Compare
    assert loaded_config.models.writer == "google-gla:custom-model"
    assert loaded_config.rag.top_k == 15
    assert loaded_config.rag.min_similarity_threshold == 0.9
    assert loaded_config.writer.custom_instructions == "Test instructions"


def test_partial_config_merges_with_defaults(tmp_path):
    """Test that partial config files merge with defaults."""
    egregora_dir = tmp_path / ".egregora"
    egregora_dir.mkdir()

    # Only specify one field
    config_content = """
models:
  writer: google-gla:custom-writer
"""
    (egregora_dir / "config.yml").write_text(config_content)

    config = load_egregora_config(tmp_path)

    # Custom field
    assert config.models.writer == "google-gla:custom-writer"

    # Defaults for everything else
    assert config.models.enricher == "google-gla:gemini-flash-latest"
    assert config.rag.enabled is True
