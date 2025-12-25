"""Generic pipeline utilities for windowing and organizing messages.

MODERN (Phase 6): Replaced period-based grouping with flexible windowing.
- Supports message count, time-based, and byte-based windowing
- Sequential window indices for simple resume logic
- No calendar edge cases (ISO weeks, timezone conversions, etc.)

MODERN (Phase 7): Checkpoint-based resume logic.
- Resume uses sentinel file tracking last processed timestamp
- Post dates are LLM-decided based on message content
- Windows are ephemeral processing batches (not tied to resume state)

MODERN (Phase 2): Moved from top-level pipeline.py to pipeline/windowing.py.
- Consolidates all windowing logic in pipeline/ subdirectory
- Re-exported from pipeline/__init__.py for backward compatibility

DESIGN PHILOSOPHY: Calculate, Don't Iterate
- When max_window_time constraint would be exceeded, calculate exact reduction upfront
- max_window_time constrains the **step** (advancement), not the overlap-adjusted span
- Formula: effective_step_size = max_window_time (actual span will be x (1 + overlap_ratio))
- Creates correctly-sized windows from the start (no post-hoc splitting)
- Only applies to time-based windowing (hours/days); message-based windowing
  cannot enforce time limits without knowing message density beforehand
"""

import hashlib
import json
import logging
import math
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import ibis
from ibis.expr.types import Table

from egregora.agents.formatting import build_conversation_xml
from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)

