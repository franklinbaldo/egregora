"""Tests for write.py exception handling."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from egregora.orchestration.pipelines.write import run, process_item, PipelineRunParams
from egregora.orchestration.exceptions import ProfileGenerationError
from egregora.input_adapters.exceptions import UnknownAdapterError
from egregora.orchestration.context import PipelineContext
from egregora.config.settings import EgregoraConfig

@patch("egregora.orchestration.pipelines.write.ADAPTER_REGISTRY")
def test_run_raises_unknown_adapter_error(mock_registry):
    """Test that run raises UnknownAdapterError when source type is not in registry."""
    mock_registry.get.return_value = None
    mock_registry.keys.return_value = ["whatsapp"]

    params = MagicMock(spec=PipelineRunParams)
    params.source_type = "invalid_source"

    with pytest.raises(UnknownAdapterError) as excinfo:
        run(params)

    assert "Unknown adapter source: 'invalid_source'" in str(excinfo.value)
    assert "Available: whatsapp" in str(excinfo.value)

@patch("egregora.orchestration.pipelines.write.generate_profile_posts")
@patch("egregora.orchestration.pipelines.write.extract_commands_list")
@patch("egregora.orchestration.pipelines.write.filter_commands")
@patch("egregora.orchestration.pipelines.write.write_posts_for_window")
@patch("egregora.orchestration.pipelines.write.process_background_tasks")
@patch("egregora.orchestration.pipelines.write.WriterResources")
def test_process_item_raises_profile_error(
    mock_resources, mock_bg, mock_write, mock_filter, mock_extract, mock_generate
):
    """Test that process_item raises ProfileGenerationError when profile generation fails."""

    # Setup mocks
    mock_extract.return_value = []
    mock_filter.return_value = [{"event_id": "1", "ts": 1, "author_uuid": "a"}]
    mock_write.return_value = {"posts": [], "profiles": []}

    # Mock conversation
    conversation = MagicMock()
    conversation.messages_table.execute.return_value = MagicMock(to_pylist=lambda: [])
    conversation.window.start_time = datetime(2025, 1, 1, 10, 0)
    conversation.window.end_time = datetime(2025, 1, 1, 12, 0)

    # Context
    ctx = MagicMock(spec=PipelineContext)
    conversation.context = ctx

    # Simulate profile generation failure
    mock_generate.side_effect = Exception("Profile gen failed")

    with pytest.raises(ProfileGenerationError) as excinfo:
        process_item(conversation)

    assert "Failed to generate profile posts" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, Exception)
