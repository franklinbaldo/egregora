from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from egregora.data_primitives.document import Document, OutputSink
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.pipelines.etl.preparation import Conversation
from egregora.orchestration.pipelines.write import process_item


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PipelineContext)
    ctx.output_sink = MagicMock(spec=OutputSink)
    ctx.config = MagicMock()
    ctx.config.models.writer = "test-model"
    ctx.run_id = "test-run"
    ctx.site_root = Path("/tmp/site")
    ctx.cache = MagicMock()
    return ctx


@pytest.fixture
def mock_conversation(mock_context):
    conv = MagicMock(spec=Conversation)
    conv.context = mock_context
    conv.window = MagicMock()
    conv.window.start_time = datetime(2023, 1, 1, 10, 0)
    conv.window.end_time = datetime(2023, 1, 1, 11, 0)

    # Mock messages_table execution
    conv.messages_table = MagicMock()
    # Mock to_pylist behavior
    conv.messages_table.execute.return_value.to_pylist.return_value = [{"id": 1, "text": "hello"}]

    conv.adapter_info = ("summary", "instructions")
    return conv


@patch("egregora.orchestration.pipelines.write.build_conversation_xml")
@patch("egregora.orchestration.pipelines.write.PromptManager")
@patch("egregora.orchestration.pipelines.write.generate_window_signature")
@patch("egregora.orchestration.pipelines.write.window_already_processed")
@patch("egregora.orchestration.pipelines.write.create_journal_document")
@patch("egregora.orchestration.pipelines.write.write_posts_for_window")
@patch("egregora.orchestration.pipelines.write.generate_profile_posts")
@patch("egregora.orchestration.pipelines.write.process_background_tasks")
@patch("egregora.orchestration.pipelines.write.extract_commands_list")
@patch("egregora.orchestration.pipelines.write.filter_commands")
def test_process_item_skips_processed_window(
    mock_filter,
    mock_extract,
    mock_bg_tasks,
    mock_gen_profiles,
    mock_write_posts,
    mock_create_journal,
    mock_window_processed,
    mock_gen_signature,
    mock_prompt_manager,
    mock_build_xml,
    mock_conversation,
):
    # Setup
    mock_build_xml.return_value = "<xml>"
    mock_prompt_manager.get_template_content.return_value = "template"
    mock_gen_signature.return_value = "sig123"

    # Condition: Window ALREADY processed
    mock_window_processed.return_value = True

    # Execute
    result = process_item(mock_conversation)

    # Verify
    assert result == {}

    # Check checks happened
    mock_window_processed.assert_called_once_with(mock_conversation.context.output_sink, "sig123")

    # Ensure downstream logic was SKIPPED
    mock_write_posts.assert_not_called()
    mock_create_journal.assert_not_called()
    mock_conversation.context.output_sink.persist.assert_not_called()


@patch("egregora.orchestration.pipelines.write.build_conversation_xml")
@patch("egregora.orchestration.pipelines.write.PromptManager")
@patch("egregora.orchestration.pipelines.write.generate_window_signature")
@patch("egregora.orchestration.pipelines.write.window_already_processed")
@patch("egregora.orchestration.pipelines.write.create_journal_document")
@patch("egregora.orchestration.pipelines.write.write_posts_for_window")
@patch("egregora.orchestration.pipelines.write.generate_profile_posts")
@patch("egregora.orchestration.pipelines.write.process_background_tasks")
@patch("egregora.orchestration.pipelines.write.extract_commands_list")
@patch("egregora.orchestration.pipelines.write.filter_commands")
def test_process_item_persists_journal_on_success(
    mock_filter,
    mock_extract,
    mock_bg_tasks,
    mock_gen_profiles,
    mock_write_posts,
    mock_create_journal,
    mock_window_processed,
    mock_gen_signature,
    mock_prompt_manager,
    mock_build_xml,
    mock_conversation,
):
    # Setup
    mock_build_xml.return_value = "<xml>"
    mock_prompt_manager.get_template_content.return_value = "template"
    mock_gen_signature.return_value = "sig123"

    # Condition: Window NOT processed
    mock_window_processed.return_value = False

    # Mocks for execution
    mock_extract.return_value = []  # No commands
    mock_filter.return_value = [{"id": 1, "text": "hello"}]
    mock_write_posts.return_value = {"posts": ["post1"], "profiles": []}
    mock_gen_profiles.return_value = []

    # Mock Journal Creation
    mock_journal_doc = MagicMock(spec=Document)
    mock_create_journal.return_value = mock_journal_doc

    # Execute
    result = process_item(mock_conversation)

    # Verify
    assert "posts" in next(iter(result.values()))

    # Check checks happened
    mock_window_processed.assert_called_once_with(mock_conversation.context.output_sink, "sig123")

    # Ensure logic EXECUTED
    mock_write_posts.assert_called_once()

    # Ensure Journal Created and Persisted
    mock_create_journal.assert_called_once_with(
        signature="sig123",
        run_id="test-run",
        window_start=mock_conversation.window.start_time,
        window_end=mock_conversation.window.end_time,
        model="test-model",
        posts_generated=1,
        profiles_updated=0,
    )

    # Check persist calls
    # Should persist journal (posts are strings in this mock, so skipped by hasattr check)
    persist_calls = mock_conversation.context.output_sink.persist.call_args_list
    assert len(persist_calls) >= 1

    # Verify journal persistence specifically
    assert any(call.args[0] == mock_journal_doc for call in persist_calls)
