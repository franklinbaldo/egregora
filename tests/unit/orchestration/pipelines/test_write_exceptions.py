from datetime import datetime
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

    # Use real datetimes to support f-string formatting in process_item
    conversation.window.start_time = datetime(2023, 1, 1, 10, 0)
    conversation.window.end_time = datetime(2023, 1, 1, 11, 0)

    conversation.messages_table = MagicMock()
    conversation.messages_table.execute.return_value.to_pylist.return_value = []

    conversation.context.error_boundary = MagicMock()

    return conversation


def test_process_item_handles_command_announcement_error(mock_conversation):
    # Setup
    # Ensure error_boundary is a mock to verify the call
    mock_conversation.context.error_boundary = MagicMock()

    with (
        patch("egregora.orchestration.pipelines.write.extract_commands_list", return_value=[{"cmd": "test"}]),
        patch(
            "egregora.orchestration.pipelines.write.command_to_announcement",
            side_effect=ValueError("Command failed"),
        ),
        # We need to mock _run_writer_agent to avoid it running and causing side effects
        patch("egregora.orchestration.pipelines.write._run_writer_agent", return_value=([], [])),
        # Mock profile generation to avoid it running
        patch("egregora.orchestration.pipelines.write._run_profile_agent", return_value=[]),
        # Mock background tasks
        patch("egregora.orchestration.pipelines.write.process_background_tasks"),
    ):
        # Act
        process_item(mock_conversation)

        # Verify that the error was caught and handled, NOT raised
        mock_conversation.context.error_boundary.handle_command_error.assert_called_once()
        # Verify the exception passed was correct (wrapped in CommandAnnouncementError or original ValueError?
        # The code catches Exception and calls handle_command_error(e).
        # In _process_commands, it re-raises as CommandAnnouncementError.
        args, _ = mock_conversation.context.error_boundary.handle_command_error.call_args
        assert isinstance(args[0], CommandAnnouncementError)
        assert "Command failed" in str(args[0])


def test_process_item_raises_output_sink_error_on_post_persist(mock_conversation):
    # Setup
    # Use DefaultErrorBoundary behavior which RAISES for writer errors
    mock_conversation.context.error_boundary = None

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


def test_process_item_handles_profile_generation_error(mock_conversation):
    # Setup
    # Ensure error_boundary is a mock to verify the call
    mock_conversation.context.error_boundary = MagicMock()

    with (
        patch("egregora.orchestration.pipelines.write.write_posts_for_window", return_value={"posts": []}),
        patch("egregora.orchestration.pipelines.write.extract_commands_list", return_value=[]),
        patch("egregora.orchestration.pipelines.write.filter_commands", return_value=[]),
        patch("egregora.orchestration.pipelines.write.WriterResources.from_pipeline_context"),
        patch(
            "egregora.orchestration.pipelines.write.generate_profile_posts",
            side_effect=RuntimeError("Profile generation failed"),
        ),
        # Mock background tasks
        patch("egregora.orchestration.pipelines.write.process_background_tasks"),
    ):
        # Act
        process_item(mock_conversation)

        # Verify that the error was caught and handled, NOT raised
        mock_conversation.context.error_boundary.handle_profile_error.assert_called_once()

        args, _ = mock_conversation.context.error_boundary.handle_profile_error.call_args
        assert isinstance(args[0], ProfileGenerationError)
        assert "Profile generation failed" in str(args[0])


@patch("egregora.orchestration.pipelines.write.ADAPTER_REGISTRY", {})
def test_run_raises_unknown_adapter_error():
    run_params = MagicMock(spec=PipelineRunParams)
    run_params.source_type = "non_existent_adapter"

    # Currently run() raises ValueError, we want UnknownAdapterError
    # This test will fail if run() raises ValueError
    with pytest.raises(UnknownAdapterError, match="Unknown adapter source"):
        run(run_params)
