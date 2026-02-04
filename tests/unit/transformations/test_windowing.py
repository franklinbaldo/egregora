from datetime import datetime, timedelta

import ibis
import pytest

from egregora.transformations.exceptions import InvalidSplitError, InvalidStepUnitError
from egregora.transformations.windowing import WindowConfig, create_windows, split_window_into_n_parts


@pytest.fixture
def messages_table():
    """Create an Ibis table with 10 messages spaced 1 hour apart."""
    base_time = datetime(2023, 1, 1, 12, 0, 0)
    data = {
        "ts": [base_time + timedelta(hours=i) for i in range(10)],
        "text": [f"message_{i}" for i in range(10)],
        "id": list(range(10)),
    }
    return ibis.memtable(data)


def test_window_by_count_no_overlap(messages_table):
    """Test splitting by message count without overlap."""
    config = WindowConfig(step_size=3, step_unit="messages", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))

    # 10 messages, step 3 -> 4 windows (3, 3, 3, 1)
    assert len(windows) == 4
    assert windows[0].size == 3
    assert windows[1].size == 3
    assert windows[2].size == 3
    assert windows[3].size == 1

    # Verify content via IDs (assuming order is preserved which it should be)
    w0_ids = windows[0].table.select("id").execute()["id"].tolist()
    assert w0_ids == [0, 1, 2]

    w3_ids = windows[3].table.select("id").execute()["id"].tolist()
    assert w3_ids == [9]


def test_window_by_count_with_overlap(messages_table):
    """Test splitting by message count with overlap."""
    # Step 3, overlap 0.34 -> 1 message overlap
    config = WindowConfig(step_size=3, step_unit="messages", overlap_ratio=0.34)
    windows = list(create_windows(messages_table, config=config))

    # Logic:
    # W0: start=0, size=3+1=4 (indices 0-3) -> [0, 1, 2, 3]
    # W1: start=3, size=3+1=4 (indices 3-6) -> [3, 4, 5, 6]
    # W2: start=6, size=3+1=4 (indices 6-9) -> [6, 7, 8, 9]
    # W3: start=9, size=1 (index 9) -> [9] (Wait, overlap extends end, but limited by total)

    # Let's trace `_window_by_count` logic:
    # num_windows = (10 + 3 - 1) // 3 = 4
    # i=0: offset=0, end=min(0+3+1, 10)=4. Size=4.
    # i=1: offset=3, end=min(3+3+1, 10)=7. Size=4.
    # i=2: offset=6, end=min(6+3+1, 10)=10. Size=4.
    # i=3: offset=9, end=min(9+3+1, 10)=11->10. Size=1.

    assert len(windows) == 4
    assert windows[0].size == 4
    assert windows[1].size == 4
    assert windows[2].size == 4
    assert windows[3].size == 1

    w0_ids = windows[0].table.select("id").execute()["id"].tolist()
    assert w0_ids == [0, 1, 2, 3]

    w1_ids = windows[1].table.select("id").execute()["id"].tolist()
    assert w1_ids == [3, 4, 5, 6]


def test_window_by_time_hours(messages_table):
    """Test splitting by time (hours)."""
    # 10 messages spaced 1 hour apart (0, 1, ..., 9 hours offsets)
    # Step 3 hours.
    # W0: [0, 3) -> 0, 1, 2
    # W1: [3, 6) -> 3, 4, 5
    # W2: [6, 9) -> 6, 7, 8
    # W3: [9, 12) -> 9
    config = WindowConfig(step_size=3, step_unit="hours", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))

    assert len(windows) == 4
    assert windows[0].size == 3
    assert windows[3].size == 1

    # Verify content
    w0_ids = windows[0].table.select("id").execute()["id"].tolist()
    assert w0_ids == [0, 1, 2]


def test_window_by_time_days(messages_table):
    """Test splitting by time (days)."""
    # Data spans 9 hours (less than 1 day).
    # Step 1 day. Should be 1 window.
    config = WindowConfig(step_size=1, step_unit="days", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))

    assert len(windows) == 1
    assert windows[0].size == 10


def test_window_by_time_max_constraint(messages_table):
    """Test max_window_time reduces the step size."""
    # Requested: 5 hours. Max: 2 hours.
    # Should reduce step size to 2 hours.
    # 10 messages (0..9 hours).
    # W0: [0, 2) -> 0, 1
    # W1: [2, 4) -> 2, 3
    # ...
    # W4: [8, 10) -> 8, 9

    config = WindowConfig(
        step_size=5, step_unit="hours", max_window_time=timedelta(hours=2), overlap_ratio=0.0
    )
    windows = list(create_windows(messages_table, config=config))

    # Logic in code: effective_step_size = max(math.floor(max_hours), 1)
    # max_hours = 2. effective_step_size = 2.

    assert len(windows) == 5
    assert windows[0].size == 2


