"""Unit tests for windowing strategies."""

from datetime import datetime, timedelta

import ibis
import pytest

from egregora.transformations.windowing import (
    WindowConfig,
    create_windows,
    split_window_into_n_parts,
)


# Helper to create test data
def create_test_table(num_messages=100, start_time=None):
    if start_time is None:
        start_time = datetime(2023, 1, 1, 10, 0, 0)

    data = []
    for i in range(num_messages):
        data.append({"ts": start_time + timedelta(minutes=i), "text": f"message {i}", "sender": "Alice"})
    return ibis.memtable(data)


def _extract_scalar(val):
    """Helper to safely extract scalar from pandas/ibis result."""
    # If it's a dataframe, get the first cell
    if hasattr(val, "iloc"):
        return val.iloc[0, 0]
    if hasattr(val, "item"):
        return val.item()
    return val


def test_window_by_count():
    """Test windowing by message count."""
    table = create_test_table(120)
    config = WindowConfig(step_size=50, step_unit="messages", overlap_ratio=0.0)

    windows = list(create_windows(table, config=config))

    # Expect 3 windows: 0-49, 50-99, 100-119
    assert len(windows) == 3
    assert windows[0].size == 50
    assert windows[1].size == 50
    assert windows[2].size == 20

    # Check bounds
    assert windows[0].window_index == 0
    assert windows[1].window_index == 1
    assert windows[2].window_index == 2


def test_window_by_count_with_overlap():
    """Test windowing by message count with overlap."""
    table = create_test_table(100)
    # step=50, overlap=0.2 (10 messages).
    # Window 1: 50 + 10 = 60 messages. Start offset 0.
    # Window 2: Start offset 50. Remaining 50 messages. Window size 50.

    config = WindowConfig(step_size=50, step_unit="messages", overlap_ratio=0.2)
    windows = list(create_windows(table, config=config))

    assert len(windows) == 2
    assert windows[0].size == 60  # 50 + 10 overlap
    assert windows[1].size == 50  # Remaining 50

    # Verify overlap content
    # Window 0 should contain messages 0-59
    # Window 1 should contain messages 50-99
    # Overlap is messages 50-59

    w0_min = windows[0].table.aggregate(windows[0].table.ts.min()).execute()
    w1_min = windows[1].table.aggregate(windows[1].table.ts.min()).execute()

    w0_min = _extract_scalar(w0_min)
    w1_min = _extract_scalar(w1_min)

    # Messages are 1 min apart starting at 10:00:00
    start = datetime(2023, 1, 1, 10, 0, 0)
    assert w0_min == start
    assert w1_min == start + timedelta(minutes=50)


def test_window_by_time_hours():
    """Test windowing by hours."""
    # 5 hours of messages (300 mins)
    table = create_test_table(300)

    # Window size 2 hours. Overlap 0.
    config = WindowConfig(step_size=2, step_unit="hours", overlap_ratio=0.0)
    windows = list(create_windows(table, config=config))

    # 0-2h, 2-4h, 4-5h -> 3 windows
    assert len(windows) == 3

    # First window: 0-120 mins (120 messages)
    assert windows[0].size == 120
    # Second window: 120-240 mins (120 messages)
    assert windows[1].size == 120
    # Third window: 240-300 mins (60 messages)
    assert windows[2].size == 60


def test_window_by_bytes():
    """Test windowing by bytes."""
    # Messages are "message 0", "message 1"... "message 9" -> ~9-10 bytes each.
    # Let's use 100 messages.
    table = create_test_table(100)

    # "message 0" is 9 chars. "message 10" is 10 chars.
    # Average ~10 bytes.
    # Max bytes 100. Should hold ~10 messages per window.

    config = WindowConfig(step_unit="bytes", max_bytes_per_window=100, overlap_ratio=0.0)
    windows = list(create_windows(table, config=config))

    # 1000 total bytes approx. 100 bytes/window -> ~10 windows
    assert len(windows) > 5

    # Check a window size respects limit (approx)
    # The implementation calculates cumulative bytes.
    # Just ensure we have windows and they aren't empty (except maybe if input empty)
    for w in windows:
        assert w.size > 0


def test_split_window_into_n_parts():
    """Test splitting a window."""
    table = create_test_table(100)
    config = WindowConfig(step_size=100, step_unit="messages")
    windows = list(create_windows(table, config=config))
    assert len(windows) == 1

    main_window = windows[0]
    parts = split_window_into_n_parts(main_window, 2)

    assert len(parts) == 2
    # Should be roughly equal split by time.
    # 100 mins total. 50 mins each.
    # Messages are exactly 1 per min. So 50 messages each.
    assert parts[0].size == 50
    assert parts[1].size == 50


def test_invalid_config():
    """Test invalid configuration raises error."""
    table = create_test_table(10)
    config = WindowConfig(step_unit="invalid")
    with pytest.raises(ValueError, match="Unknown step_unit"):
        list(create_windows(table, config=config))
