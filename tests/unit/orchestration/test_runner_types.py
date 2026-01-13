
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import pytest

from egregora.orchestration.runner import PipelineRunner

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime
    from egregora.orchestration.context import PipelineContext
    from egregora.transformations.windowing import Window


@pytest.fixture
def mock_context() -> PipelineContext:
    """Provides a mocked PipelineContext."""
    context = MagicMock()
    context.config.pipeline.max_windows = 1
    context.config.pipeline.use_full_context_window = False
    context.config.pipeline.max_prompt_tokens = 1024
    context.library = None
    context.output_sink = None
    context.run_id = "test-run"
    return context


@pytest.fixture
def mock_window_iterator() -> Iterator[Window]:
    """Provides a mocked iterator of Window objects."""
    window = MagicMock(name="WindowMock")
    window.size = 10
    window.window_index = 0
    window.start_time = Mock(spec=datetime)
    window.end_time = Mock(spec=datetime)
    window.start_time.isoformat.return_value = "2024-01-01T00:00:00"
    window.end_time.isoformat.return_value = "2024-01-01T01:00:00"
    return iter([window])


def test_pipeline_runner_accepts_window_iterator(
    mock_context: PipelineContext, mock_window_iterator: Iterator[Window]
) -> None:
    """
    Ensures that PipelineRunner.process_windows can be called with an iterator of Windows.
    This is a characterization test to lock in behavior before refactoring types.
    """
    runner = PipelineRunner(context=mock_context)

    # Mock the internal processing to prevent side effects
    runner._process_window_with_auto_split = Mock(return_value={})
    runner.process_background_tasks = Mock()
    runner._fetch_processed_intervals = Mock(return_value=set())


    # The main call we are testing
    results, timestamp = runner.process_windows(mock_window_iterator)

    # Assert basic post-conditions
    assert isinstance(results, dict)
    assert timestamp is not None
    runner._process_window_with_auto_split.assert_called_once()
    runner.process_background_tasks.assert_called_once()
