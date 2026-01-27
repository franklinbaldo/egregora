"""Unit tests for windowing strategies."""

from datetime import datetime, timedelta
from unittest.mock import patch

import ibis
import pytest

from egregora.transformations.exceptions import InvalidSplitError, InvalidStepUnitError
from egregora.transformations.windowing import (
    WindowConfig,
    _window_by_bytes,
    create_windows,
    generate_window_signature,
    split_window_into_n_parts,
)


# Helper to create test data
def create_test_table(messages=100, start_time=None):
    if start_time is None:
        start_time = datetime(2023, 1, 1, 10, 0, 0)

    if isinstance(messages, int):
        num_messages = messages
        data = [
            {"ts": start_time + timedelta(minutes=i), "text": f"message {i}", "sender": "Alice"}
            for i in range(num_messages)
        ]
    else:
        data = [
            {"ts": start_time + timedelta(minutes=i), "text": msg, "sender": "Alice"}
            for i, msg in enumerate(messages)
        ]

    if not data:
        schema = ibis.schema(
            [
                ("ts", "timestamp"),
                ("text", "string"),
                ("sender", "string"),
            ]
        )
        return ibis.memtable(data, schema=schema)
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


def test_window_by_bytes_precise():
    """Test windowing by bytes with a deterministic dataset."""
    messages = [
        "short",  # 5 bytes
        "medium msg",  # 10 bytes
        "a bit longer message",  # 20 bytes
        "short",  # 5 bytes
        "another medium",  # 14 bytes
    ]  # Total bytes = 54

    table = create_test_table(messages)

    # Scenario 1: No overlap, max_bytes_per_window=20
    # The actual behavior is:
    # 1. "short", "medium msg" (15 bytes) -> Window 1 (size 2)
    # 2. "a bit longer message", "short", "another medium" (20 + 5 + 14 = 39 bytes, but
    #    relative bytes are [0, 5, 19] which are all <= 20) -> Window 2 (size 3)
    config = WindowConfig(step_unit="bytes", max_bytes_per_window=20, overlap_ratio=0.0)
    windows = list(create_windows(table, config=config))

    assert len(windows) == 2
    assert [w.size for w in windows] == [2, 3]

    # Scenario 2: With overlap, max_bytes_per_window=30, overlap_ratio=0.5
    # My manual trace of the actual implementation shows this should produce
    # three windows with sizes [3, 2, 1].
    config = WindowConfig(step_unit="bytes", max_bytes_per_window=30, overlap_ratio=0.5)
    windows = list(create_windows(table, config=config))

    assert len(windows) == 3
    assert [w.size for w in windows] == [3, 2, 1]


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


def test_invalid_config_raises_specific_error():
    """Test invalid configuration raises a structured exception."""
    table = create_test_table(10)
    config = WindowConfig(step_unit="invalid")
    with pytest.raises(InvalidStepUnitError) as exc_info:
        list(create_windows(table, config=config))
    assert exc_info.value.step_unit == "invalid"


def test_split_window_invalid_n_raises_specific_error():
    """Test splitting a window with n < 2 raises a structured exception."""
    table = create_test_table(100)
    config = WindowConfig(step_size=100, step_unit="messages")
    windows = list(create_windows(table, config=config))
    main_window = windows[0]
    with pytest.raises(InvalidSplitError) as exc_info:
        split_window_into_n_parts(main_window, 1)
    assert exc_info.value.n == 1


def test_generate_window_signature(config_factory):
    """Test window signature generation."""
    table = create_test_table(10)
    config = config_factory()

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


@pytest.mark.parametrize(
    ("num_messages", "step_size", "overlap_ratio", "expected_windows"),
    [
        # Case 1: Exact multiple, no overlap
        (100, 50, 0.0, [50, 50]),
        # Case 2: Partial last window, no overlap
        (120, 50, 0.0, [50, 50, 20]),
        # Case 3: Single window (less than step_size)
        (30, 50, 0.0, [30]),
        # Case 4: Empty input
        (0, 50, 0.0, []),
        # Case 5: Exact multiple with overlap
        (100, 50, 0.2, [60, 50]),
        # Case 6: Partial last window with overlap
        (120, 50, 0.2, [60, 60, 20]),
        # Case 7: Single window with overlap (overlap has no effect)
        (30, 50, 0.2, [30]),
    ],
    ids=[
        "exact-multiple-no-overlap",
        "partial-last-no-overlap",
        "single-window-no-overlap",
        "empty-input",
        "exact-multiple-with-overlap",
        "partial-last-with-overlap",
        "single-window-with-overlap",
    ],
)
def test_window_by_count_scenarios(num_messages, step_size, overlap_ratio, expected_windows):
    """Test various scenarios for message count-based windowing."""
    table = create_test_table(num_messages)
    config = WindowConfig(step_size=step_size, step_unit="messages", overlap_ratio=overlap_ratio)

    windows = list(create_windows(table, config=config))
    window_sizes = [w.size for w in windows]

    assert window_sizes == expected_windows
    assert len(windows) == len(expected_windows)
    for i, window in enumerate(windows):
        assert window.window_index == i

def test_window_by_bytes_duplicates():
    # Create table with duplicate timestamps
    # 5 messages, first 3 have same TS
    ts = datetime(2023, 1, 1)
    data = {
        "ts": [ts, ts, ts, ts, ts],
        "text": ["a", "b", "c", "d", "e"],  # 1 byte each
        "id": [1, 2, 3, 4, 5]
    }
    table = ibis.memtable(data)

    # Legacy behavior allows first message to be "free".
    # max_bytes=2.
    # W0: a(1) + b(1) + c(1) = 3 bytes. (1 "free", 2 accumulated).
    # W1: d(1) + e(1) = 2 bytes.

    windows = list(_window_by_bytes(table, max_bytes=2, overlap_bytes=0))

    assert len(windows) == 2

    res0 = windows[0].table.execute()
    assert res0["text"].tolist() == ["a", "b", "c"]

    res1 = windows[1].table.execute()
    assert res1["text"].tolist() == ["d", "e"]


def test_window_by_bytes_partial_duplicates():
    # TS: A, B, B, B, C
    t1 = datetime(2023, 1, 1)
    t2 = datetime(2023, 1, 2)
    t3 = datetime(2023, 1, 3)

    data = {
        "ts": [t1, t2, t2, t2, t3],
        "text": ["a", "b", "c", "d", "e"],
        "id": [1, 2, 3, 4, 5]
    }
    table = ibis.memtable(data)

    # Same chunking logic applies.
    # W0: [a, b, c]
    # W1: [d, e]

    windows = list(_window_by_bytes(table, max_bytes=2, overlap_bytes=0))

    assert len(windows) == 2

    res0 = windows[0].table.execute()
    assert res0["text"].tolist() == ["a", "b", "c"]

    res1 = windows[1].table.execute()
    assert res1["text"].tolist() == ["d", "e"]
