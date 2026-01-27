from datetime import datetime
from unittest.mock import MagicMock

from egregora.data_primitives.document import OutputSink
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.runner import PipelineRunner


def test_fetch_processed_intervals():
    """Test fetching processed intervals from journal documents."""
    context = MagicMock(spec=PipelineContext)
    # Mock library.journal.list() - journals are dictionaries with document fields
    mock_journal1 = {"window_start": "2023-01-01T10:00:00", "window_end": "2023-01-01T12:00:00"}
    mock_journal2 = {}  # Missing metadata should be ignored

    context.library.journal.list.return_value = [mock_journal1, mock_journal2]

    runner = PipelineRunner(context)
    intervals = runner._fetch_processed_intervals()

    assert len(intervals) == 1
    assert ("2023-01-01T10:00:00", "2023-01-01T12:00:00") in intervals


def test_process_windows_skips_existing():
    """Test that process_windows skips windows that match processed intervals."""
    context = MagicMock(spec=PipelineContext)
    # Mock OutputSink to avoid validation errors
    context.output_format = MagicMock(spec=OutputSink)

    # Mock config to avoid type error on max_windows
    config = MagicMock()
    config.pipeline.max_windows = 100
    context.config = config

    # Mock processed intervals (via library) - journals are dictionaries
    mock_journal = {"window_start": "2023-01-01T10:00:00", "window_end": "2023-01-01T12:00:00"}
    context.library.journal.list.return_value = [mock_journal]

    runner = PipelineRunner(context)
    # Mock internal processing to avoid complex setup
    runner._process_single_window = MagicMock(return_value={})
    runner.process_background_tasks = MagicMock()

    # Define windows
    # Window 1: Matches journal -> Should be skipped
    window1 = MagicMock()
    window1.start_time = datetime(2023, 1, 1, 10, 0, 0)
    window1.end_time = datetime(2023, 1, 1, 12, 0, 0)
    window1.window_index = 0
    window1.size = 10

    # Window 2: New -> Should be processed
    window2 = MagicMock()
    window2.start_time = datetime(2023, 1, 1, 12, 0, 0)
    window2.end_time = datetime(2023, 1, 1, 14, 0, 0)
    window2.window_index = 1
    window2.size = 10

    windows = [window1, window2]

    _results, _max_ts = runner.process_windows(iter(windows))

    # Assertions
    # Only window 2 should trigger processing
    assert runner._process_single_window.call_count == 1
    # Verify call args to ensure it was window2
    args, _ = runner._process_single_window.call_args
    assert args[0] == window2
