from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from egregora.data_primitives.protocols import OutputSink
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.exceptions import (
    CommandProcessingError,
    MaxSplitDepthError,
    MediaPersistenceError,
    OutputSinkError,
    ProfileGenerationError,
    WindowValidationError,
)
from egregora.orchestration.runner import PipelineRunner


@pytest.fixture
def mock_create_writer_resources():
    with patch("egregora.orchestration.runner.PipelineFactory.create_writer_resources") as mock:
        yield mock


def test_pipeline_runner_init():
    context = MagicMock(spec=PipelineContext)
    runner = PipelineRunner(context)
    assert runner.context == context


def test_pipeline_runner_process_windows():
    context = MagicMock(spec=PipelineContext)
    # Mock output_format (OutputSink)
    output_sink = MagicMock(spec=OutputSink)
    context.output_format = output_sink

    # Mock config
    config = MagicMock()
    config.pipeline.max_windows = 1
    config.pipeline.max_prompt_tokens = 1000
    context.config = config

    runner = PipelineRunner(context)

    # Create a mock window
    window = MagicMock()
    window.size = 10
    # Use real datetime objects to avoid formatting issues
    window.start_time = datetime(2023, 1, 1, 10, 0)
    window.end_time = datetime(2023, 1, 2, 10, 0)
    window.window_index = 0

    windows_iterator = [window]

    # Mock internal methods to avoid complex dependency mocking
    # Note: _process_single_window returns a dict of results
    runner._process_single_window = MagicMock(return_value={"test_window": {"posts": ["post1"]}})

    # Mock process_background_tasks to simply return (it is tested via its dependencies in other tests, or we should mock the workers if we want to test its logic, but here we test the loop)
    # Actually, in the test I was trying to mock `_process_background_tasks` but I renamed it to `process_background_tasks`.
    runner.process_background_tasks = MagicMock()

    results, max_ts = runner.process_windows(windows_iterator)
    assert results == {"test_window": {"posts": ["post1"]}}
    assert max_ts == datetime(2023, 1, 2, 10, 0)

    runner.process_background_tasks.assert_called()


def test_validate_window_size_raises_exception():
    context = MagicMock(spec=PipelineContext)
    runner = PipelineRunner(context)
    window = MagicMock()
    window.size = 100
    window.window_index = 1
    max_size = 50
    with pytest.raises(WindowValidationError) as excinfo:
        runner._validate_window_size(window, max_size)
    assert "Window 1 failed validation" in str(excinfo.value)


def test_process_window_with_auto_split_raises_max_depth_error():
    context = MagicMock(spec=PipelineContext)
    runner = PipelineRunner(context)
    window = MagicMock()
    window.start_time = datetime(2023, 1, 1)
    window.end_time = datetime(2023, 1, 1, 1)
    window.size = 10

    with pytest.raises(MaxSplitDepthError) as excinfo:
        runner._process_window_with_auto_split(window, depth=5, max_depth=5)
    assert "Max split depth of 5 reached" in str(excinfo.value)


def test_process_single_window_raises_output_sink_error():
    context = MagicMock(spec=PipelineContext)
    context.output_format = None
    runner = PipelineRunner(context)
    window = MagicMock()
    window.start_time = datetime(2023, 1, 1)
    window.end_time = datetime(2023, 1, 1, 1)

    with pytest.raises(OutputSinkError) as excinfo:
        runner._process_single_window(window)
    assert "Output adapter must be initialized" in str(excinfo.value)


@patch("egregora.orchestration.runner.process_media_for_window")
def test_enrich_window_data_raises_media_persistence_error(mock_process_media):
    context = MagicMock(spec=PipelineContext)
    output_sink = MagicMock(spec=OutputSink)
    output_sink.persist.side_effect = OSError("Disk full")
    context.output_format = output_sink
    context.enable_enrichment = False
    runner = PipelineRunner(context)
    window = MagicMock()
    media_doc = MagicMock()
    media_doc.document_id = "media.jpg"
    mock_process_media.return_value = (MagicMock(), {"media.jpg": media_doc})

    with pytest.raises(MediaPersistenceError) as excinfo:
        runner._enrich_window_data(window, output_sink)
    assert "Failed to persist media file 'media.jpg'" in str(excinfo.value)


