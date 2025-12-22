from unittest.mock import MagicMock, Mock
import pytest
from datetime import datetime
from egregora.orchestration.runner import PipelineRunner
from egregora.orchestration.context import PipelineContext
from egregora.data_primitives.protocols import OutputSink

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
