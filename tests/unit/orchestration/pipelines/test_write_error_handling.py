from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from egregora.orchestration.context import PipelineContext
from egregora.orchestration.pipelines.write import process_item


@pytest.fixture
def mock_conversation():
    ctx = MagicMock(spec=PipelineContext)
    # Ensure error_boundary is a Mock, not None
    ctx.error_boundary = MagicMock()
    ctx.output_sink = MagicMock()

    conversation = MagicMock()
    conversation.context = ctx
    conversation.window = MagicMock()
    # Use real datetime objects for formatting to work
    conversation.window.start_time = datetime(2024, 1, 1, 10, 0)
    conversation.window.end_time = datetime(2024, 1, 1, 12, 0)

    return conversation


@patch("egregora.orchestration.pipelines.write.convert_ibis_table_to_list")
@patch("egregora.orchestration.pipelines.write._check_window_processed")
@patch("egregora.orchestration.pipelines.write._process_commands")
@patch("egregora.orchestration.pipelines.write._prepare_messages")
@patch("egregora.orchestration.pipelines.write._run_writer_agent")
@patch("egregora.orchestration.pipelines.write._run_profile_agent")
@patch("egregora.orchestration.pipelines.write.process_background_tasks")
@patch("egregora.orchestration.pipelines.write._persist_journal_entry")
def test_process_item_delegates_command_error(
    mock_persist,
    mock_bg,
    mock_profile,
    mock_writer,
    mock_prep,
    mock_cmd,
    mock_check,
    mock_convert,
    mock_conversation,
):
    mock_convert.return_value = []
    mock_check.return_value = (False, "sig")
    mock_prep.return_value = ([], [])
    mock_writer.return_value = ([], [])
    mock_profile.return_value = []

    # Simulate error
    error = ValueError("Command failed")
    mock_cmd.side_effect = error

    process_item(mock_conversation)

    mock_conversation.context.error_boundary.handle_command_error.assert_called_once()
    args, _ = mock_conversation.context.error_boundary.handle_command_error.call_args
    assert args[0] == error


@patch("egregora.orchestration.pipelines.write.convert_ibis_table_to_list")
@patch("egregora.orchestration.pipelines.write._check_window_processed")
@patch("egregora.orchestration.pipelines.write._process_commands")
@patch("egregora.orchestration.pipelines.write._prepare_messages")
@patch("egregora.orchestration.pipelines.write._run_writer_agent")
@patch("egregora.orchestration.pipelines.write._run_profile_agent")
@patch("egregora.orchestration.pipelines.write.process_background_tasks")
@patch("egregora.orchestration.pipelines.write._persist_journal_entry")
def test_process_item_delegates_writer_error(
    mock_persist,
    mock_bg,
    mock_profile,
    mock_writer,
    mock_prep,
    mock_cmd,
    mock_check,
    mock_convert,
    mock_conversation,
):
    mock_convert.return_value = []
    mock_check.return_value = (False, "sig")
    mock_prep.return_value = ([], [])
    mock_profile.return_value = []

    # Simulate error
    error = ValueError("Writer failed")
    mock_writer.side_effect = error

    process_item(mock_conversation)

    mock_conversation.context.error_boundary.handle_writer_error.assert_called_once()
    args, _ = mock_conversation.context.error_boundary.handle_writer_error.call_args
    assert args[0] == error


@patch("egregora.orchestration.pipelines.write.convert_ibis_table_to_list")
@patch("egregora.orchestration.pipelines.write._check_window_processed")
@patch("egregora.orchestration.pipelines.write._process_commands")
@patch("egregora.orchestration.pipelines.write._prepare_messages")
@patch("egregora.orchestration.pipelines.write._run_writer_agent")
@patch("egregora.orchestration.pipelines.write._run_profile_agent")
@patch("egregora.orchestration.pipelines.write.process_background_tasks")
@patch("egregora.orchestration.pipelines.write._persist_journal_entry")
def test_process_item_delegates_enrichment_error(
    mock_persist,
    mock_bg,
    mock_profile,
    mock_writer,
    mock_prep,
    mock_cmd,
    mock_check,
    mock_convert,
    mock_conversation,
):
    mock_convert.return_value = []
    mock_check.return_value = (False, "sig")
    mock_prep.return_value = ([], [])
    mock_writer.return_value = ([], [])
    mock_profile.return_value = []

    # Simulate error
    error = ValueError("Enrichment failed")
    mock_bg.side_effect = error

    process_item(mock_conversation)

    mock_conversation.context.error_boundary.handle_enrichment_error.assert_called_once()
    args, _ = mock_conversation.context.error_boundary.handle_enrichment_error.call_args
    assert args[0] == error
