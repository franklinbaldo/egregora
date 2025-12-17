# tests/unit/orchestration/pipelines/test_write_resumability.py

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import ibis

from egregora.orchestration.pipelines.write import _process_all_windows, _apply_checkpoint_filter
from egregora.transformations.windowing import Window, load_checkpoint, save_checkpoint

@pytest.fixture
def mock_pipeline_context(tmp_path):
    """Provides a mock PipelineContext for testing."""
    ctx = MagicMock()
    ctx.config.pipeline.max_windows = None
    ctx.site_root = tmp_path
    return ctx

def test_process_all_windows_saves_checkpoint_on_failure(monkeypatch, mock_pipeline_context, tmp_path):
    """
    Verify that a checkpoint is saved after the first window
    even if the second window raises an exception.
    """
    # 1. Setup
    checkpoint_path = tmp_path / ".egregora" / "checkpoint.json"

    # Create two mock windows
    now = datetime.now()
    window1 = Window(window_index=0, start_time=now, end_time=now + timedelta(hours=1), table=Mock(), size=10)
    window2 = Window(window_index=1, start_time=now + timedelta(hours=1), end_time=now + timedelta(hours=2), table=Mock(), size=10)
    windows_iterator = iter([window1, window2])

    # Mock _process_window_with_auto_split
    # It should succeed for window1 and raise an exception for window2
    def mock_process_window(*args, **kwargs):
        window = args[0]
        if window.window_index == 0:
            # Simulate one post being generated
            return {"window1": {"posts": ["dummy-post-id"]}}
        else:
            raise ValueError("Simulated failure on window 2")

    monkeypatch.setattr(
        "egregora.orchestration.pipelines.write._process_window_with_auto_split",
        mock_process_window
    )

    # Mock other dependencies of _process_all_windows
    monkeypatch.setattr(
        "egregora.orchestration.pipelines.write._calculate_max_window_size",
        lambda config: 100
    )
    monkeypatch.setattr(
        "egregora.orchestration.pipelines.write._resolve_context_token_limit",
        lambda config: 100000
    )
    monkeypatch.setattr(
        "egregora.orchestration.pipelines.write._validate_window_size",
        lambda window, max_size: None
    )
    # Isolate the test from the background task processing
    monkeypatch.setattr(
        "egregora.orchestration.pipelines.write._process_background_tasks",
        lambda ctx: None
    )


    # 2. Execute
    with pytest.raises(ValueError, match="Simulated failure on window 2"):
        _process_all_windows(windows_iterator, mock_pipeline_context, checkpoint_path)

    # 3. Verify
    assert checkpoint_path.exists(), "Checkpoint file should have been created"

    checkpoint_data = load_checkpoint(checkpoint_path)
    assert checkpoint_data is not None

    last_ts = datetime.fromisoformat(checkpoint_data["last_processed_timestamp"])

    # The timestamp should be the end_time of the first window
    # and should be timezone-aware (UTC)
    assert last_ts.isoformat() == window1.end_time.astimezone().isoformat()
    assert checkpoint_data["messages_processed"] == 1

def test_apply_checkpoint_filter_skips_old_messages(tmp_path):
    """
    Verify that _apply_checkpoint_filter correctly filters out messages
    older than the timestamp in the checkpoint file.
    """
    # 1. Setup
    checkpoint_path = tmp_path / "checkpoint.json"

    # Create a checkpoint file
    checkpoint_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    save_checkpoint(checkpoint_path, checkpoint_time, 1)

    # Use an in-memory duckdb backend to avoid pandas dependency
    ibis.duckdb.connect()

    # Create a sample ibis table using a dictionary of lists
    data = {
        'ts': [
            datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc), # Before checkpoint
            datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc), # At checkpoint
            datetime(2023, 1, 1, 13, 0, 0, tzinfo=timezone.utc), # After checkpoint
        ],
        'text': ['msg1', 'msg2', 'msg3']
    }
    table = ibis.memtable(data)

    # 2. Execute
    filtered_table = _apply_checkpoint_filter(table, checkpoint_path, checkpoint_enabled=True)

    # 3. Verify
    # DuckDB backend can return pyarrow table which has .to_pylist()
    pyarrow_table = filtered_table.to_pyarrow()
    assert pyarrow_table.num_rows == 1

    result_list = pyarrow_table.to_pylist()
    assert len(result_list) == 1
    assert result_list[0]['text'] == 'msg3'