@patch("egregora.orchestration.runner.extract_commands_list")
@patch("egregora.orchestration.runner.command_to_announcement")
def test_handle_commands_raises_command_processing_error(mock_command_to_announcement, mock_extract_commands):
    context = MagicMock(spec=PipelineContext)
    output_sink = MagicMock(spec=OutputSink)
    runner = PipelineRunner(context)
    messages = [{"text": "/cmd"}]
    mock_extract_commands.return_value = messages
    mock_command_to_announcement.side_effect = ValueError("Invalid command")

    with pytest.raises(CommandProcessingError) as excinfo:
        runner._handle_commands(messages, output_sink)
    assert "Failed to process command '/cmd'" in str(excinfo.value)


@pytest.mark.usefixtures("mock_create_writer_resources")
@patch("egregora.orchestration.runner.asyncio.run")
def test_generate_posts_and_profiles_raises_profile_generation_error(mock_asyncio_run):
    context = MagicMock(spec=PipelineContext)
    output_sink = MagicMock(spec=OutputSink)
    runner = PipelineRunner(context)
    window = MagicMock()
    window.start_time = datetime(2023, 1, 1)
    mock_asyncio_run.side_effect = [
        {"posts": [], "profiles": []},  # write_posts_for_window
        ValueError("Failed to generate"),  # generate_profile_posts
    ]
    runner._extract_adapter_info = MagicMock(return_value=("", ""))

    with pytest.raises(ProfileGenerationError):
        runner._generate_posts_and_profiles(MagicMock(), [], window, output_sink)


@patch("egregora.orchestration.runner.process_media_for_window")
@patch("egregora.orchestration.runner.extract_commands_list")
@patch("egregora.orchestration.runner.command_to_announcement")
@patch("egregora.orchestration.runner.filter_commands")
@patch("egregora.orchestration.runner.asyncio.run")
def test_process_single_window_orchestration(
    mock_asyncio_run,
    mock_filter_commands,
    mock_command_to_announcement,
    mock_extract_commands,
    mock_process_media,
):
    # Arrange
    context = MagicMock(spec=PipelineContext)
    context.output_format = MagicMock(spec=OutputSink)
    context.url_context = None
    context.enable_enrichment = False
    context.config.pipeline.is_demo = False
    context.run_id = "test-run"
    context.config_obj.is_demo = False
    runner = PipelineRunner(context)

    window = MagicMock()
    window.start_time = datetime(2023, 1, 1)
    window.end_time = datetime(2023, 1, 1, 1)
    window.table = MagicMock()
    window.size = 10

    mock_table = MagicMock()
    mock_table.execute.return_value.to_pylist.return_value = [{"id": 1, "text": "/cmd"}]
    mock_process_media.return_value = (mock_table, {"media.jpg": MagicMock()})

    mock_extract_commands.return_value = [{"id": 1, "text": "/cmd"}]
    mock_command_to_announcement.return_value = MagicMock()
    mock_filter_commands.return_value = [{"id": 2, "text": "not a command"}]

    # Mock the two async calls
    mock_asyncio_run.side_effect = [
        {"posts": ["post1"], "profiles": []},  # write_posts_for_window
        [MagicMock()],  # generate_profile_posts
    ]

    runner._extract_adapter_info = MagicMock(return_value=("summary", "instructions"))

    # Act
    window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
    result = runner._process_single_window(window, depth=0)

    # Assert
    assert window_label in result
    window_result = result[window_label]
    assert window_result["posts"] == ["post1"]
    assert len(window_result["profiles"]) == 1  # from generate_profile_posts

    mock_process_media.assert_called_once()
    # one for media, one for announcement, one for profile
    assert context.output_format.persist.call_count == 3

    mock_extract_commands.assert_called_once()
    mock_command_to_announcement.assert_called_once()
    mock_filter_commands.assert_called_once()
    assert mock_asyncio_run.call_count == 2
