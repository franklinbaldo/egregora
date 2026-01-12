"""Tests for declarative windowing logic."""

from datetime import datetime, timedelta

import ibis
import pandas as pd  # noqa: TID251
import pytest

from egregora.transformations.windowing import WindowConfig
from egregora.transformations.windowing import create_windows as declarative_create_windows
from egregora.transformations.windowing_legacy import create_windows as legacy_create_windows


@pytest.fixture
def sample_message_table():
    """Creates a sample Ibis table of messages for testing windowing."""
    start_time = datetime(2024, 1, 1, 10, 0, 0)
    data = [{"ts": start_time + timedelta(minutes=i), "text": f"Message {i}"} for i in range(200)]
    return ibis.memtable(data)


def run_and_collect_windows(create_windows_func, table, config):
    """Helper to run a windowing function and collect the results."""
    windows = []
    for window in create_windows_func(table, config=config):
        df = window.table.execute()
        windows.append(
            {
                "window_index": window.window_index,
                "start_time": window.start_time,
                "end_time": window.end_time,
                "size": window.size,
                "first_message_ts": df["ts"].min(),
                "last_message_ts": df["ts"].max(),
            }
        )
    return pd.DataFrame(windows)


def test_declarative_windowing_matches_legacy_by_count(sample_message_table):
    """Tests that declarative windowing by message count matches the legacy implementation."""
    config = WindowConfig(step_size=50, step_unit="messages", overlap_ratio=0.2)

    legacy_windows_df = run_and_collect_windows(legacy_create_windows, sample_message_table, config)
    declarative_windows_df = run_and_collect_windows(declarative_create_windows, sample_message_table, config)

    pd.testing.assert_frame_equal(legacy_windows_df, declarative_windows_df)


def test_declarative_windowing_matches_legacy_by_time(sample_message_table):
    """Tests that declarative windowing by time matches the legacy implementation."""
    config = WindowConfig(step_size=1, step_unit="hours", overlap_ratio=0.1)

    legacy_windows_df = run_and_collect_windows(legacy_create_windows, sample_message_table, config)
    declarative_windows_df = run_and_collect_windows(declarative_create_windows, sample_message_table, config)

    pd.testing.assert_frame_equal(legacy_windows_df, declarative_windows_df)
