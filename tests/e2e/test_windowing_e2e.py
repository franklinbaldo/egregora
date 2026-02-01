"""E2E tests for windowing transformation logic.

These tests verify the behavior of the windowing engine against a real DuckDB backend,
ensuring that:
1. Message-based windowing correctly slices data.
2. Time-based windowing respects time boundaries and overlaps.
3. Byte-based windowing packs messages efficiently.
4. Window splitting works as expected.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import ibis
import pytest
from ibis import schema

from egregora.config.settings import EgregoraConfig
from egregora.transformations.windowing import (
    WindowConfig,
    create_windows,
    generate_window_signature,
    split_window_into_n_parts,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@pytest.fixture
def messages_table():
    """Create an in-memory DuckDB table with messages."""
    con = ibis.duckdb.connect()

    # Generate 100 messages over 10 hours (10 messages per hour)
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    data = []

    for i in range(100):
        # Varying message length for byte windowing
        msg_len = (i % 10) + 1  # 1 to 10 chars
        data.append({
            "ts": base_time + timedelta(minutes=i * 6),  # Every 6 minutes
            "text": "x" * msg_len,
            "author": f"user_{i%5}",
            "source": "whatsapp"
        })

    t = ibis.memtable(data)
    # Ensure schema matches what windowing expects (ts, text)
    return t


def test_window_by_messages(messages_table):
    """Test count-based windowing (step_unit='messages')."""
    config = WindowConfig(step_size=20, step_unit="messages", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))

    assert len(windows) == 5  # 100 / 20 = 5
    assert windows[0].size == 20
    assert windows[4].size == 20

    # Test overlap
    config_overlap = WindowConfig(step_size=20, step_unit="messages", overlap_ratio=0.5)
    windows_overlap = list(create_windows(messages_table, config=config_overlap))

    # Overlap extends the window but doesn't change the step count (windows start every 20)
    assert len(windows_overlap) == 5
    # Size should be ~30 (20 + 10 overlap), except last ones might be clipped
    assert windows_overlap[0].size == 30
    assert windows_overlap[4].size == 20  # Last window clipped at end


def test_window_by_time_hours(messages_table):
    """Test time-based windowing (step_unit='hours')."""
    # 100 messages over 10 hours (600 minutes total range: 12:00 to 21:54)
    # step_size=2 hours -> ~5 windows
    config = WindowConfig(step_size=2, step_unit="hours", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))

    # 10 hours / 2 hours = 5 windows
    assert len(windows) == 5

    # Each window should span 2 hours. 10 msgs/hour -> ~20 msgs/window
    # Note: Using >= start < end logic.
    assert windows[0].size == 20
    assert (windows[0].end_time - windows[0].start_time) == timedelta(hours=2)


def test_window_by_time_days(messages_table):
    """Test time-based windowing (step_unit='days')."""
    # 100 messages over 10 hours. 1 day window should cover everything.
    config = WindowConfig(step_size=1, step_unit="days", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))

    assert len(windows) == 1
    assert windows[0].size == 100


def test_window_by_bytes(messages_table):
    """Test byte-based windowing (step_unit='bytes')."""
    # Messages have lengths 1..10 chars. Avg ~5.5 chars.
    # 100 messages -> ~550 bytes.
    # Max bytes = 100 -> ~5 windows.

    config = WindowConfig(max_bytes_per_window=100, step_unit="bytes", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))

    # Should be around 5-6 windows
    assert len(windows) >= 5

    # Verify sizes are roughly constrained
    # Note: _window_by_bytes logic allows first message to exceed, but subsequent ones fit.
    # With small messages, it should fit closely.
    for w in windows:
        # Re-fetch size
        text_len = w.table.text.length().sum().execute()
        # It's possible to slightly exceed if one message is huge, but here max is 10.
        # However, the logic is: sum(start+1..end) <= max_bytes.
        # So total size <= first_msg + max_bytes.
        assert text_len <= 100 + 10  # Tolerance for first message


def test_split_window_into_n_parts(messages_table):
    """Test splitting a window."""
    # Create a window that spans 10 hours (full data range)
    # Data is 12:00 to 22:00 (approx)
    # Disable overlap to simplify splitting math
    config = WindowConfig(step_size=12, step_unit="hours", overlap_ratio=0.0)
    windows = list(create_windows(messages_table, config=config))
    main_window = windows[0]

    # Split into 2 parts (6 hours each)
    # Part 1: 12:00 - 18:00
    # Part 2: 18:00 - 00:00
    parts = split_window_into_n_parts(main_window, 2)

    assert len(parts) == 2

    # 100 messages over 10 hours = 10 msgs/hour
    # Part 1 (6 hours): ~60 messages
    # Part 2 (4 hours overlap with data): ~40 messages

    assert abs(parts[0].size - 60) <= 5
    assert abs(parts[1].size - 40) <= 5

    # Total size matches
    assert parts[0].size + parts[1].size == 100


def test_generate_window_signature(messages_table):
    """Test signature generation."""
    config = EgregoraConfig()
    config.models.writer = "test-model"
    template = "Prompt template"

    sig = generate_window_signature(
        window_table=messages_table,
        config=config,
        prompt_template=template
    )

    assert isinstance(sig, str)
    assert len(sig.split(":")) == 3
