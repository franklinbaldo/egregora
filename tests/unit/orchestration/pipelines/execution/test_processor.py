import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from egregora.orchestration.pipelines.execution.processor import process_item
from egregora.orchestration.pipelines.etl.preparation import Conversation
from egregora.orchestration.context import PipelineContext
from egregora.transformations import Window
from egregora.data_primitives.document import Document

@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PipelineContext)
    ctx.config = MagicMock()
    ctx.cache = MagicMock()
    ctx.state = MagicMock()
    ctx.state.smoke_test = False
    ctx.run_id = "test-run-id"
    ctx.output_sink = MagicMock()
    return ctx

@pytest.fixture
def mock_window():
    window = MagicMock(spec=Window)
    window.start_time = datetime(2023, 1, 1, 10, 0)
    window.end_time = datetime(2023, 1, 1, 11, 0)
    return window

@pytest.fixture
def mock_messages_table():
    table = MagicMock()
    # Mock execute() to return a list of dicts directly or an object with to_pylist
    executed = MagicMock()
    executed.to_pylist.return_value = [
        {
            "role": "user",
            "content": "Hello",
            "author": "Alice",
            "ts": datetime(2023, 1, 1, 10, 5),
            "event_id": "event1",
            "author_uuid": "uuid1"
        },
        {
            "role": "user",
            "content": "/egregora command",
            "author": "Bob",
            "ts": datetime(2023, 1, 1, 10, 6),
            "event_id": "event2",
            "author_uuid": "uuid2"
        }
    ]
    table.execute.return_value = executed
    return table

@pytest.fixture
def mock_conversation(mock_context, mock_window, mock_messages_table):
    return Conversation(
        window=mock_window,
        messages_table=mock_messages_table,
        media_mapping={},
        context=mock_context,
        adapter_info=("Summary", "Instructions"),
        depth=0
    )

@patch("egregora.orchestration.pipelines.execution.processor.write_posts_for_window")
@patch("egregora.orchestration.pipelines.execution.processor.generate_profile_posts")
@patch("egregora.orchestration.pipelines.execution.processor.process_background_tasks")
@patch("egregora.orchestration.pipelines.execution.processor.extract_commands_list")
@patch("egregora.orchestration.pipelines.execution.processor.command_to_announcement")
@patch("egregora.orchestration.pipelines.execution.processor.PipelineFactory")
def test_process_item_success(
    mock_factory,
    mock_command_to_announcement,
    mock_extract_commands,
    mock_bg_tasks,
    mock_gen_profiles,
    mock_write_posts,
    mock_conversation
):
    # Setup mocks
    mock_extract_commands.return_value = [{"role": "user", "content": "/egregora command"}]
    mock_command_to_announcement.return_value = MagicMock(spec=Document)

    mock_write_posts.return_value = {
        "posts": [MagicMock(spec=Document, document_id="post1")],
        "profiles": ["profile1"]
    }

    mock_gen_profiles.return_value = [MagicMock(spec=Document, document_id="profile2")]

    # Run
    result = process_item(mock_conversation)

    # Assertions
    assert len(result) == 1
    window_label = list(result.keys())[0]
    assert "posts" in result[window_label]
    assert "profiles" in result[window_label]

    # Check announcements were processed
    mock_command_to_announcement.assert_called()
    mock_conversation.context.output_sink.persist.assert_called()

    # Check writer was called
    mock_write_posts.assert_called_once()

    # Check profile generator was called
    mock_gen_profiles.assert_called_once()

    # Check background tasks
    mock_bg_tasks.assert_called_once()

@patch("egregora.orchestration.pipelines.execution.processor.write_posts_for_window")
@patch("egregora.orchestration.pipelines.execution.processor.generate_profile_posts")
@patch("egregora.orchestration.pipelines.execution.processor.process_background_tasks")
def test_process_item_empty_messages(
    mock_bg_tasks,
    mock_gen_profiles,
    mock_write_posts,
    mock_conversation
):
    # Setup empty messages
    mock_conversation.messages_table.execute.return_value.to_pylist.return_value = []

    mock_write_posts.return_value = {"posts": [], "profiles": []}
    mock_gen_profiles.return_value = []

    result = process_item(mock_conversation)

    # Should run without error but produce empty results
    assert len(result) == 1
    val = list(result.values())[0]
    assert val["posts"] == []
    assert val["profiles"] == []

    mock_bg_tasks.assert_called_once()
