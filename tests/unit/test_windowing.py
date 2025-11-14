from datetime import datetime, timedelta, timezone

import ibis

from egregora.transformations.windowing import create_windows


def _memtable(rows: list[dict]) -> ibis.Table:
    """Create an ibis memtable with the minimal fields needed for windowing tests."""

    schema = {"ts": "timestamp", "text": "string"}
    return ibis.memtable(rows, schema=schema)


def test_create_windows_message_overlap_clamps_ratio():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"ts": base + timedelta(minutes=i), "text": f"msg-{i}"}
        for i in range(6)
    ]

    table = _memtable(rows)

    windows = list(
        create_windows(
            table,
            step_size=3,
            step_unit="messages",
            overlap_ratio=0.75,  # intentionally above supported range to exercise clamping
        )
    )

    assert len(windows) == 2

    first_df = windows[0].table.execute()
    second_df = windows[1].table.execute()

    # overlap_ratio should be clamped to 0.5 -> 1 message overlap (4 + 3 rows)
    assert len(first_df) == 4
    assert len(second_df) == 3
    assert first_df.iloc[-1]["text"] == second_df.iloc[0]["text"]


def test_create_windows_time_overlap_and_max_window_time_adjustment():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"ts": base + timedelta(hours=6 * i), "text": f"msg-{i}"}
        for i in range(12)
    ]

    table = _memtable(rows)

    windows = list(
        create_windows(
            table,
            step_size=2,
            step_unit="days",
            overlap_ratio=0.5,
            max_window_time=timedelta(hours=24),
        )
    )

    assert len(windows) >= 2

    first_window, second_window = windows[0], windows[1]

    # max_window_time should reduce the effective step to 16 hours with 8 hours overlap (24h total span)
    assert first_window.end_time - first_window.start_time == timedelta(hours=24)
    assert second_window.start_time - first_window.start_time == timedelta(hours=16)

    first_df = first_window.table.execute()
    second_df = second_window.table.execute()

    assert not first_df.empty
    assert not second_df.empty
    assert set(first_df["text"]) & set(second_df["text"])  # overlapping context is preserved


def test_create_windows_byte_overlap_applies_ratio():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"ts": base + timedelta(minutes=5 * i), "text": f"message-{i}"}
        for i in range(6)
    ]

    table = _memtable(rows)

    windows = list(
        create_windows(
            table,
            step_unit="bytes",
            max_bytes_per_window=25,
            overlap_ratio=0.4,
        )
    )

    assert len(windows) >= 2

    first_df = windows[0].table.execute()
    second_df = windows[1].table.execute()

    # Overlap should retain the last message from the previous window as context
    assert first_df.iloc[-1]["text"] == second_df.iloc[0]["text"]
