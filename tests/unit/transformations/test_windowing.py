"""Unit tests for windowing strategies."""

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import ibis
import pytest

from egregora.config.settings import EgregoraConfig
from egregora.transformations.windowing import (
    WindowConfig,
    create_windows,
    generate_window_signature,
    load_checkpoint,
    save_checkpoint,
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


def test_checkpoint_operations(tmp_path):
    """Test saving and loading checkpoints."""
    checkpoint_path = tmp_path / ".egregora" / "checkpoint.json"

    # Test loading non-existent checkpoint
    assert load_checkpoint(checkpoint_path) is None

    # Test saving checkpoint
    last_timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
    messages_processed = 150

    save_checkpoint(checkpoint_path, last_timestamp, messages_processed)

    assert checkpoint_path.exists()

    # Test loading saved checkpoint
    loaded = load_checkpoint(checkpoint_path)
    assert loaded is not None
    assert loaded["messages_processed"] == 150
    # JSON stores ISO string, verify it parses back
    loaded_ts = datetime.fromisoformat(loaded["last_processed_timestamp"])
    assert loaded_ts == last_timestamp

    # Test corrupted checkpoint
    checkpoint_path.write_text("invalid json")
    assert load_checkpoint(checkpoint_path) is None


def test_generate_window_signature():
    """Test window signature generation."""
    table = create_test_table(10)
    config = EgregoraConfig()

    # Mock build_conversation_xml to return deterministic XML
    with patch("egregora.transformations.windowing.build_conversation_xml") as mock_build_xml:
        mock_build_xml.return_value = "<chat>content</chat>"

        sig1 = generate_window_signature(table, config, "prompt template")
        sig2 = generate_window_signature(table, config, "prompt template")

        assert sig1 == sig2
        assert mock_build_xml.call_count == 2

        # Verify components of signature
        # data_hash:logic_hash:model_hash
        parts = sig1.split(":")
        # The default model name might contain colons (e.g., google-gla:gemini-2.5-flash)
        # So splitting by ":" might yield more than 3 parts if we don't handle it.
        # But the implementation is: return f"{data_hash}:{logic_hash}:{model_hash}"
        # If model_hash has ':', then len(parts) > 3.
        # Let's check that we have AT LEAST 3 parts, and the last part(s) form the model name
        assert len(parts) >= 3

        # Change prompt template -> different signature
        sig3 = generate_window_signature(table, config, "different template")
        assert sig1 != sig3

        # Provide pre-computed XML -> should use it
        mock_build_xml.reset_mock()
        sig4 = generate_window_signature(table, config, "prompt template", xml_content="<chat>content</chat>")
        assert sig1 == sig4
        mock_build_xml.assert_not_called()


def test_window_by_time_with_max_window_limit(caplog):
    """Test that max_window_time constrains the window size."""
    # 3 days of data (72 hours)
    start_time = datetime(2023, 1, 1, 0, 0, 0)
    # One message per hour for 72 hours
    data = [{"ts": start_time + timedelta(hours=i), "text": f"msg {i}", "sender": "A"} for i in range(72)]
    table = ibis.memtable(data)

    # Request 2 days per window, but limit to 24 hours
    max_window = timedelta(hours=24)
    config = WindowConfig(step_size=2, step_unit="days", max_window_time=max_window, overlap_ratio=0.0)

    with caplog.at_level("INFO"):
        windows = list(create_windows(table, config=config))

    # Should reduce step size to 24 hours (1 day)
    # 72 hours total / 24 hours per window = 3 windows
    assert len(windows) == 3
    assert "Adjusted window size" in caplog.text

    # Verify each window is approx 24 hours
    for w in windows:
        duration = w.end_time - w.start_time
        # Allow minor floating point diff
        assert duration <= max_window + timedelta(seconds=1)


def test_window_by_count_max_window_warning(caplog):
    """Test warning when max_window_time is used with message count windowing."""
    table = create_test_table(10)
    config = WindowConfig(step_size=10, step_unit="messages", max_window_time=timedelta(hours=1))

    with caplog.at_level("WARNING"):
        list(create_windows(table, config=config))

    assert "max_window_time constraint not enforced for message-based windowing" in caplog.text
