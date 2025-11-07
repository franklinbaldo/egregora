"""Generic pipeline utilities for windowing and organizing messages.

MODERN (Phase 6): Replaced period-based grouping with flexible windowing.
- Supports message count, time-based, and byte-based windowing
- Sequential window indices for simple resume logic
- No calendar edge cases (ISO weeks, timezone conversions, etc.)

MODERN (Phase 7): Checkpoint-based resume logic.
- Resume uses sentinel file tracking last processed timestamp
- Post dates are LLM-decided based on message content
- Windows are ephemeral processing batches (not tied to resume state)

DESIGN PHILOSOPHY: Calculate, Don't Iterate
- When constraints would be exceeded, calculate the exact reduction factor needed
- max_window_time: Calculate effective_step_size = max_time / (1 + overlap_ratio)
- Context limits: Calculate num_splits = ceil(estimated_tokens / effective_limit)
- This avoids trial-and-error iteration and ensures deterministic behavior
"""

import json
import logging
import math
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

    Note: No window_id needed - use (start_time, end_time) for identification.
    """

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

    Overlap provides conversation context across window boundaries, improving
    LLM understanding and blog post quality at the cost of ~20% more tokens.

    Args:
        table: Table with timestamp column
        step_size: Size of each window
        step_unit: Unit for windowing ("messages", "hours", "days")
        min_window_size: Minimum messages per window (skip smaller windows)
        overlap_ratio: Fraction of window to overlap (0.0-0.5, default 0.2 = 20%)
        max_window_time: Optional maximum time span per window

    Yields:
        Window objects with overlapping message sets

    Examples:
        >>> # 100 messages per window with 20% overlap
        >>> for window in create_windows(table, step_size=100, step_unit="messages"):
        ...     print(f"Processing window {window.window_index}: {window.size} messages")
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
        # For message-based windowing, we still need time limit check
        # (can't predict time span of N messages upfront)
        if max_window_time:
            windows = _apply_time_limit(windows, max_window_time)
    elif step_unit in ("hours", "days"):
        # Dynamically reduce step_size if max_window_time constraint would be exceeded
        effective_step_size = step_size
        effective_step_unit = step_unit

        if max_window_time:
            # Convert step_size to timedelta
            if step_unit == "hours":
                requested_delta = timedelta(hours=step_size)
            else:  # days
                requested_delta = timedelta(days=step_size)

            # If requested window exceeds max, reduce to max
            if requested_delta > max_window_time:
                # Account for overlap: window_duration = step_size * (1 + overlap_ratio)
                # So: effective_step_size = max_window_time / (1 + overlap_ratio)
                max_with_overlap = max_window_time / (1 + overlap_ratio)

                # Convert to appropriate unit
                max_hours = max_with_overlap.total_seconds() / 3600
                if max_hours < 24:
                    # Use hours if < 1 day (floor to avoid exceeding)
                    effective_step_size = int(math.floor(max_hours))
                    effective_step_size = max(effective_step_size, 1)  # Minimum 1 hour
                    effective_step_unit = "hours"
                else:
                    # Use days if >= 1 day (floor to avoid exceeding)
                    effective_step_size = int(math.floor(max_with_overlap.days))
                    effective_step_size = max(effective_step_size, 1)  # Minimum 1 day
                    effective_step_unit = "days"

                logger.info(
                    "🔧 [yellow]Adjusted window size:[/] %s %s → %s %s (max_window_time=%s)",
                    step_size,
                    step_unit,
                    effective_step_size,
                    effective_step_unit,
                    max_window_time,
                )

        windows = _window_by_time(
            sorted_table, effective_step_size, effective_step_unit, min_window_size, overlap_ratio
        )
    else:
        msg = f"Unknown step_unit: {step_unit}. Must be 'messages', 'hours', or 'days'."
        raise ValueError(msg)

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

        yield Window(
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

    while current_start <= max_ts:  # Use <= to handle single-timestamp datasets
        current_end = current_start + delta + overlap_delta

        # Filter messages in this window
        window_table = table.filter((table.timestamp >= current_start) & (table.timestamp < current_end))

        window_size = window_table.count().execute()

        # Skip if below minimum
        if window_size < min_window_size:
            logger.debug("Skipping window with %d messages (min=%d)", window_size, min_window_size)
            current_start += delta  # Advance without overlap
            continue

        yield Window(
            window_index=window_index,
            start_time=current_start,
            end_time=current_end,
            table=window_table,
            size=window_size,
        )

        window_index += 1
        current_start += delta  # Advance by delta, creating overlap


def _apply_time_limit(windows: Iterator[Window], max_time: timedelta) -> Iterator[Window]:
    """Safety check: split any windows that still exceed max_time duration.

    NOTE: With dynamic step_size reduction (Phase 7+), this should rarely
    trigger. Kept as defensive programming for edge cases.

    Args:
        windows: Generator of windows to process
        max_time: Maximum allowed duration per window

    Yields:
        Windows, split if they exceed the constraint

    """
    for window in windows:
        duration = window.end_time - window.start_time

        if duration <= max_time:
            yield window
            continue

        # Edge case: window still exceeds limit (shouldn't happen with dynamic reduction)
        logger.warning(
            "⚠️  Window exceeded max_window_time despite dynamic reduction (edge case). "
            "Duration: %s, Max: %s. Splitting...",
            duration,
            max_time,
        )

        # Calculate splits needed and recursively split
        num_splits = math.ceil(duration / max_time)
        split_windows = split_window_into_n_parts(window, num_splits)
        yield from _apply_time_limit(iter(split_windows), max_time)


def _get_min_timestamp(table: Table) -> datetime:
    """Get minimum timestamp from table."""
    result = table.aggregate(table.timestamp.min().name("min_ts")).execute()
    return result["min_ts"][0]


def _get_max_timestamp(table: Table) -> datetime:
    """Get maximum timestamp from table."""
    result = table.aggregate(table.timestamp.max().name("max_ts")).execute()
    return result["max_ts"][0]


def split_window_into_n_parts(window: Window, n: int) -> list[Window]:
    """Split a window into N equal parts by time.

    Args:
        window: Window to split
        n: Number of parts to split into (must be >= 2)

    Returns:
        List of windows (may be shorter than n if some time ranges are empty)

    Raises:
        ValueError: If n < 2

    """
    min_splits = 2
    if n < min_splits:
        msg = f"Cannot split into {n} parts (must be >= {min_splits})"
        raise ValueError(msg)

    duration = window.end_time - window.start_time
    part_duration = duration / n

    windows = []
    for i in range(n):
        part_start = window.start_time + (part_duration * i)
        part_end = window.start_time + (part_duration * (i + 1)) if i < n - 1 else window.end_time

        part_table = window.table.filter(
            (window.table.timestamp >= part_start) & (window.table.timestamp < part_end)
        )

        part_size = part_table.count().execute()
        if part_size > 0:
            part_window = Window(
                window_index=window.window_index,
                start_time=part_start,
                end_time=part_end,
                table=part_table,
                size=part_size,
            )
            windows.append(part_window)

    return windows
