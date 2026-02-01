from unittest.mock import MagicMock

from egregora.config.defaults import PipelineDefaults
from egregora.config.settings import EgregoraConfig, PipelineSettings
from egregora.orchestration.pipelines.etl.preparation import _calculate_max_window_size


def test_calculate_max_window_size_default():
    """Verify calculation with default settings."""
    config = MagicMock(spec=EgregoraConfig)
    pipeline_config = MagicMock(spec=PipelineSettings)

    # Defaults: max_prompt_tokens=400_000
    pipeline_config.max_prompt_tokens = 400_000
    pipeline_config.use_full_context_window = False

    config.pipeline = pipeline_config

    expected_size = int((400_000 * PipelineDefaults.BUFFER_RATIO) / PipelineDefaults.AVG_TOKENS_PER_MESSAGE)

    assert _calculate_max_window_size(config) == expected_size


def test_calculate_max_window_size_custom_values():
    """Verify calculation with custom configuration values."""
    config = MagicMock(spec=EgregoraConfig)
    pipeline_config = MagicMock(spec=PipelineSettings)

    pipeline_config.max_prompt_tokens = 100_000
    pipeline_config.use_full_context_window = False

    config.pipeline = pipeline_config

    expected_size = int((100_000 * PipelineDefaults.BUFFER_RATIO) / PipelineDefaults.AVG_TOKENS_PER_MESSAGE)

    assert _calculate_max_window_size(config) == expected_size


def test_calculate_max_window_size_full_context():
    """Verify calculation when use_full_context_window is True."""
    config = MagicMock(spec=EgregoraConfig)
    pipeline_config = MagicMock(spec=PipelineSettings)

    pipeline_config.max_prompt_tokens = 1000  # Should be ignored
    pipeline_config.use_full_context_window = True

    config.pipeline = pipeline_config

    # Full context window constant in code is 1_048_576
    full_context_window_size = 1_048_576
    expected_size = int(
        (full_context_window_size * PipelineDefaults.BUFFER_RATIO) / PipelineDefaults.AVG_TOKENS_PER_MESSAGE
    )

    assert _calculate_max_window_size(config) == expected_size
