"""Generic pipeline utilities for windowing and organizing messages.

MODERN (Phase 6): Replaced period-based grouping with flexible windowing.
- Supports message count, time-based, and byte-based windowing
- Sequential window indices for simple resume logic
- No calendar edge cases (ISO weeks, timezone conversions, etc.)

MODERN (Phase 7): Checkpoint-based resume logic.
- Resume uses sentinel file tracking last processed timestamp
- Post dates are LLM-decided based on message content
- Windows are ephemeral processing batches (not tied to resume state)
"""

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ibis.expr.types import Table

logger = logging.getLogger(__name__)


# ============================================================================
# Checkpoint / Sentinel File Utilities
# ============================================================================


def load_checkpoint(checkpoint_path: Path) -> dict | None:
    """Load processing checkpoint from sentinel file.

    Args:
        checkpoint_path: Path to .egregora/checkpoint.json

    Returns:
        Checkpoint dict with 'last_processed_timestamp' or None if not found

    """
    if not checkpoint_path.exists():
        return None

    try:
        with checkpoint_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load checkpoint from %s: %s", checkpoint_path, e)
        return None


def save_checkpoint(checkpoint_path: Path, last_timestamp: datetime, messages_processed: int) -> None:
    """Save processing checkpoint to sentinel file.

    Args:
        checkpoint_path: Path to .egregora/checkpoint.json
        last_timestamp: Timestamp of last processed message
        messages_processed: Total count of messages processed

    """
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "last_processed_timestamp": last_timestamp.isoformat(),
        "messages_processed": messages_processed,
        "schema_version": "1.0",
    }

    try:
        with checkpoint_path.open("w") as f:
            json.dump(checkpoint, f, indent=2)
        logger.info("Checkpoint saved: %s", checkpoint_path)
    except OSError as e:
        logger.warning("Failed to save checkpoint to %s: %s", checkpoint_path, e)


# ============================================================================
# Window Dataclass
# ============================================================================


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


def create_windows(  # noqa: PLR0913
    table: Table,
    *,
    step_size: int = 100,
    step_unit: str = "messages",
    min_window_size: int = 10,
    overlap_ratio: float = 0.2,
    max_window_time: timedelta | None = None,
) -> Iterator[Window]:
    """Create processing windows from messages with overlap for context continuity.

    Replaces period-based grouping with flexible windowing:
    - By message count: step_size=100, step_unit="messages"
    - By time: step_size=2, step_unit="days"
    - By byte count: step_size=50000, step_unit="bytes" (not yet implemented)

    Overlap provides conversation context across window boundaries, improving
    LLM understanding and blog post quality at the cost of ~20% more tokens.

    Args:
        table: Table with timestamp column
        step_size: Size of each window
        step_unit: Unit for windowing ("messages", "hours", "days", "bytes")
        min_window_size: Minimum messages per window (skip smaller windows)
        overlap_ratio: Fraction of window to overlap (0.0-0.5, default 0.2 = 20%)
        max_window_time: Optional maximum time span per window

    Yields:
        Window objects with overlapping message sets

    Examples:
        >>> # 100 messages per window with 20% overlap
        >>> for window in create_windows(table, step_size=100, step_unit="messages"):
        ...     print(f"Processing {window.window_id}: {window.size} messages")
        >>>
        >>> # No overlap (old behavior)
        >>> for window in create_windows(table, step_size=100, overlap_ratio=0.0):
        ...     pass

    """
    if table.count().execute() == 0:
        return

    # Sort by timestamp
    sorted_table = table.order_by(table.timestamp)

    # Calculate overlap in messages
    overlap = int(step_size * overlap_ratio)

    if step_unit == "messages":
        windows = _window_by_count(sorted_table, step_size, min_window_size, overlap)
    elif step_unit in ("hours", "days"):
        windows = _window_by_time(sorted_table, step_size, step_unit, min_window_size, overlap_ratio)
    elif step_unit == "bytes":
        windows = _window_by_bytes(sorted_table, step_size, min_window_size, overlap)
    else:
        msg = f"Unknown step_unit: {step_unit}"
        raise ValueError(msg)

    # Apply max_window_time constraint if specified
    if max_window_time:
        windows = _apply_time_limit(windows, max_window_time)

    yield from windows


def _window_by_count(
    table: Table,
    step_size: int,
    min_window_size: int,
    overlap: int = 0,
) -> Iterator[Window]:
    """Generate windows of fixed message count with optional overlap.

    Overlap provides conversation context across window boundaries:
    - Window 1: messages [0-119] (100 + 20 overlap)
    - Window 2: messages [100-219] (100 + 20 overlap)
    - Messages 100-119 appear in both windows for context

    Args:
        table: Sorted table of messages
        step_size: Number of messages per window (before overlap)
        min_window_size: Minimum messages (skip smaller windows)
        overlap: Number of messages to overlap with previous window

    Yields:
        Windows with overlapping message sets

    """
    total_count = table.count().execute()
    window_index = 0
    offset = 0

    while offset < total_count:
        # Window size = step_size + overlap (or remaining messages)
        chunk_size = min(step_size + overlap, total_count - offset)

        # Skip tiny trailing windows
        if chunk_size < min_window_size:
            logger.debug("Skipping tiny trailing window: %d messages (min=%d)", chunk_size, min_window_size)
            break

        window_table = table.limit(chunk_size, offset=offset)

        # Get time bounds
        start_time = _get_min_timestamp(window_table)
        end_time = _get_max_timestamp(window_table)

        # Timestamp-based window_id for stability across config changes
        window_id = f"window_{start_time.strftime('%Y%m%d_%H%M%S')}"

        yield Window(
            window_id=window_id,
            window_index=window_index,
            start_time=start_time,
            end_time=end_time,
            table=window_table,
            size=chunk_size,
        )

        window_index += 1
        offset += step_size  # Advance by step_size (not chunk_size), creating overlap