def test_window_by_bytes(messages_table):
    """Test splitting by byte size."""
    # Note: Logic ignores size of first message in window.
    # Msg 0 (9 bytes) ignored. Remaining limit 20.
    # Fits Msg 1 (9) + Msg 2 (9) = 18.
    # Msg 3 would be 27 > 20.
    # So 3 messages per window.
    # 10 messages -> 3, 3, 3, 1 -> 4 windows.

    config = WindowConfig(max_bytes_per_window=20, step_unit="bytes", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))

    assert len(windows) == 4
    assert windows[0].size == 3
    assert windows[3].size == 1


def test_window_by_bytes_overlap(messages_table):
    """Test splitting by bytes with overlap."""
    # Limit 27.
    # W0: Msg 0 ignored. Remaining 27.
    # Fits 1, 2, 3 (9*3=27).
    # So 4 messages (0, 1, 2, 3).

    # Overlap 0.35 * 27 = 9 bytes.
    # Msg 3 is 9 bytes. So next window starts at 3.
    # W1: 3, 4, 5, 6.
    # W2: 6, 7, 8, 9.
    # W3: 9.

    config = WindowConfig(max_bytes_per_window=27, step_unit="bytes", overlap_ratio=0.35)
    windows = list(create_windows(messages_table, config=config))

    assert len(windows) == 4
    assert windows[0].size == 4

    w0_ids = windows[0].table.select("id").execute()["id"].tolist()
    assert w0_ids == [0, 1, 2, 3]

    w1_ids = windows[1].table.select("id").execute()["id"].tolist()
    assert w1_ids == [3, 4, 5, 6]


def test_split_window(messages_table):
    """Test splitting a window into N parts."""
    # 10 messages, 1 hour each. Total duration 9 hours (start to last msg).
    # Wait, create_windows uses end_time = last msg timestamp.
    # W0: 0..9.

    # Let's create a single window manually or via create_windows
    config = WindowConfig(step_size=10, step_unit="messages")
    windows = list(create_windows(messages_table, config=config))
    assert len(windows) == 1
    window = windows[0]

    # Split into 2 parts.
    # Duration: 9 hours (12:00 to 21:00).
    # Part 1: [12:00, 16:30).
    # Part 2: [16:30, 21:00].

    # Messages at: 12, 13, 14, 15, 16 -> Part 1. (5 msgs)
    # Messages at: 17, 18, 19, 20, 21 -> Part 2. (5 msgs)

    parts = split_window_into_n_parts(window, 2)

    assert len(parts) == 2
    assert parts[0].size == 5
    assert parts[1].size == 5

    # Verify content
    p0_ids = parts[0].table.select("id").execute()["id"].tolist()
    assert p0_ids == [0, 1, 2, 3, 4]


def test_split_window_uneven(messages_table):
    """Test splitting into parts with uneven distribution."""
    # Split into 3 parts.
    # 9 hours. Part = 3 hours.
    # P1: [12:00, 15:00) -> 12, 13, 14. (3 msgs)
    # P2: [15:00, 18:00) -> 15, 16, 17. (3 msgs)
    # P3: [18:00, 21:00] -> 18, 19, 20, 21. (4 msgs)

    config = WindowConfig(step_size=10, step_unit="messages")
    window = next(iter(create_windows(messages_table, config=config)))

    parts = split_window_into_n_parts(window, 3)

    assert len(parts) == 3
    assert parts[0].size == 3
    assert parts[1].size == 3
    assert parts[2].size == 4


def test_empty_table():
    """Test behavior with empty table."""
    con = ibis.duckdb.connect()
    schema = ibis.schema({"ts": "timestamp", "text": "string", "id": "int64"})
    t = con.create_table("empty", schema=schema)

    config = WindowConfig(step_size=10, step_unit="messages")
    windows = list(create_windows(t, config=config))
    assert len(windows) == 0


def test_single_row(messages_table):
    """Test behavior with single row."""
    t = messages_table.limit(1)

    config = WindowConfig(step_size=5, step_unit="messages")
    windows = list(create_windows(t, config=config))
    assert len(windows) == 1
    assert windows[0].size == 1


def test_invalid_unit(messages_table):
    """Test invalid unit raises error."""
    config = WindowConfig(step_size=10, step_unit="invalid")
    with pytest.raises(InvalidStepUnitError):
        list(create_windows(messages_table, config=config))


def test_invalid_split(messages_table):
    """Test invalid split n raises error."""
    config = WindowConfig(step_size=10, step_unit="messages")
    window = next(iter(create_windows(messages_table, config=config)))

    with pytest.raises(InvalidSplitError):
        split_window_into_n_parts(window, 1)
