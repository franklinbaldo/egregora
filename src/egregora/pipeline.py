"""Generic pipeline utilities for windowing and organizing messages.

MODERN (Phase 6): Replaced period-based grouping with flexible windowing.
- Supports message count, time-based, and byte-based windowing
- Sequential window indices for simple resume logic
- No calendar edge cases (ISO weeks, timezone conversions, etc.)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import ibis
from ibis.expr.types import Table

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Window:
    """Represents a processing window of messages (runtime-only construct).

    Windows are transient views of the conversation data, computed dynamically
    based on runtime config (step_size, step_unit). They are NOT persisted to
    the database since changing windowing params would invalidate any stored
    window metadata.

    The `table` field contains a filtered view of CONVERSATION_SCHEMA data.
    """

    window_id: str
    window_index: int
    start_time: datetime
    end_time: datetime
    table: Table  # Filtered view of CONVERSATION_SCHEMA (not a separate DB schema)
    size: int  # Number of messages


def window_has_posts(window_index: int, posts_dir: Path) -> bool:
    """Check if posts already exist for this window.

    Simplified resume logic: check by sequential window index.

    Args:
        window_index: Sequential index (0, 1, 2, ...)
        posts_dir: Directory containing post files

    Returns:
        True if posts exist for this window

    """
    if not posts_dir.exists():
        return False

    # Look for posts matching "chunk_{index:03d}-*.md" or "window_{index}-*.md"
    patterns = [
        f"chunk_{window_index:03d}-*.md",
        f"window_{window_index}-*.md",
    ]

    return any(list(posts_dir.glob(pattern)) for pattern in patterns)


def get_last_processed_window(posts_dir: Path) -> int:
    """Get the last processed window index for resume logic.

    Args:
        posts_dir: Directory containing post files

    Returns:
        -1 if no windows processed yet, otherwise max window index

    """
    if not posts_dir.exists():
        return -1

    existing_posts = list(posts_dir.glob("chunk_*.md")) + list(posts_dir.glob("window_*.md"))

    if not existing_posts:
        return -1

    # Extract indices from filenames
    indices = []
    for post in existing_posts:
        stem = post.stem
        if stem.startswith(("chunk_", "window_")):
            idx_str = stem.split("_")[1].split("-")[0]
        else:
            continue

        try:
            indices.append(int(idx_str))
        except ValueError:
            continue

    return max(indices) if indices else -1


def create_windows(
    table: Table,
    *,
    step_size: int = 100,
    step_unit: str = "messages",
    min_window_size: int = 10,
    max_window_time: timedelta | None = None,
) -> dict[str, Table]:
    """Create processing windows from messages.

    Replaces period-based grouping with flexible windowing:
    - By message count: step_size=100, step_unit="messages"
    - By time: step_size=2, step_unit="days"
    - By byte count: step_size=50000, step_unit="bytes" (not yet implemented)

    Args:
        table: Table with timestamp column
        step_size: Size of each window
        step_unit: Unit for windowing ("messages", "hours", "days", "bytes")
        min_window_size: Minimum messages per window (skip smaller windows)
        max_window_time: Optional maximum time span per window

    Returns:
        Dict mapping window_id to Table

    Examples:
        >>> # 100 messages per window
        >>> windows = create_windows(table, step_size=100, step_unit="messages")
        >>> # 2 days per window
        >>> windows = create_windows(table, step_size=2, step_unit="days")

    """
    if table.count().execute() == 0:
        return {}

    # Sort by timestamp
    sorted_table = table.order_by(table.timestamp)

    if step_unit == "messages":
        windows = _window_by_count(sorted_table, step_size, min_window_size)
    elif step_unit in ("hours", "days"):
        windows = _window_by_time(sorted_table, step_size, step_unit, min_window_size)
    elif step_unit == "bytes":
        windows = _window_by_bytes(sorted_table, step_size, min_window_size)
    else:
        msg = f"Unknown step_unit: {step_unit}"
        raise ValueError(msg)

    # Apply max_window_time constraint if specified
    if max_window_time:
        windows = _apply_time_limit(windows, max_window_time)

    return {w.window_id: w.table for w in windows}


def _window_by_count(
    table: Table,
    step_size: int,
    min_window_size: int,
) -> list[Window]:
    """Create windows of fixed message count."""
    windows = []
    total_count = table.count().execute()

    window_index = 0
    for offset in range(0, total_count, step_size):
        chunk_size = min(step_size, total_count - offset)

        # Skip if below minimum
        if chunk_size < min_window_size and offset > 0:
            # Merge into previous window
            if windows:
                prev = windows[-1]
                merged_table = ibis.union(prev.table, table.limit(chunk_size, offset=offset))
                windows[-1] = Window(
                    window_id=prev.window_id,
                    window_index=prev.window_index,
                    start_time=prev.start_time,
                    end_time=_get_max_timestamp(merged_table),
                    table=merged_table,
                    size=prev.size + chunk_size,
                )
            continue

        window_table = table.limit(chunk_size, offset=offset)
        window_id = f"chunk_{window_index:03d}"

        # Get time bounds
        start_time = _get_min_timestamp(window_table)
        end_time = _get_max_timestamp(window_table)

        windows.append(
            Window(
                window_id=window_id,
                window_index=window_index,
                start_time=start_time,
                end_time=end_time,
                table=window_table,
                size=chunk_size,
            )
        )
        window_index += 1

    return windows


def _window_by_time(
    table: Table,
    step_size: int,
    step_unit: str,
    min_window_size: int,
) -> list[Window]:
    """Create windows of fixed time duration."""
    windows = []

    # Get overall time range
    min_ts = _get_min_timestamp(table)
    max_ts = _get_max_timestamp(table)

    # Calculate window duration
    if step_unit == "hours":
        delta = timedelta(hours=step_size)
    else:  # days
        delta = timedelta(days=step_size)

    # Create windows
    window_index = 0
    current_start = min_ts

    while current_start < max_ts:
        current_end = current_start + delta

        # Filter messages in this window
        window_table = table.filter((table.timestamp >= current_start) & (table.timestamp < current_end))

        window_size = window_table.count().execute()

        # Skip if below minimum
        if window_size < min_window_size:
            current_start = current_end
            continue

        window_id = f"window_{current_start.strftime('%Y%m%d_%H%M%S')}"

        windows.append(
            Window(
                window_id=window_id,
                window_index=window_index,
                start_time=current_start,
                end_time=current_end,
                table=window_table,
                size=window_size,
            )
        )
        window_index += 1
        current_start = current_end

    return windows


def _window_by_bytes(
    table: Table,
    step_size: int,
    min_window_size: int,
) -> list[Window]:
    """Create windows based on byte count (text size).

    Groups messages until cumulative byte count reaches step_size.
    Uses SUM(LENGTH(message)) in SQL for accurate counting.

    Byte counts serve as token proxies (~4 bytes per token for English),
    useful for respecting LLM context limits without tokenizer dependencies.

    Args:
        table: Input table
        step_size: Target bytes per window
        min_window_size: Minimum messages per window

    Returns:
        List of windows

    Raises:
        NotImplementedError: Byte-based windowing not yet implemented

    """
    msg = "Byte-based windowing not yet implemented"
    raise NotImplementedError(msg)


def _apply_time_limit(windows: list[Window], max_time: timedelta) -> list[Window]:
    """Split windows that exceed max_time duration."""
    result = []

    for window in windows:
        duration = window.end_time - window.start_time

        if duration <= max_time:
            result.append(window)
            continue

        # Split window into smaller time chunks
        # Simplified: just split in half for now
        mid_time = window.start_time + (duration / 2)

        first_half = window.table.filter(window.table.timestamp < mid_time)
        second_half = window.table.filter(window.table.timestamp >= mid_time)

        first_size = first_half.count().execute()
        second_size = second_half.count().execute()

        if first_size > 0:
            result.append(
                Window(
                    window_id=f"{window.window_id}_a",
                    window_index=window.window_index,
                    start_time=window.start_time,
                    end_time=mid_time,
                    table=first_half,
                    size=first_size,
                )
            )

        if second_size > 0:
            result.append(
                Window(
                    window_id=f"{window.window_id}_b",
                    window_index=window.window_index + 1,
                    start_time=mid_time,
                    end_time=window.end_time,
                    table=second_half,
                    size=second_size,
                )
            )

    return result


def _get_min_timestamp(table: Table) -> datetime:
    """Get minimum timestamp from table."""
    result = table.aggregate(table.timestamp.min().name("min_ts")).execute()
    return result["min_ts"][0]


def _get_max_timestamp(table: Table) -> datetime:
    """Get maximum timestamp from table."""
    result = table.aggregate(table.timestamp.max().name("max_ts")).execute()
    return result["max_ts"][0]
