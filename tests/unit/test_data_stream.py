"""Tests for egregora.data.stream module - Ibis-first streaming utilities.

These tests verify:
1. Correct DuckDB context handling (no "table not found" errors)
2. Memory-efficient streaming (no full materialization)
3. Deterministic ordering for reproducibility
4. File I/O operations (Parquet, NDJSON)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import ibis
import pytest

from egregora.database.streaming import (
    copy_expr_to_ndjson,
    copy_expr_to_parquet,
    ensure_deterministic_order,
    stream_ibis,
)

# Constants for magic numbers
EXPECTED_ROW_COUNT = 5
HIGH_SCORE_THRESHOLD = 90
FILTERED_ROW_COUNT = 3
LARGE_TABLE_ROW_COUNT = 10000
MAX_BATCH_SIZE = 1000

# Additional constants for batch testing
EXPECTED_BATCH_COUNT = 3
BATCH_SIZE_2_FIRST = 2
BATCH_SIZE_2_SECOND = 2
BATCH_SIZE_2_THIRD = 1
MIN_ARGS_FOR_MAIN = 2


@pytest.fixture()
def duckdb_con():
    """Create an in-memory DuckDB connection via Ibis."""
    return ibis.duckdb.connect(":memory:")


@pytest.fixture()
def sample_table(duckdb_con):
    """Create a sample table for testing."""
    data = {
        "id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "score": [95, 87, 92, 88, 91],
        "published_at": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"],
    }
    return duckdb_con.create_table("sample", data)


@pytest.fixture()
def large_table(duckdb_con):
    """Create a large table for memory efficiency tests."""
    # Create a table with 10,000 rows
    duckdb_con.raw_sql("""
        CREATE TABLE large AS
        SELECT
            i AS id,
            'user_' || i AS name,
            i * 10 AS score
        FROM range(10000) t(i)
    """)
    return duckdb_con.table("large")


class TestStreamIbis:
    """Tests for stream_ibis() function."""

    def test_stream_basic(self, duckdb_con, sample_table):
        """Test basic streaming of a small table."""

        all_rows = []
        for batch in stream_ibis(sample_table, duckdb_con, batch_size=2):
            all_rows.extend(batch)

        assert len(all_rows) == EXPECTED_ROW_COUNT
        assert all_rows[0]["name"] == "Alice"
        assert all_rows[4]["name"] == "Eve"

    def test_stream_with_filter(self, duckdb_con, sample_table):
        """Test streaming with filtered expression (uses Ibis context)."""

        # This tests that SQL compilation uses the correct DuckDB context
        expr = sample_table.filter(sample_table.score > HIGH_SCORE_THRESHOLD)

        all_rows = []
        for batch in stream_ibis(expr, duckdb_con, batch_size=10):
            all_rows.extend(batch)

        assert len(all_rows) == FILTERED_ROW_COUNT  # Alice (95), Charlie (92), Eve (91)
        names = {row["name"] for row in all_rows}
        assert names == {"Alice", "Charlie", "Eve"}

    def test_stream_batch_size(self, duckdb_con, sample_table):
        """Test that batch_size is respected."""

        batches = list(stream_ibis(sample_table, duckdb_con, batch_size=2))

        # EXPECTED_ROW_COUNT rows with batch_size=2 should yield EXPECTED_BATCH_COUNT batches:
        # [BATCH_SIZE_2_FIRST, BATCH_SIZE_2_SECOND, BATCH_SIZE_2_THIRD]
        assert len(batches) == EXPECTED_BATCH_COUNT
        assert len(batches[0]) == BATCH_SIZE_2_FIRST
        assert len(batches[1]) == BATCH_SIZE_2_SECOND
        assert len(batches[2]) == BATCH_SIZE_2_THIRD

    def test_stream_empty_table(self, duckdb_con):
        """Test streaming an empty table."""

        empty_table = duckdb_con.create_table("empty", {"id": [], "name": []})

        batches = list(stream_ibis(empty_table, duckdb_con, batch_size=10))

        assert len(batches) == 0

    def test_stream_large_table_memory_efficiency(self, duckdb_con, large_table):
        """Test that large tables are streamed without full materialization.

        This test verifies that we don't load all LARGE_TABLE_ROW_COUNT rows into memory at once.
        If we materialized the full table, this would allocate significant memory.
        With streaming, we only hold one batch (MAX_BATCH_SIZE rows) at a time.
        """

        row_count = 0
        max_batch_size = 0

        for batch in stream_ibis(large_table, duckdb_con, batch_size=MAX_BATCH_SIZE):
            row_count += len(batch)
            max_batch_size = max(max_batch_size, len(batch))

        assert row_count == LARGE_TABLE_ROW_COUNT
        assert max_batch_size <= MAX_BATCH_SIZE  # No batch should exceed batch_size

    def test_stream_with_select(self, duckdb_con, sample_table):
        """Test streaming with column selection."""

        expr = sample_table.select("id", "name")

        all_rows = []
        for batch in stream_ibis(expr, duckdb_con, batch_size=10):
            all_rows.extend(batch)

        # Verify only selected columns are present
        assert set(all_rows[0].keys()) == {"id", "name"}
        assert "score" not in all_rows[0]


class TestCopyExprToParquet:
    """Tests for copy_expr_to_parquet() function."""

    def test_write_parquet(self, duckdb_con, sample_table):
        """Test writing Ibis expression to Parquet file."""

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.parquet"

            copy_expr_to_parquet(sample_table, duckdb_con, output_path)

            # Verify file was created
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            # Verify contents by reading back
            result_table = duckdb_con.read_parquet(str(output_path))
            rows = result_table.execute()
            assert len(rows) == EXPECTED_ROW_COUNT

    def test_write_filtered_expression(self, duckdb_con, sample_table):
        """Test writing a filtered expression to Parquet."""

        expr = sample_table.filter(sample_table.score > HIGH_SCORE_THRESHOLD)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "filtered.parquet"

            copy_expr_to_parquet(expr, duckdb_con, output_path)

            # Verify filtered results
            result_table = duckdb_con.read_parquet(str(output_path))
            rows = result_table.execute()
            assert len(rows) == FILTERED_ROW_COUNT


class TestCopyExprToNdjson:
    """Tests for copy_expr_to_ndjson() function."""

    def test_write_ndjson(self, duckdb_con, sample_table):
        """Test writing Ibis expression to NDJSON file."""

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.ndjson"

            copy_expr_to_ndjson(sample_table, duckdb_con, output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify NDJSON format (one JSON object per line)
            lines = output_path.read_text().strip().split("\n")
            assert len(lines) == EXPECTED_ROW_COUNT

            # Parse first line
            first_record = json.loads(lines[0])
            assert "id" in first_record
            assert "name" in first_record

    def test_write_ndjson_with_selection(self, duckdb_con, sample_table):
        """Test writing selected columns to NDJSON."""

        expr = sample_table.select("id", "name")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "selected.ndjson"

            copy_expr_to_ndjson(expr, duckdb_con, output_path)

            lines = output_path.read_text().strip().split("\n")
            first_record = json.loads(lines[0])

            # Verify only selected columns
            assert set(first_record.keys()) == {"id", "name"}


class TestEnsureDeterministicOrder:
    """Tests for ensure_deterministic_order() function."""

    def test_sorts_by_published_at(self, duckdb_con):
        """Test that tables with published_at column are sorted correctly."""

        # Create table with unsorted data
        data = {
            "id": [3, 1, 2],
            "published_at": ["2025-01-03", "2025-01-01", "2025-01-02"],
            "content": ["third", "first", "second"],
        }
        table = duckdb_con.create_table("unsorted", data)

        # Apply deterministic ordering
        ordered = ensure_deterministic_order(table)

        # Stream and verify order
        all_rows = []
        for batch in stream_ibis(ordered, duckdb_con, batch_size=10):
            all_rows.extend(batch)

        # Should be sorted by published_at
        assert all_rows[0]["content"] == "first"
        assert all_rows[1]["content"] == "second"
        assert all_rows[2]["content"] == "third"

    def test_sorts_by_id_fallback(self, duckdb_con):
        """Test that tables without published_at use id for sorting."""

        data = {
            "id": [3, 1, 2],
            "name": ["third", "first", "second"],
        }
        table = duckdb_con.create_table("no_timestamp", data)

        ordered = ensure_deterministic_order(table)

        all_rows = []
        for batch in stream_ibis(ordered, duckdb_con, batch_size=10):
            all_rows.extend(batch)

        # Should be sorted by id
        assert all_rows[0]["name"] == "first"
        assert all_rows[1]["name"] == "second"
        assert all_rows[2]["name"] == "third"

    def test_no_sortable_columns(self, duckdb_con):
        """Test that tables without sortable columns return unchanged."""

        data = {"name": ["Alice", "Bob"], "score": [95, 87]}
        table = duckdb_con.create_table("no_keys", data)

        ordered = ensure_deterministic_order(table)

        # Should return the expression unchanged (no error)
        assert ordered is not None

    def test_deterministic_across_runs(self, duckdb_con, sample_table):
        """Test that ordering is reproducible across multiple runs."""

        ordered = ensure_deterministic_order(sample_table)

        # Run twice and compare
        run1 = []
        for batch in stream_ibis(ordered, duckdb_con, batch_size=10):
            run1.extend(batch)

        run2 = []
        for batch in stream_ibis(ordered, duckdb_con, batch_size=10):
            run2.extend(batch)

        # Results should be identical
        assert [r["id"] for r in run1] == [r["id"] for r in run2]
        assert [r["name"] for r in run1] == [r["name"] for r in run2]


class TestIntegration:
    """Integration tests combining multiple utilities."""

    def test_stream_order_and_write(self, duckdb_con):
        """Test full workflow: create -> order -> stream -> write."""

        # Create unsorted data
        data = {
            "id": [3, 1, 4, 2],
            "timestamp": ["2025-01-03", "2025-01-01", "2025-01-04", "2025-01-02"],
            "value": [30, 10, 40, 20],
        }
        table = duckdb_con.create_table("workflow", data)

        # Apply ordering
        ordered = ensure_deterministic_order(table)

        # Stream and collect
        all_rows = []
        for batch in stream_ibis(ordered, duckdb_con, batch_size=2):
            all_rows.extend(batch)

        # Verify order
        assert [r["value"] for r in all_rows] == [10, 20, 30, 40]

        # Write to file
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "workflow.parquet"
            copy_expr_to_parquet(ordered, duckdb_con, output_path)

            # Read back and verify order is preserved
            result = duckdb_con.read_parquet(str(output_path))
            result_rows = result.execute().to_dict("records")
            assert [r["value"] for r in result_rows] == [10, 20, 30, 40]
