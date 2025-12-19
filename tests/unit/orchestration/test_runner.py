from unittest.mock import MagicMock, Mock, patch

import pytest
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.runner import PipelineRunner
from egregora.transformations.windowing import Window


def test_pipeline_runner_execution():
    """
    GREEN TEST: Verify that PipelineRunner can process windows.
    """
    # 1. Setup Mocks
    mock_context = MagicMock(spec=PipelineContext)
    mock_context.config.pipeline.max_windows = None  # Process all
    mock_context.config.pipeline.max_prompt_tokens = 1000
    mock_context.config.pipeline.use_full_context_window = False

    # Mock window objects - using simple Mock without spec to allow attribute setting easily
    # or just creating real Window objects if feasible, but they require tables.
    # Simpler to just use a Mock that has the necessary attributes.

    mock_window_1 = Mock()
    mock_window_1.window_index = 0
    mock_window_1.size = 10
    mock_window_1.start_time.strftime.return_value = "2023-01-01 10:00"
    mock_window_1.end_time.strftime.return_value = "11:00"
    # Ensure comparisons work for timestamp tracking
    mock_window_1.end_time.__gt__ = lambda self, other: True

    mock_window_2 = Mock()
    mock_window_2.window_index = 1
    mock_window_2.size = 15
    mock_window_2.start_time.strftime.return_value = "2023-01-01 11:00"
    mock_window_2.end_time.strftime.return_value = "12:00"
    mock_window_2.end_time.__gt__ = lambda self, other: True

    windows = [mock_window_1, mock_window_2]

    # 2. Instantiate Runner
    runner = PipelineRunner(mock_context)

    # 3. Patch the internal processing method
    # We patch it on the INSTANCE of the class or the class itself.
    # Since we import PipelineRunner, we can patch the class method.
    with patch.object(PipelineRunner, "_process_window_with_auto_split") as mock_process:
        mock_process.return_value = {"post1": {"posts": ["p1"]}}

        # Patch background tasks to avoid errors
        with patch.object(PipelineRunner, "_process_background_tasks"):
            results = runner.run(windows)

        assert mock_process.call_count == 2
        assert len(results) > 0
