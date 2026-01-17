import uuid
from datetime import datetime, timedelta

import ibis
import pytest

from egregora.knowledge.profiles import get_active_authors


@pytest.fixture(scope="module")
def large_ibis_table():
    """Creates a large Ibis table for benchmarking."""
    # Create 100k rows with 100 unique authors
    num_rows = 100_000
    num_authors = 100

    authors = [str(uuid.uuid4()) for _ in range(num_authors)]
    # Add 'system' and 'egregora' to test filtering
    authors.extend(["system", "egregora"])

    # Repeat authors to fill rows
    author_col = (authors * (num_rows // len(authors) + 1))[:num_rows]

    # Simple data structure without pandas
    data = {
        "author_uuid": author_col,
        "message": ["test"] * num_rows,
        # Use simple timestamps if needed, or omit if unused by function under test
        "timestamp": [datetime(2023, 1, 1) + timedelta(minutes=i) for i in range(num_rows)],
    }

    # ibis.memtable uses DuckDB backend by default
    return ibis.memtable(data, name="messages")


def test_get_active_authors_benchmark_no_limit(benchmark, large_ibis_table):
    """Benchmark get_active_authors without limit."""
    result = benchmark(get_active_authors, large_ibis_table)
    assert len(result) == 100
    assert "system" not in result
    assert "egregora" not in result


def test_get_active_authors_benchmark_with_limit(benchmark, large_ibis_table):
    """Benchmark get_active_authors with limit."""
    # Limit 10
    result = benchmark(get_active_authors, large_ibis_table, limit=10)
    assert len(result) == 10
    assert "system" not in result