def _window_by_time(
    table: Table,
    step_size: int,
    step_unit: str,
    min_window_size: int,
    overlap_ratio: float = 0.0,
) -> Iterator[Window]:
    """Generate windows of fixed time duration with optional overlap.

    Time overlap ensures conversation threads spanning window boundaries
    maintain context for the LLM.

    Args:
        table: Sorted table of messages
        step_size: Duration of each window
        step_unit: "hours" or "days"
        min_window_size: Minimum messages per window
        overlap_ratio: Fraction of time window to overlap (0.0-0.5)

    Yields:
        Windows with overlapping time ranges

    """
    # Get overall time range
    min_ts = _get_min_timestamp(table)
    max_ts = _get_max_timestamp(table)

    # Calculate window duration
    if step_unit == "hours":
        delta = timedelta(hours=step_size)
    else:  # days
        delta = timedelta(days=step_size)

    # Calculate overlap duration
    overlap_delta = delta * overlap_ratio

    # Create windows
    window_index = 0
    current_start = min_ts

    while current_start < max_ts:
        current_end = current_start + delta + overlap_delta

        # Filter messages in this window
        window_table = table.filter((table.timestamp >= current_start) & (table.timestamp < current_end))

        window_size = window_table.count().execute()

        # Skip if below minimum
        if window_size < min_window_size:
            logger.debug("Skipping window with %d messages (min=%d)", window_size, min_window_size)
            current_start += delta  # Advance without overlap
            continue

        window_id = f"window_{current_start.strftime('%Y%m%d_%H%M%S')}"

        yield Window(
            window_id=window_id,
            window_index=window_index,
            start_time=current_start,
            end_time=current_end,
            table=window_table,
            size=window_size,
        )

        window_index += 1
        current_start += delta  # Advance by delta, creating overlap


def _window_by_bytes(
    table: Table,
    step_size: int,
    min_window_size: int,
    overlap: int = 0,
) -> Iterator[Window]:
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


def _apply_time_limit(windows: Iterator[Window], max_time: timedelta) -> Iterator[Window]:
    """Split windows that exceed max_time duration.

    Args:
        windows: Generator of windows to process
        max_time: Maximum allowed duration per window

    Yields:
        Windows split to respect max_time constraint

    """
    for window in windows:
        duration = window.end_time - window.start_time

        if duration <= max_time:
            yield window
            continue

        # Split window into smaller time chunks
        # Simplified: just split in half for now
        mid_time = window.start_time + (duration / 2)

        first_half = window.table.filter(window.table.timestamp < mid_time)
        second_half = window.table.filter(window.table.timestamp >= mid_time)

        first_size = first_half.count().execute()
        second_size = second_half.count().execute()

        if first_size > 0:
            yield Window(
                window_id=f"{window.window_id}_a",
                window_index=window.window_index,
                start_time=window.start_time,
                end_time=mid_time,
                table=first_half,
                size=first_size,
            )

        if second_size > 0:
            yield Window(
                window_id=f"{window.window_id}_b",
                window_index=window.window_index + 1,
                start_time=mid_time,
                end_time=window.end_time,
                table=second_half,
                size=second_size,
            )


def _get_min_timestamp(table: Table) -> datetime:
    """Get minimum timestamp from table."""
    result = table.aggregate(table.timestamp.min().name("min_ts")).execute()
    return result["min_ts"][0]


def _get_max_timestamp(table: Table) -> datetime:
    """Get maximum timestamp from table."""
    result = table.aggregate(table.timestamp.max().name("max_ts")).execute()
    return result["max_ts"][0]


def split_window_in_half(window: Window) -> tuple[Window | None, Window | None]:
    """Split a window in half by time.

    Args:
        window: Window to split

    Returns:
        Tuple of (first_half, second_half) windows. Either can be None if empty.

    """
    duration = window.end_time - window.start_time
    mid_time = window.start_time + (duration / 2)

    first_half = window.table.filter(window.table.timestamp < mid_time)
    second_half = window.table.filter(window.table.timestamp >= mid_time)

    first_size = first_half.count().execute()
    second_size = second_half.count().execute()

    first_window = None
    if first_size > 0:
        first_window = Window(
            window_id=f"{window.window_id}_a",
            window_index=window.window_index,
            start_time=window.start_time,
            end_time=mid_time,
            table=first_half,
            size=first_size,
        )

    second_window = None
    if second_size > 0:
        second_window = Window(
            window_id=f"{window.window_id}_b",
            window_index=window.window_index + 1,
            start_time=mid_time,
            end_time=window.end_time,
            table=second_half,
            size=second_size,
        )

    return first_window, second_window
