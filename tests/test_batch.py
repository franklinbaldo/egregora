"""Tests for batch processing utilities in enrichment module."""

import ibis

from egregora.augmentation.enrichment.batch import _iter_table_record_batches


def test_iter_table_record_batches_exact_coverage():
    """Test that batching covers all rows exactly once without omission or duplication.

    Regression test for off-by-one bug where first batch would get batch_size-1 rows
    due to 1-based row_number() being treated as 0-based.
    """
    # Create table with 1001 rows to test batch boundary edge cases
    # This ensures we have:
    # - First batch: rows 0-999 (1000 rows)
    # - Second batch: rows 1000 (1 row)
    num_rows = 1001
    batch_size = 1000

    data = [{"id": i, "value": f"row_{i}"} for i in range(num_rows)]
    table = ibis.memtable(data)

    # Collect all batches
    all_rows = []
    batch_sizes = []
    for batch in _iter_table_record_batches(table, batch_size=batch_size):
        batch_sizes.append(len(batch))
        all_rows.extend(batch)

    # Verify we got exactly the right number of rows
    assert len(all_rows) == num_rows, f"Expected {num_rows} rows, got {len(all_rows)}"

    # Verify batch sizes are correct
    assert batch_sizes == [1000, 1], f"Expected [1000, 1] batch sizes, got {batch_sizes}"

    # Verify all IDs are present and unique (no omissions or duplicates)
    ids = [row["id"] for row in all_rows]
    assert sorted(ids) == list(range(num_rows)), "Not all rows were retrieved or duplicates found"

    # Verify row order is preserved (stable ordering)
    assert ids == list(range(num_rows)), "Row order was not preserved"


def test_iter_table_record_batches_single_batch():
    """Test batching when all rows fit in a single batch."""
    data = [{"id": i} for i in range(100)]
    table = ibis.memtable(data)

    batches = list(_iter_table_record_batches(table, batch_size=1000))

    assert len(batches) == 1, "Should have exactly one batch"
    assert len(batches[0]) == 100, "Batch should contain all 100 rows"  # noqa: PLR2004


def test_iter_table_record_batches_exact_multiple():
    """Test batching when row count is exact multiple of batch size."""
    data = [{"id": i} for i in range(2000)]
    table = ibis.memtable(data)

    batches = list(_iter_table_record_batches(table, batch_size=1000))

    assert len(batches) == 2, "Should have exactly two batches"  # noqa: PLR2004
    assert all(len(batch) == 1000 for batch in batches), "All batches should have 1000 rows"  # noqa: PLR2004

    # Verify all IDs are present
    all_ids = [row["id"] for batch in batches for row in batch]
    assert sorted(all_ids) == list(range(2000)), "Not all rows retrieved"


def test_iter_table_record_batches_empty_table():
    """Test batching with empty table."""
    # Create empty table with schema
    table = ibis.memtable([], schema=ibis.schema({"id": "int64"}))

    batches = list(_iter_table_record_batches(table, batch_size=1000))

    assert len(batches) == 0, "Empty table should produce no batches"


def test_iter_table_record_batches_small_batch_size():
    """Test batching with small batch size."""
    data = [{"id": i, "value": i * 2} for i in range(10)]
    table = ibis.memtable(data)

    batches = list(_iter_table_record_batches(table, batch_size=3))

    # 10 rows with batch_size=3 should give [3, 3, 3, 1]
    assert len(batches) == 4, "Should have 4 batches"  # noqa: PLR2004
    assert [len(b) for b in batches] == [3, 3, 3, 1], "Batch sizes incorrect"

    # Verify all data is present
    all_rows = [row for batch in batches for row in batch]
    assert len(all_rows) == 10, "Should have all 10 rows"  # noqa: PLR2004
    assert all_rows[0]["value"] == 0, "First row value incorrect"
    assert all_rows[-1]["value"] == 18, "Last row value incorrect"  # noqa: PLR2004
