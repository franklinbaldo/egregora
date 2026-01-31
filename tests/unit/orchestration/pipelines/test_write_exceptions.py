from unittest.mock import MagicMock, patch

import pytest

from egregora.data_primitives.document import Document
from egregora.input_adapters.exceptions import UnknownAdapterError
from egregora.orchestration.context import PipelineRunParams
from egregora.orchestration.exceptions import (
    CommandAnnouncementError,
    OutputSinkError,
    ProfileGenerationError,
)
from egregora.orchestration.pipelines.write import process_item, run


@pytest.fixture
def mock_conversation():
    conversation = MagicMock()
    conversation.context = MagicMock()
    conversation.window = MagicMock()
    conversation.messages_table = MagicMock()

    # Mock messages table execution to return a list
    # The code tries execute().to_pylist() or to_dict() or just to_pylist()
    # We mock the first one to succeed
    conversation.messages_table.execute.return_value.to_pylist.return_value = []

    return conversation


def test_process_item_raises_command_announcement_error(mock_conversation):
    # Setup
    with (
        patch("egregora.orchestration.pipelines.write.extract_commands_list", return_value=[{"cmd": "test"}]),
        patch(
            "egregora.orchestration.pipelines.write.command_to_announcement",
            side_effect=ValueError("Command failed"),
        ),
    ):
        # Verify
        with pytest.raises(CommandAnnouncementError, match="Failed to generate announcement"):
            process_item(mock_conversation)


def test_process_item_raises_output_sink_error_on_post_persist(mock_conversation):
    # Setup
    mock_post = MagicMock(spec=Document)
    mock_post.document_id = "test_doc"

    # Mock write_posts_for_window to return a post
    with (
        patch(
            "egregora.orchestration.pipelines.write.write_posts_for_window",
            return_value={"posts": [mock_post]},
        ),
        patch("egregora.orchestration.pipelines.write.extract_commands_list", return_value=[]),
        patch("egregora.orchestration.pipelines.write.filter_commands", return_value=[]),
        patch("egregora.orchestration.pipelines.write.WriterResources.from_pipeline_context"),
    ):
        # Mock output_sink.persist to fail
        mock_conversation.context.output_sink.persist.side_effect = OSError("Disk full")

        # Verify
        with pytest.raises(OutputSinkError, match="Failed to persist post"):
            process_item(mock_conversation)


def test_process_item_raises_profile_generation_error(mock_conversation):
    # Setup
    with (
        patch("egregora.orchestration.pipelines.write.write_posts_for_window", return_value={"posts": []}),
        patch("egregora.orchestration.pipelines.write.extract_commands_list", return_value=[]),
        patch("egregora.orchestration.pipelines.write.filter_commands", return_value=[]),
        patch("egregora.orchestration.pipelines.write.WriterResources.from_pipeline_context"),
        patch(
            "egregora.orchestration.pipelines.write.generate_profile_posts",
            side_effect=RuntimeError("Profile generation failed"),
        ),
    ):
        # Verify
        with pytest.raises(ProfileGenerationError, match="Failed to generate profile posts"):
            process_item(mock_conversation)


@patch("egregora.orchestration.pipelines.write.ADAPTER_REGISTRY", {})
def test_run_raises_unknown_adapter_error():
    run_params = MagicMock(spec=PipelineRunParams)
    run_params.source_type = "non_existent_adapter"

    # Currently run() raises ValueError, we want UnknownAdapterError
    # This test will fail if run() raises ValueError
    with pytest.raises(UnknownAdapterError, match="Unknown adapter source"):
        run(run_params)
