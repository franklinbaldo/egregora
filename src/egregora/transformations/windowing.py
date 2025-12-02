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
from abc import ABC, abstractmethod
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
    """Load processing checkpoint from sentinel file."""
    if not checkpoint_path.exists():
        return None

    try:
        with checkpoint_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load checkpoint from %s: %s", checkpoint_path, e)
        return None


def save_checkpoint(checkpoint_path: Path, last_timestamp: datetime, messages_processed: int) -> None:
    """Save processing checkpoint to sentinel file."""
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
    """Represents a processing window of messages (runtime-only construct)."""

    window_index: int
    start_time: datetime
    end_time: datetime
    table: Table  # Filtered view of data (not a separate DB schema)
    size: int  # Number of messages


# ============================================================================
# Windowing Strategies
# ============================================================================


class WindowStrategy(ABC):
    """Abstract base class for windowing strategies."""

    @abstractmethod
    def generate_windows(self, table: Table) -> Iterator[Window]:
        """Generate windows from the table."""


class MessageCountWindowStrategy(WindowStrategy):
    """Strategy for windowing by message count."""

    def __init__(self, step_size: int, overlap_ratio: float, max_window_time: timedelta | None):
        self.step_size = step_size
        self.overlap_ratio = overlap_ratio
        self.max_window_time = max_window_time

    def generate_windows(self, table: Table) -> Iterator[Window]:
        overlap = int(self.step_size * self.overlap_ratio)

        if self.max_window_time:
            logger.warning(
                "⚠️  max_window_time constraint not enforced for message-based windowing. "
                "Use time-based windowing (--step-unit=hours/days) for strict time limits."
            )

        yield from _window_by_count(table, self.step_size, overlap)


class TimeWindowStrategy(WindowStrategy):
    """Strategy for windowing by time duration."""

    def __init__(self, step_size: int, step_unit: str, overlap_ratio: float, max_window_time: timedelta | None):
        self.step_size = step_size
        self.step_unit = step_unit
        self.overlap_ratio = overlap_ratio
        self.max_window_time = max_window_time

    def generate_windows(self, table: Table) -> Iterator[Window]:
        effective_step_size = self.step_size
        effective_step_unit = self.step_unit

        if self.max_window_time:
            if self.step_unit == "hours":
                requested_delta = timedelta(hours=self.step_size)
            else:
                requested_delta = timedelta(days=self.step_size)

            if requested_delta > self.max_window_time:
                max_with_overlap = self.max_window_time / (1 + self.overlap_ratio)
                max_hours = max_with_overlap.total_seconds() / 3600

                if max_hours < HOURS_PER_DAY:
                    effective_step_size = max(math.floor(max_hours), 1)
                    effective_step_unit = "hours"
                else:
                    effective_step_size = max(math.floor(max_with_overlap.days), 1)
                    effective_step_unit = "days"

                logger.info(
                    "🔧 [yellow]Adjusted window size:[/] %s %s → %s %s (max_window_time=%s)",
                    self.step_size,
                    self.step_unit,
                    effective_step_size,
                    effective_step_unit,
                    self.max_window_time,
                )

        yield from _window_by_time(
            table,
            effective_step_size,
            effective_step_unit,
            self.overlap_ratio,
        )


class ByteWindowStrategy(WindowStrategy):
    """Strategy for windowing by byte size."""

    def __init__(self, max_bytes_per_window: int, overlap_ratio: float):
        self.max_bytes_per_window = max_bytes_per_window
        self.overlap_ratio = overlap_ratio

    def generate_windows(self, table: Table) -> Iterator[Window]:
        overlap_bytes = int(self.max_bytes_per_window * self.overlap_ratio)
        yield from _window_by_bytes(table, self.max_bytes_per_window, overlap_bytes)


def create_windows(
    table: Table,
    *,
    step_size: int = 100,
    step_unit: str = "messages",
    overlap_ratio: float = 0.2,
    max_window_time: timedelta | None = None,
    max_bytes_per_window: int = 320_000,
) -> Iterator[Window]:
    """Create processing windows from messages with overlap for context continuity.

    Uses a Strategy pattern to dispatch to the appropriate windowing logic.
    """
    if table.count().execute() == 0:
        return

    normalized_unit = step_unit.lower()
    normalized_ratio = max(0.0, min(overlap_ratio, 0.5))

    if normalized_ratio != overlap_ratio:
        logger.info(
            "Adjusted overlap_ratio from %s to %s (supported range: 0.0-0.5)",
            overlap_ratio,
            normalized_ratio,
        )

    sorted_table = table.order_by(table.ts)
    strategy: WindowStrategy

    if normalized_unit == "messages":
        strategy = MessageCountWindowStrategy(
            step_size=step_size,
            overlap_ratio=normalized_ratio,
            max_window_time=max_window_time,
        )
    elif normalized_unit in {"hours", "days"}:
        strategy = TimeWindowStrategy(
            step_size=step_size,
            step_unit=normalized_unit,
            overlap_ratio=normalized_ratio,
            max_window_time=max_window_time,
        )
    elif normalized_unit == "bytes":
        strategy = ByteWindowStrategy(
            max_bytes_per_window=max_bytes_per_window,
            overlap_ratio=normalized_ratio,
        )
    else:
        msg = f"Unknown step_unit: {step_unit}. Must be 'messages', 'hours', 'days', or 'bytes'."
        raise ValueError(msg)

    yield from strategy.generate_windows(sorted_table)