# Constants
HOURS_PER_DAY = 24  # Hours in a day for time unit conversion


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

    utc_zone = ZoneInfo("UTC")
    if last_timestamp.tzinfo is None:
        last_timestamp = last_timestamp.replace(tzinfo=utc_zone)
    else:
        last_timestamp = last_timestamp.astimezone(utc_zone)

    checkpoint = {
        "last_processed_timestamp": last_timestamp.isoformat(),
        "messages_processed": int(messages_processed),
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

    The `table` field contains a filtered view of data (IR_MESSAGE_SCHEMA).

    Note: No window_id needed - use (start_time, end_time) for identification.
    """

    window_index: int
    start_time: datetime
    end_time: datetime
    table: Table  # Filtered view of data (not a separate DB schema)
    size: int  # Number of messages


@dataclass
class WindowConfig:
    """Configuration for window creation."""

    step_size: int = 100
    step_unit: str = "messages"
    overlap_ratio: float = 0.2
    max_window_time: timedelta | None = None
    max_bytes_per_window: int = 320_000


def create_windows(
    table: Table,
    *,
    config: WindowConfig | None = None,
) -> Iterator[Window]:
    """Create processing windows from messages with overlap for context continuity.

    Replaces period-based grouping with flexible windowing:
    - By message count: step_size=100, step_unit="messages"
    - By time: step_size=2, step_unit="days"
    - By byte packing: step_unit="bytes" (maximizes context per window)

    Overlap provides conversation context across window boundaries, improving
    LLM understanding and blog post quality at the cost of ~20% more tokens.

    Byte packing mode (step_unit="bytes") ignores time boundaries and packs
    messages to maximize context usage (~4 bytes/token). This minimizes
    API calls but may produce less time-coherent posts.

    All windows are processed - the LLM decides if content warrants a post.

    Args:
        table: Table with timestamp column
        config: Window creation configuration

    Yields:
        Window objects with overlapping message sets

    Examples:
        >>> # 100 messages per window with 20% overlap
        >>> config = WindowConfig(step_size=100, step_unit="messages")
        >>> for window in create_windows(table, config=config):
        ...     print(f"Processing window {window.window_index}: {window.size} messages")

    """
    if config is None:
        config = WindowConfig()
    if table.count().execute() == 0:
        return

    normalized_unit = config.step_unit.lower()
    normalized_ratio = max(0.0, min(config.overlap_ratio, 0.5))

    if normalized_ratio != config.overlap_ratio:
        logger.info(
            "Adjusted overlap_ratio from %s to %s (supported range: 0.0-0.5)",
            config.overlap_ratio,
            normalized_ratio,
        )

    sorted_table = table.order_by(table.ts)

    if normalized_unit == "messages":
        yield from _prepare_message_windows(
            sorted_table,
            step_size=config.step_size,
            overlap_ratio=normalized_ratio,
            max_window_time=config.max_window_time,
        )
    elif normalized_unit in {"hours", "days"}:
        yield from _prepare_time_windows(
            sorted_table,
            step_size=config.step_size,
            step_unit=normalized_unit,
            overlap_ratio=normalized_ratio,
            max_window_time=config.max_window_time,
        )
    elif normalized_unit == "bytes":
        yield from _prepare_byte_windows(
            sorted_table,
            max_bytes_per_window=config.max_bytes_per_window,
            overlap_ratio=normalized_ratio,
        )
    else:
        msg = f"Unknown step_unit: {config.step_unit}. Must be 'messages', 'hours', 'days', or 'bytes'."
        raise ValueError(msg)


def _prepare_message_windows(
    table: Table,
    *,
    step_size: int,
    overlap_ratio: float,
    max_window_time: timedelta | None,
) -> Iterator[Window]:
    """Normalize message-based inputs and generate windows."""
    overlap = int(step_size * overlap_ratio)

    if max_window_time:
        logger.warning(
            "⚠️  max_window_time constraint not enforced for message-based windowing. "
            "Use time-based windowing (--step-unit=hours/days) for strict time limits."
        )

    yield from _window_by_count(table, step_size, overlap)


def _prepare_time_windows(
    table: Table,
    *,
    step_size: int,
    step_unit: str,
    overlap_ratio: float,
    max_window_time: timedelta | None,
) -> Iterator[Window]:
    """Normalize time-based inputs (including max_window_time) and generate windows."""
    effective_step_size = step_size
    effective_step_unit = step_unit

    if max_window_time:
        if step_unit == "hours":
            requested_delta = timedelta(hours=step_size)
        else:
            requested_delta = timedelta(days=step_size)

        if requested_delta > max_window_time:
            max_with_overlap = max_window_time / (1 + overlap_ratio)
            max_hours = max_with_overlap.total_seconds() / 3600

            if max_hours < HOURS_PER_DAY:
                effective_step_size = max(math.floor(max_hours), 1)
                effective_step_unit = "hours"
            else:
                effective_step_size = max(math.floor(max_with_overlap.days), 1)
                effective_step_unit = "days"

            logger.info(
                "🔧 [yellow]Adjusted window size:[/] %s %s → %s %s (max_window_time=%s)",
                step_size,
                step_unit,
                effective_step_size,
                effective_step_unit,
                max_window_time,
            )

    yield from _window_by_time(
        table,
        effective_step_size,
        effective_step_unit,
        overlap_ratio,
    )


def _prepare_byte_windows(
    table: Table,
    *,
    max_bytes_per_window: int,
    overlap_ratio: float,
) -> Iterator[Window]:
    """Normalize byte-based inputs and generate windows."""
    overlap_bytes = int(max_bytes_per_window * overlap_ratio)
    yield from _window_by_bytes(table, max_bytes_per_window, overlap_bytes)


def _window_by_count(
    table: Table,
    step_size: int,
    overlap: int = 0,
) -> Iterator[Window]:
    """Generate windows of fixed message count with optional overlap.

    Overlap provides conversation context across window boundaries:
    - Window 1: messages [0-119] (100 + 20 overlap)
    - Window 2: messages [100-219] (100 + 20 overlap)
    - Messages 100-119 appear in both windows for context

    All windows are processed - the LLM decides if content warrants a post.

    Args:
        table: Sorted table of messages
        step_size: Number of messages per window (before overlap)
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
    overlap_ratio: float = 0.0,
) -> Iterator[Window]:
    """Generate windows of fixed time duration with optional overlap.

    Time overlap ensures conversation threads spanning window boundaries
    maintain context for the LLM.

    All windows are processed - the LLM decides if content warrants a post.

    Args:
        table: Sorted table of messages
        step_size: Duration of each window
        step_unit: "hours" or "days"
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

        # Filter messages in this window (IR v1: use .ts column)
        window_table = table.filter((table.ts >= current_start) & (table.ts < current_end))

        window_size = window_table.count().execute()

        yield Window(
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
    max_bytes: int,
    overlap_bytes: int = 0,
) -> Iterator[Window]:
    """Generate windows by packing messages up to a byte limit.

    Uses DuckDB window functions for efficient cumulative byte calculation.
    This mode ignores time boundaries and maximizes context per window,
    trading time-coherence for fewer API calls.

    Byte-to-token ratio: ~4 bytes per token (industry standard).

    Args:
        table: Sorted table of messages
        max_bytes: Maximum bytes per window
        overlap_bytes: Bytes to overlap between windows

    Yields:
        Windows packed to maximum byte capacity

    """
    # Add row number and byte length columns (IR v1: use .ts and .text columns)
    enriched = table.mutate(
        row_num=ibis.row_number().over(ibis.window(order_by=[table.ts])),
        msg_bytes=table.text.length().cast("int64"),
    )

    # Calculate cumulative bytes
    windowed = enriched.mutate(
        cumulative_bytes=enriched.msg_bytes.sum().over(ibis.window(order_by=[enriched.ts], rows=(None, 0)))
    )

    # Materialize to avoid recomputation
    materialized = windowed.cache()
    total_count = materialized.count().execute()

    if total_count == 0:
        return

    window_index = 0
    offset = 0

    while offset < total_count:
        # Get chunk starting from offset
        chunk = materialized.limit(total_count - offset, offset=offset)

        # Reset cumulative bytes relative to chunk start
        chunk_with_relative = chunk.mutate(
            relative_bytes=chunk.cumulative_bytes - chunk.cumulative_bytes.min()
        )

        # Find messages that fit within max_bytes
        fitting = chunk_with_relative.filter(chunk_with_relative.relative_bytes <= max_bytes)
        chunk_size = fitting.count().execute()

        if chunk_size == 0:
            # Edge case: single message exceeds limit, take it anyway
            chunk_size = 1

        # Create window from these messages
        window_table = materialized.limit(chunk_size, offset=offset)

        # Get time bounds
        start_time = _get_min_timestamp(window_table)
        end_time = _get_max_timestamp(window_table)

        yield Window(
            window_index=window_index,
            start_time=start_time,
            end_time=end_time,
            table=window_table.drop(["row_num", "msg_bytes", "cumulative_bytes"]),  # Clean up temp columns
            size=chunk_size,
        )

        window_index += 1

        # Calculate overlap in messages (approximate from bytes)
        if overlap_bytes > 0 and chunk_size > 1:
            # Find how many messages from end fit in overlap_bytes (IR v1: use .text and .ts columns)
            # window_table is already the correct chunk, no need for tail()
            tail_with_bytes = window_table.mutate(msg_bytes_col=window_table.text.length())

            # Cumulative bytes from end (reverse order using DESC)
            tail_cumsum = tail_with_bytes.mutate(
                reverse_cum=tail_with_bytes.msg_bytes_col.sum().over(
                    ibis.window(order_by=[tail_with_bytes.ts.desc()], rows=(None, 0))
                )
            )

            overlap_rows_table = tail_cumsum.filter(tail_cumsum.reverse_cum <= overlap_bytes)
            overlap_rows = overlap_rows_table.count().execute()

            advance = max(1, chunk_size - overlap_rows)
        else:
            advance = chunk_size

        offset += advance


def _get_min_timestamp(table: Table) -> datetime:
    """Get minimum timestamp from table (IR v1: use .ts column)."""
    result = table.aggregate(table.ts.min().name("min_ts")).execute()
    return result["min_ts"][0]


def _get_max_timestamp(table: Table) -> datetime:
    """Get maximum timestamp from table (IR v1: use .ts column)."""
    result = table.aggregate(table.ts.max().name("max_ts")).execute()
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

        # For the LAST partition, use <= to include messages at window.end_time
        # (critical for message/byte-based windows where end_time == last message timestamp)
        # IR v1: use .ts column
        if i == n - 1:
            part_table = window.table.filter((window.table.ts >= part_start) & (window.table.ts <= part_end))
        else:
            part_table = window.table.filter((window.table.ts >= part_start) & (window.table.ts < part_end))

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


def generate_window_signature(
    window_table: Table,
    config: EgregoraConfig,
    prompt_template: str,
    xml_content: str | None = None,
) -> str:
    """Generate a deterministic signature for a processing window.

    Components:
    1. DATA: Hash of message IDs in the window (derived from XML if provided, else computed).
    2. LOGIC: Hash of the prompt template + custom instructions.
    3. ENGINE: Model ID.

    Args:
        window_table: The window's data table.
        config: Pipeline configuration.
        prompt_template: Raw template string for the writer prompt.
        xml_content: Optional pre-computed XML content to hash (avoid re-generating).

    """
    # 1. Data Hash
    if xml_content:
        data_hash = hashlib.sha256(xml_content.encode()).hexdigest()
    else:
        # Fallback to generating XML for hash consistency
        # (We use XML because that's what the LLM sees)
        xml_content = build_conversation_xml(window_table.to_pyarrow(), None)
        data_hash = hashlib.sha256(xml_content.encode()).hexdigest()

    # 2. Logic Hash
    # Combine template and user instructions
    custom_instructions = config.writer.custom_instructions or ""
    logic_input = f"{prompt_template}:{custom_instructions}"
    logic_hash = hashlib.sha256(logic_input.encode()).hexdigest()

    # 3. Engine Hash
    model_hash = config.models.writer

    return f"{data_hash}:{logic_hash}:{model_hash}"
