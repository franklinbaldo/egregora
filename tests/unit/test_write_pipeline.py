"""Unit tests for write pipeline utilities."""

from egregora.agents.model_limits import get_model_context_limit
from egregora.config.settings import EgregoraConfig
from egregora.orchestration.write_pipeline import _calculate_max_window_size


def test_calculate_max_window_size_uses_config_cap() -> None:
    """When full context is disabled, use the configured max_prompt_tokens cap."""

    config = EgregoraConfig(pipeline={"max_prompt_tokens": 50_000})

    expected_window_size = int((50_000 * 0.8) / 5)

    assert _calculate_max_window_size(config) == expected_window_size


def test_calculate_max_window_size_full_context_respects_model_limits() -> None:
    """Full-context mode should use model limits and honor config model settings."""

    config = EgregoraConfig(
        pipeline={"use_full_context_window": True, "max_prompt_tokens": 2_000},
        models={"writer": "google-gla:gemini-pro"},
    )

    config_model_limit = get_model_context_limit("google-gla:gemini-pro")
    expected_from_config = int((config_model_limit * 0.8) / 5)

    # Verify we use the model's limit instead of the pipeline cap
    assert _calculate_max_window_size(config) == expected_from_config

    # Test with a different model (simulating CLI override applied to config)
    override_config = config.model_copy(
        update={"models": config.models.model_copy(update={"writer": "google-gla:gemini-flash-latest"})}
    )
    override_limit = get_model_context_limit("google-gla:gemini-flash-latest")
    expected_from_override = int((override_limit * 0.8) / 5)

    assert _calculate_max_window_size(override_config) == expected_from_override
