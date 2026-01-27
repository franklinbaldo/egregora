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

import bisect
import hashlib
import itertools
import logging
import math
from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import accumulate

import ibis
from ibis.expr.types import Table

from egregora.agents.formatting import build_conversation_xml
from egregora.config.settings import EgregoraConfig
from egregora.transformations.exceptions import InvalidSplitError, InvalidStepUnitError

logger = logging.getLogger(__name__)

# Constants
HOURS_PER_DAY = 24  # Hours in a day for time unit conversion


# ============================================================================
# Checkpoint / Sentinel File Utilities
# ============================================================================

# DEPRECATED: Checkpoints are now handled via DocumentType.JOURNAL in database.
# Functions load_checkpoint/save_checkpoint removed.


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

    The `table` field contains a filtered view of data (STAGING_MESSAGES_SCHEMA).

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
        raise InvalidStepUnitError(config.step_unit)


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
        requested_delta = timedelta(hours=step_size) if step_unit == "hours" else timedelta(days=step_size)

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

    Optimized implementation using "Fetch-then-Compute" pattern:
    1. Fetches all timestamps in a single query (O(1) queries).
    2. Computes window boundaries in Python using simple arithmetic.
    3. Yields windows with lazy Ibis table slices using limit/offset.

    Args:
        table: Sorted table of messages
        step_size: Number of messages per window (before overlap)
        overlap: Number of messages to overlap with previous window

    Yields:
        Windows with overlapping message sets

    """
    # 1. Fetch metadata (timestamp) for all rows in one query.
    # We rely on the implicit row ordering provided by timestamp sorting.
    timestamps = table.select("ts").order_by("ts").execute()["ts"].tolist()

    total_count = len(timestamps)
    if total_count == 0:
        return

    # 2. Iterate and define windows locally
    num_windows = (total_count + step_size - 1) // step_size

    for i in range(num_windows):
        offset = i * step_size
        # The window extends by step_size + overlap, but cannot exceed total count
        end_idx = min(offset + step_size + overlap, total_count)
        chunk_size = end_idx - offset

        if chunk_size <= 0:
            continue

        # Get time bounds from pre-fetched metadata
        start_time = timestamps[offset]
        end_time = timestamps[end_idx - 1]

        # Construct lazy table using limit/offset
        # Critical: Must apply order_by("ts") again to ensure limit/offset is deterministic
        window_table = table.order_by("ts").limit(chunk_size, offset=offset)

        yield Window(
            window_index=i,
            start_time=start_time,
            end_time=end_time,
            table=window_table,
            size=chunk_size,
        )


def _window_by_time(
    table: Table,
    step_size: int,
    step_unit: str,
    overlap_ratio: float = 0.0,
) -> Iterator[Window]:
    """Generate windows of fixed time duration with optional overlap.

    This implementation is declarative and vectorized, using Ibis window
    functions and unnesting to calculate window memberships in a single pass.

    Args:
        table: Sorted table of messages
        step_size: Duration of each window
        step_unit: "hours" or "days"
        overlap_ratio: Fraction of time window to overlap (0.0-0.5)

    Yields:
        Windows with overlapping time ranges

    """
    # Get overall time range
    bounds = table.aggregate(
        min_ts=table.ts.min(),
        max_ts=table.ts.max(),
    ).execute()
    min_ts = bounds["min_ts"][0]
    max_ts = bounds["max_ts"][0]

    # Calculate window duration
    delta = timedelta(hours=step_size) if step_unit == "hours" else timedelta(days=step_size)
    overlap_delta = delta * overlap_ratio

    # Calculate total seconds for vectorized math
    step_sec = delta.total_seconds()
    overlap_sec = overlap_delta.total_seconds()

    # Calculate number of windows
    # We loop until current_start > max_ts.
    # start = min_ts + i * delta
    # min_ts + i * delta <= max_ts  -> i * delta <= max_ts - min_ts
    total_duration = (max_ts - min_ts).total_seconds()
    num_windows = math.floor(total_duration / step_sec) + 1

    # Vectorized count calculation:
    # 1. Calculate offset in seconds from min_ts
    # 2. Assign range of window indices [lower, upper]
    # 3. Unnest and group count

    min_ts_timestamp = min_ts.timestamp()

    t = table.mutate(offset_sec=table.ts.epoch_seconds() - int(min_ts_timestamp))

    t = t.mutate(
        lower_idx=((t.offset_sec - step_sec - overlap_sec) / step_sec).floor().cast("int") + 1,
        upper_idx=(t.offset_sec / step_sec).floor().cast("int"),
    )

    t = t.mutate(lower_idx=ibis.greatest(t.lower_idx, 0))

    # [lower, upper] inclusive, so range(lower, upper + 1)
    t = t.mutate(window_indices=ibis.range(t.lower_idx, t.upper_idx + 1))

    # We must explicitly name the count column to avoid backend-specific default names (e.g. CountStar())
    unnested = t.unnest("window_indices")
    window_counts = unnested.group_by("window_indices").aggregate(count=unnested.count()).execute()

    # Convert counts to dict for O(1) lookup
    # Iterate and cast to native int to avoid numpy/arrow types
    counts_map = {int(row["window_indices"]): int(row["count"]) for _, row in window_counts.iterrows()}

    current_start = min_ts
    for i in range(num_windows):
        current_end = current_start + delta + overlap_delta

        size = counts_map.get(i, 0)

        # Reconstruct the window table expression
        window_table = table.filter((table.ts >= current_start) & (table.ts < current_end))

        yield Window(
            window_index=i,
            start_time=current_start,
            end_time=current_end,
            table=window_table,
            size=size,
        )

        current_start += delta


def _window_by_bytes(
    table: Table,
    max_bytes: int,
    overlap_bytes: int = 0,
) -> Iterator[Window]:
    """Generate windows by packing messages up to a byte limit.

    Optimized implementation using "Fetch-then-Compute" pattern:
    1. Fetches metadata (row_number, timestamp, length) for all rows in one query.
    2. Computes window boundaries efficiently using prefix sums and bisect (O(log N)).
    3. Yields windows with precise row_number filtering.

    Byte-to-token ratio: ~4 bytes per token (industry standard).

    Args:
        table: Sorted table of messages
        max_bytes: Maximum bytes per window
        overlap_bytes: Bytes to overlap between windows

    Yields:
        Windows packed to maximum byte capacity

    """
    # 1. Fetch metadata (Fetch phase)
    # Add row_number to allow precise, efficient slicing without limit/offset scaling issues.
    table_with_rn = table.mutate(row_number=ibis.row_number().over(ibis.window(order_by=table.ts)))

    metadata = (
        table_with_rn.select(
            rn=table_with_rn.row_number,
            ts=table_with_rn.ts,
            msg_bytes=table_with_rn.text.length().cast("int64"),
        )
        .order_by("rn")
        .execute()
    )

    total_count = len(metadata)
    if total_count == 0:
        return

    # Extract columns
    row_numbers = metadata["rn"].tolist()
    timestamps = metadata["ts"].tolist()
    msg_bytes_list = metadata["msg_bytes"].tolist()

    # 2. Compute window boundaries (Compute phase)
    # Prefix sum for O(1) range sum queries: accum_bytes[i] = sum(bytes[0]...bytes[i-1])
    accum_bytes = [0] + list(accumulate(msg_bytes_list))

    current_start_idx = 0
    window_index = 0

    while current_start_idx < total_count:
        # Find end index such that sum(start+1..end) <= max_bytes
        # Legacy behavior: The first message's size is ignored in the limit check.
        # sum(start+1..end) = accum_bytes[end] - accum_bytes[start+1]
        # accum_bytes[end] <= accum_bytes[start+1] + max_bytes

        # Check if we have at least one message
        if current_start_idx >= total_count:
            break

        # Calculate target based on start+1 to ignore first message size
        # accum_bytes has length total_count + 1.
        base_idx = min(current_start_idx + 1, len(accum_bytes) - 1)
        target_sum = accum_bytes[base_idx] + max_bytes

        # bisect_right returns the first index where val > target_sum.
        # We want the last index where val <= target_sum, so index - 1.
        end_idx = bisect_right(accum_bytes, target_sum, lo=current_start_idx + 1) - 1

        # Ensure at least one message is included if the first message exceeds max_bytes
        if end_idx <= current_start_idx:
            end_idx = current_start_idx + 1

        # Ensure we don't go past the end
        if end_idx > total_count:
            end_idx = total_count

        chunk_size = end_idx - current_start_idx

        # Get boundaries
        start_rn = row_numbers[current_start_idx]
        # row_number logic: inclusive start, exclusive end for logic, but filter works on values.
        # If we use range(start_idx, end_idx), we want rows with indices start_idx ... end_idx - 1.
        # Their row_numbers are row_numbers[start_idx] ... row_numbers[end_idx - 1].
        # So filter(rn >= start_rn & rn <= end_rn)
        end_rn = row_numbers[end_idx - 1]

        start_time = timestamps[current_start_idx]
        end_time = timestamps[end_idx - 1]

        # Construct window table
        window_table = table_with_rn.filter(
            (table_with_rn.row_number >= start_rn) &
            (table_with_rn.row_number <= end_rn)
        ).drop("row_number")

        yield Window(
            window_index=window_index,
            start_time=start_time,
            end_time=end_time,
            table=window_table,
            size=chunk_size,
        )

        window_index += 1

        # Calculate next start index with overlap
        # We want to overlap such that shared bytes <= overlap_bytes.
        # Shared range is [next_start, end).
        # sum(next_start..end) <= overlap_bytes.
        # accum_bytes[end] - accum_bytes[next_start] <= overlap_bytes.
        # accum_bytes[next_start] >= accum_bytes[end] - overlap_bytes.

        # Note: Overlap logic strictly counts ALL bytes in the overlap region,
        # unlike the window limit which might ignore the first message.
        target_overlap = accum_bytes[end_idx] - overlap_bytes
        next_start_idx = bisect_left(accum_bytes, target_overlap, lo=current_start_idx, hi=end_idx)

        # Ensure forward progress
        if next_start_idx <= current_start_idx:
            next_start_idx = current_start_idx + 1

        current_start_idx = next_start_idx


def split_window_into_n_parts(window: Window, n: int) -> list[Window]:
    """Split a window into N equal parts by time.

    Args:
        window: Window to split
        n: Number of parts to split into (must be >= 2)

    Returns:
        List of windows (may be shorter than n if some time ranges are empty)

    Raises:
        InvalidSplitError: If n < 2

    """
    min_splits = 2
    if n < min_splits:
        raise InvalidSplitError(n)

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
    window_table: Table | None,
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
        window_table: The window's data table (Optional if xml_content is provided).
        config: Pipeline configuration.
        prompt_template: Raw template string for the writer prompt.
        xml_content: Optional pre-computed XML content to hash (avoid re-generating).

    """
    # 1. Data Hash
    if xml_content:
        data_hash = hashlib.sha256(xml_content.encode()).hexdigest()
    elif window_table is not None:
        # Fallback to generating XML for hash consistency
        # (We use XML because that's what the LLM sees)
        xml_content = build_conversation_xml(window_table.to_pyarrow(), None)
        data_hash = hashlib.sha256(xml_content.encode()).hexdigest()
    else:
        msg = "Either xml_content or window_table must be provided"
        raise ValueError(msg)

    # 2. Logic Hash
    # Combine template and user instructions
    custom_instructions = config.writer.custom_instructions or ""
    logic_input = f"{prompt_template}:{custom_instructions}"
    logic_hash = hashlib.sha256(logic_input.encode()).hexdigest()

    # 3. Engine Hash
    model_hash = config.models.writer

    return f"{data_hash}:{logic_hash}:{model_hash}"
