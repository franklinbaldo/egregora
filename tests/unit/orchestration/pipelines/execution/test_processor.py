from unittest.mock import MagicMock, patch

import pytest
from egregora.orchestration.pipelines.execution.processor import process_item
from egregora.data_primitives.document import Document

@pytest.fixture
def mock_conversation():
    conversation = MagicMock()
    conversation.context = MagicMock()
    conversation.window.start_time.strftime.return_value = "2023-01-01"
    conversation.window.start_time = MagicMock()
    conversation.window.end_time = MagicMock()
    # Mock date formatting
    conversation.window.start_time.__format__ = lambda self, fmt: "2023-01-01 12:00"
    conversation.window.end_time.__format__ = lambda self, fmt: "13:00"

    # Mock messages table
    mock_msg = {
        "text": "hello",
        "sender": "user",
        "event_id": "1",
        "ts": "2023-01-01 12:00:00",
        "author_uuid": "user1"
    }
    conversation.messages_table.to_pylist.return_value = [mock_msg]
    return conversation

@patch("egregora.orchestration.pipelines.execution.processor.write_posts_for_window")
@patch("egregora.orchestration.pipelines.execution.processor.generate_profile_posts")
@patch("egregora.orchestration.pipelines.execution.processor.extract_commands_list")
@patch("egregora.orchestration.pipelines.execution.processor.filter_commands")
@patch("egregora.orchestration.pipelines.execution.processor.PipelineFactory")
@patch("egregora.orchestration.pipelines.execution.processor.process_background_tasks")
def test_process_item_flow(
    mock_bg_tasks,
    mock_factory,
    mock_filter,
    mock_extract,
    mock_gen_profiles,
    mock_write_posts,
    mock_conversation
):
    # Setup mocks
    mock_extract.return_value = []
    mock_msg = {
        "text": "hello",
        "sender": "user",
        "event_id": "1",
        "ts": "2023-01-01 12:00:00",
        "author_uuid": "user1"
    }
    mock_filter.return_value = [mock_msg]

    # Mock writer result
    mock_post = MagicMock()
    mock_post.document_id = "post1"
    mock_write_posts.return_value = {
        "posts": [mock_post],
        "profiles": []
    }

    # Mock profile generator result
    mock_profile = MagicMock()
    mock_profile.document_id = "profile1"
    mock_gen_profiles.return_value = [mock_profile]

    # Run
    result = process_item(mock_conversation)

    # Assertions
    # Check return structure
    assert result is not None
    key = list(result.keys())[0]
    assert "posts" in result[key]
    assert "profiles" in result[key]

    # Check persistence called
    output_sink = mock_conversation.context.output_sink
    assert output_sink.persist.call_count >= 2 # 1 post + 1 profile

    # Verify calls
    mock_write_posts.assert_called_once()
    mock_gen_profiles.assert_called_once()
    mock_bg_tasks.assert_called_once()

@patch("egregora.orchestration.pipelines.execution.processor.extract_commands_list")
@patch("egregora.orchestration.pipelines.execution.processor.command_to_announcement")
def test_process_item_announcements(
    mock_cmd_to_ann,
    mock_extract,
    mock_conversation
):
    # Setup mocks to simulate a command
    mock_extract.return_value = [{"text": "/announce something"}]
    mock_announcement = MagicMock()
    mock_cmd_to_ann.return_value = mock_announcement

    # Mock other dependencies to avoid errors
    with patch("egregora.orchestration.pipelines.execution.processor.write_posts_for_window") as mock_write:
        mock_write.return_value = {}
        with patch("egregora.orchestration.pipelines.execution.processor.generate_profile_posts") as mock_gen:
            mock_gen.return_value = []
            with patch("egregora.orchestration.pipelines.execution.processor.filter_commands") as mock_filter:
                mock_filter.return_value = []
                with patch("egregora.orchestration.pipelines.execution.processor.PipelineFactory"):
                    with patch("egregora.orchestration.pipelines.execution.processor.process_background_tasks"):
                        process_item(mock_conversation)

    # Verify announcement generation and persistence
    output_sink = mock_conversation.context.output_sink
    output_sink.persist.assert_any_call(mock_announcement)
