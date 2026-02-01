"""Unit tests for windowing strategies.

Re-implements logic from windowing.feature to ensure coverage in unit test suite.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

try:
    import ibis
except ImportError:
    pytest.skip("ibis not installed", allow_module_level=True)

from egregora.transformations.exceptions import InvalidSplitError, InvalidStepUnitError
from egregora.transformations.windowing import (
    WindowConfig,
    create_windows,
    generate_window_signature,
    split_window_into_n_parts,
)


@pytest.fixture
def message_table():
    """Create a basic message table."""
    start_time = datetime(2023, 1, 1, 10, 0, 0)
    data = [
        {"ts": start_time + timedelta(minutes=i), "text": f"message {i}", "sender": "Alice"}
        for i in range(100)
    ]
    return ibis.memtable(data)


def test_window_by_count(message_table):
    """Test splitting by message count."""
    # Case 1: No overlap
    config = WindowConfig(step_size=50, step_unit="messages", overlap_ratio=0.0)
    windows = list(create_windows(message_table, config=config))
    assert len(windows) == 2
    assert windows[0].size == 50
    assert windows[1].size == 50

    # Case 2: With overlap
    config = WindowConfig(step_size=50, step_unit="messages", overlap_ratio=0.2)
    windows = list(create_windows(message_table, config=config))
    assert len(windows) == 2
    assert windows[0].size == 60  # 50 + 10 overlap
    assert windows[1].size == 50  # Remaining messages

    # Case 3: Uneven split
    config = WindowConfig(step_size=30, step_unit="messages", overlap_ratio=0.0)
    windows = list(create_windows(message_table, config=config))
    assert len(windows) == 4
    assert windows[0].size == 30
    assert windows[3].size == 10


def test_window_by_time_duration():
    """Test splitting by time duration."""
    start_time = datetime(2023, 1, 1, 0, 0, 0)
    # 300 minutes of data (5 hours)
    data = [{"ts": start_time + timedelta(minutes=i), "text": f"msg {i}", "sender": "A"} for i in range(300)]
    table = ibis.memtable(data)

    # Split by 2 hours
    config = WindowConfig(step_size=2, step_unit="hours", overlap_ratio=0.0)
    windows = list(create_windows(table, config=config))

    # Expect 3 windows: 0-2h (120 mins), 2-4h (120 mins), 4-5h (60 mins)
    assert len(windows) == 3
    assert windows[0].size == 120
    assert windows[1].size == 120
    assert windows[2].size == 60


def test_window_by_time_with_max_window_constraint():
    """Test max_window_time constraint logic."""
    start_time = datetime(2023, 1, 1, 0, 0, 0)
    # 72 hours of data
    data = [{"ts": start_time + timedelta(hours=i), "text": f"msg {i}", "sender": "A"} for i in range(72)]
    table = ibis.memtable(data)

    # Request 2 days windows but cap at 24 hours
    max_window = timedelta(hours=24)
    config = WindowConfig(step_size=2, step_unit="days", max_window_time=max_window, overlap_ratio=0.0)

    # Should reduce to 1 day (24 hours) windows
    windows = list(create_windows(table, config=config))

    # 72 hours / 24 hours = 3 windows
    assert len(windows) == 3
    for w in windows:
        w.end_time - w.start_time
        # Check duration is roughly 24 hours (inclusive/exclusive handling implies < 24h + 1h)
        # Actually logic is strictly time based.
        # But data is one msg per hour.
        assert (w.end_time - w.start_time) <= max_window + timedelta(seconds=1)


def test_window_by_bytes():
    """Test splitting by byte size."""
    start_time = datetime(2023, 1, 1, 10, 0, 0)
    # Messages of 10 bytes each
    text = "x" * 10
    data = [{"ts": start_time + timedelta(minutes=i), "text": text, "sender": "Alice"} for i in range(100)]
    table = ibis.memtable(data)

    # Split by 100 bytes (should be ~10 messages)
    config = WindowConfig(step_unit="bytes", max_bytes_per_window=100, overlap_ratio=0.0)
    windows = list(create_windows(table, config=config))

    assert len(windows) >= 10
    for w in windows:
        assert w.size > 0


def test_window_by_bytes_with_overlap():
    """Test byte windowing with overlap."""
    start_time = datetime(2023, 1, 1, 10, 0, 0)
    # Varying lengths
    messages = ["short", "medium msg", "a bit longer message", "short", "another medium"]
    data = [
        {"ts": start_time + timedelta(minutes=i), "text": msg, "sender": "Alice"}
        for i, msg in enumerate(messages)
    ]
    table = ibis.memtable(data)

    # Limit 30 bytes, overlap 0.5
    config = WindowConfig(step_unit="bytes", max_bytes_per_window=30, overlap_ratio=0.5)
    windows = list(create_windows(table, config=config))

    assert len(windows) > 0


def test_window_by_bytes_duplicates():
    """Test byte windowing with duplicate timestamps."""
    ts = datetime(2023, 1, 1, 10, 0, 0)
    data = [
        {"ts": ts, "text": "a", "sender": "Alice"},
        {"ts": ts, "text": "b", "sender": "Alice"},
        {"ts": ts, "text": "c", "sender": "Alice"},
        {"ts": ts + timedelta(minutes=1), "text": "d", "sender": "Alice"},
        {"ts": ts + timedelta(minutes=1), "text": "e", "sender": "Alice"},
    ]
    table = ibis.memtable(data)

    # Limit 2 bytes (should force small windows)
    config = WindowConfig(step_unit="bytes", max_bytes_per_window=2, overlap_ratio=0.0)
    windows = list(create_windows(table, config=config))

    assert len(windows) >= 2


def test_split_window_into_n_parts(message_table):
    """Test splitting a window into sub-windows."""
    config = WindowConfig(step_size=100, step_unit="messages")
    windows = list(create_windows(message_table, config=config))
    window = windows[0]

    parts = split_window_into_n_parts(window, 2)
    assert len(parts) == 2
    assert parts[0].size == 50
    assert parts[1].size == 50


def test_invalid_config(message_table):
    """Test invalid configurations."""
    # Invalid unit
    config = WindowConfig(step_unit="invalid")
    with pytest.raises(InvalidStepUnitError):
        list(create_windows(message_table, config=config))

    # Invalid split
    config = WindowConfig(step_size=100, step_unit="messages")
    windows = list(create_windows(message_table, config=config))
    with pytest.raises(InvalidSplitError):
        split_window_into_n_parts(windows[0], 1)


def test_generate_window_signature(message_table):
    """Test signature generation."""
    mock_config = MagicMock()
    mock_config.writer.custom_instructions = "instructions"
    mock_config.models.writer = "model-v1"

    with patch("egregora.transformations.windowing.build_conversation_xml") as mock_build:
        mock_build.return_value = "<xml>content</xml>"

        sig1 = generate_window_signature(message_table, mock_config, "template")
        sig2 = generate_window_signature(message_table, mock_config, "template")

        assert sig1 == sig2

        sig3 = generate_window_signature(message_table, mock_config, "other template")
        assert sig1 != sig3


def test_empty_table():
    """Test empty table handling."""
    schema = ibis.schema([("ts", "timestamp"), ("text", "string")])
    table = ibis.memtable([], schema=schema)
    windows = list(create_windows(table))
    assert len(windows) == 0
