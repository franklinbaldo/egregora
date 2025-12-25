from datetime import datetime
from unittest.mock import MagicMock, patch

from egregora.data_primitives.protocols import OutputSink
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.runner import PipelineRunner


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