def _window_by_count(
    table: Table,
    step_size: int,
    overlap: int = 0,
) -> Iterator[Window]:
    """Generate windows of fixed message count with optional overlap."""
    total_count = table.count().execute()
    window_index = 0
    offset = 0

    while offset < total_count:
        chunk_size = min(step_size + overlap, total_count - offset)
        window_table = table.limit(chunk_size, offset=offset)

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
        offset += step_size


def _window_by_time(
    table: Table,
    step_size: int,
    step_unit: str,
    overlap_ratio: float = 0.0,
) -> Iterator[Window]:
    """Generate windows of fixed time duration with optional overlap."""
    min_ts = _get_min_timestamp(table)
    max_ts = _get_max_timestamp(table)

    if step_unit == "hours":
        delta = timedelta(hours=step_size)
    else:
        delta = timedelta(days=step_size)

    overlap_delta = delta * overlap_ratio
    window_index = 0
    current_start = min_ts

    while current_start <= max_ts:
        current_end = current_start + delta + overlap_delta
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
        current_start += delta


def _window_by_bytes(
    table: Table,
    max_bytes: int,
    overlap_bytes: int = 0,
) -> Iterator[Window]:
    """Generate windows by packing messages up to a byte limit.

    Optimized to use SQL window functions and single-pass where possible,
    though strict pagination requires some iteration.
    """
    enriched = table.mutate(
        row_num=ibis.row_number().over(ibis.window(order_by=[table.ts])),
        msg_bytes=table.text.length().cast("int64"),
    )

    windowed = enriched.mutate(
        cumulative_bytes=enriched.msg_bytes.sum().over(ibis.window(order_by=[enriched.ts], rows=(None, 0)))
    )

    # Use PyArrow for local iteration if dataset fits in memory, else paginate via SQL
    # For now, we keep the pagination logic but cleaner
    materialized = windowed.cache()
    total_count = materialized.count().execute()

    if total_count == 0:
        return

    window_index = 0
    offset = 0

    while offset < total_count:
        # Optimized: fetch only necessary columns for calculation
        chunk = materialized.limit(total_count - offset, offset=offset)

        # We need to find the cut-off point. Instead of fetching all rows, we can
        # query for the count of rows that fit.
        # Shift cumulative bytes so this chunk starts at 0
        min_cum = chunk.cumulative_bytes.min()
        fitting_count = chunk.filter(chunk.cumulative_bytes - min_cum <= max_bytes).count().execute()

        chunk_size = max(1, fitting_count) # Ensure at least 1 message

        window_table = materialized.limit(chunk_size, offset=offset)

        # Only fetch timestamps for the window bounds
        bounds = window_table.aggregate(
            start=window_table.ts.min(),
            end=window_table.ts.max()
        ).execute()

        start_time = bounds["start"][0]
        end_time = bounds["end"][0]

        yield Window(
            window_index=window_index,
            start_time=start_time,
            end_time=end_time,
            table=window_table.drop(["row_num", "msg_bytes", "cumulative_bytes"]),
            size=chunk_size,
        )

        window_index += 1

        advance = chunk_size
        if overlap_bytes > 0 and chunk_size > 1:
            # Calculate overlap
            # tail of window_table
            tail_with_bytes = window_table.mutate(msg_bytes_col=window_table.text.length())
            tail_cumsum = tail_with_bytes.mutate(
                reverse_cum=tail_with_bytes.msg_bytes_col.sum().over(
                    ibis.window(order_by=[tail_with_bytes.ts.desc()], rows=(None, 0))
                )
            )
            overlap_rows = tail_cumsum.filter(tail_cumsum.reverse_cum <= overlap_bytes).count().execute()
            advance = max(1, chunk_size - overlap_rows)

        offset += advance


def _get_min_timestamp(table: Table) -> datetime:
    result = table.aggregate(table.ts.min().name("min_ts")).execute()
    return result["min_ts"][0]


def _get_max_timestamp(table: Table) -> datetime:
    result = table.aggregate(table.ts.max().name("max_ts")).execute()
    return result["max_ts"][0]


def split_window_into_n_parts(window: Window, n: int) -> list[Window]:
    """Split a window into N equal parts by time."""
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
    """Generate a deterministic signature for a processing window."""
    if xml_content:
        data_hash = hashlib.sha256(xml_content.encode()).hexdigest()
    else:
        xml_content = build_conversation_xml(window_table.to_pyarrow(), None)
        data_hash = hashlib.sha256(xml_content.encode()).hexdigest()

    custom_instructions = config.writer.custom_instructions or ""
    logic_input = f"{prompt_template}:{custom_instructions}"
    logic_hash = hashlib.sha256(logic_input.encode()).hexdigest()

    return f"{data_hash}:{logic_hash}:{config.models.writer}"
