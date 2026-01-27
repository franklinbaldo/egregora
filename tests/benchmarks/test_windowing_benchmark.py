
from datetime import datetime, timedelta

import ibis
import pandas as pd  # noqa: TID251
import pytest

from egregora.transformations.windowing import _window_by_bytes


@pytest.fixture
def message_table():
    # Create a reasonably large dataset
    # 5,000 messages for CI speed
    n = 5_000
    base_time = datetime(2023, 1, 1)

    # Approx 100 bytes per message
    data = {
        "ts": [base_time + timedelta(seconds=i) for i in range(n)],
        "text": ["a" * 100 for _ in range(n)],
        "id": range(n)
    }
    df = pd.DataFrame(data)
    return ibis.memtable(df)

def test_window_by_bytes_benchmark(benchmark, message_table):
    def run_windowing():
        # 10KB windows -> ~100 messages per window
        windows = list(_window_by_bytes(message_table, max_bytes=10_000, overlap_bytes=0))
        # Force execution of one query per window to simulate actual usage
        # We check the size to trigger the query
        for w in windows:
            _ = w.table.count().execute()

    benchmark(run_windowing)
