"""Tests for canonical batching utilities."""

import ibis
import pytest

from egregora.utils.batching import batch_table, batch_table_to_records


def test_batch_table_basic():
    """Test basic batching with explicit ordering."""
    # Create test table
    data = {"id": list(range(10)), "value": [f"val{i}" for i in range(10)]}
    table = ibis.memtable(data)

    # Batch into groups of 3
    batches = list(batch_table(table, batch_size=3, order_by=["id"]))

    # Should have 4 batches (3 + 3 + 3 + 1)
    assert len(batches) == 4  # noqa: PLR2004

    # Verify batch sizes
    batch_sizes = [len(batch.execute()) for batch in batches]
    assert batch_sizes == [3, 3, 3, 1]  # noqa: PLR2004

    # Verify all IDs present exactly once
    all_ids = []
    for batch in batches:
        result = batch.execute()
        all_ids.extend(result["id"].tolist())

    assert sorted(all_ids) == list(range(10))


def test_batch_table_exact_multiple():
    """Test batching when total rows is exact multiple of batch_size."""
    data = {"id": list(range(9)), "value": [f"val{i}" for i in range(9)]}
    table = ibis.memtable(data)

    batches = list(batch_table(table, batch_size=3, order_by=["id"]))

    # Should have exactly 3 batches
    assert len(batches) == 3  # noqa: PLR2004

    # All batches should be same size
    batch_sizes = [len(batch.execute()) for batch in batches]
    assert batch_sizes == [3, 3, 3]  # noqa: PLR2004


def test_batch_table_empty():
    """Test batching empty table."""
    data = {"id": [], "value": []}
    table = ibis.memtable(data)

    batches = list(batch_table(table, batch_size=10, order_by=["id"]))

    # Should have no batches
    assert len(batches) == 0


def test_batch_table_single_row():
    """Test batching table with single row."""
    data = {"id": [1], "value": ["single"]}
    table = ibis.memtable(data)

    batches = list(batch_table(table, batch_size=10, order_by=["id"]))

    assert len(batches) == 1

    result = batches[0].execute()
    assert len(result) == 1
    assert result["value"][0] == "single"


def test_batch_table_inferred_ordering():
    """Test that ordering is inferred from common timestamp columns."""
    data = {
        "timestamp": [i for i in range(5)],
        "value": [f"val{i}" for i in range(5)],
    }
    table = ibis.memtable(data)

    # Don't provide order_by - should infer from "timestamp"
    batches = list(batch_table(table, batch_size=2))

    assert len(batches) == 3  # noqa: PLR2004

    # Verify ordering is deterministic
    all_timestamps = []
    for batch in batches:
        result = batch.execute()
        all_timestamps.extend(result["timestamp"].tolist())

    assert all_timestamps == list(range(5))


def test_batch_table_invalid_batch_size():
    """Test that invalid batch_size raises error."""
    data = {"id": [1, 2, 3], "value": ["a", "b", "c"]}
    table = ibis.memtable(data)

    with pytest.raises(ValueError, match="batch_size must be positive"):
        list(batch_table(table, batch_size=0, order_by=["id"]))

    with pytest.raises(ValueError, match="batch_size must be positive"):
        list(batch_table(table, batch_size=-1, order_by=["id"]))


def test_batch_table_no_ordering():
    """Test that error raised when ordering cannot be inferred."""
    # Table with no standard ordering columns
    data = {"foo": [1, 2, 3], "bar": ["a", "b", "c"]}
    table = ibis.memtable(data)

    # Should succeed because we fall back to alphabetical column ordering
    batches = list(batch_table(table, batch_size=2))
    assert len(batches) == 2  # noqa: PLR2004


def test_batch_table_to_records():
    """Test batch_table_to_records convenience function."""
    data = {"id": list(range(7)), "value": [f"val{i}" for i in range(7)]}
    table = ibis.memtable(data)

    # Get batches as records
    record_batches = list(batch_table_to_records(table, batch_size=3, order_by=["id"]))

    # Should have 3 batches
    assert len(record_batches) == 3  # noqa: PLR2004

    # Verify each batch is a list of dicts
    assert len(record_batches[0]) == 3  # noqa: PLR2004
    assert len(record_batches[1]) == 3  # noqa: PLR2004
    assert len(record_batches[2]) == 1

    # Verify structure
    first_record = record_batches[0][0]
    assert isinstance(first_record, dict)
    assert "id" in first_record
    assert "value" in first_record


def test_batch_coverage_property():
    """Property test: All rows appear exactly once across all batches."""
    # Test with various sizes
    for n_rows in [0, 1, 5, 10, 99, 100, 101]:
        for batch_size in [1, 3, 10, 50]:
            data = {"id": list(range(n_rows)), "value": [f"val{i}" for i in range(n_rows)]}
            table = ibis.memtable(data)

            # Collect all IDs from all batches
            all_ids = []
            for batch in batch_table(table, batch_size=batch_size, order_by=["id"]):
                result = batch.execute()
                all_ids.extend(result["id"].tolist())

            # Verify complete coverage
            assert sorted(all_ids) == list(range(n_rows)), (
                f"Failed for n_rows={n_rows}, batch_size={batch_size}"
            )


def test_batch_ordering_stability():
    """Test that batching preserves ordering across runs."""
    data = {"id": [5, 2, 8, 1, 9, 3], "value": ["e", "b", "h", "a", "i", "c"]}
    table = ibis.memtable(data)

    # Run batching twice
    run1_ids = []
    run2_ids = []

    for batch in batch_table(table, batch_size=2, order_by=["id"]):
        result = batch.execute()
        run1_ids.extend(result["id"].tolist())

    for batch in batch_table(table, batch_size=2, order_by=["id"]):
        result = batch.execute()
        run2_ids.extend(result["id"].tolist())

    # Should be identical and sorted
    assert run1_ids == run2_ids
    assert run1_ids == [1, 2, 3, 5, 8, 9]


def test_batch_with_multiple_order_columns():
    """Test batching with composite ordering."""
    data = {
        "category": ["a", "a", "b", "b", "c"],
        "timestamp": [1, 2, 1, 2, 1],
        "value": ["a1", "a2", "b1", "b2", "c1"],
    }
    table = ibis.memtable(data)

    batches = list(batch_table(table, batch_size=2, order_by=["category", "timestamp"]))

    # Collect all values in order
    all_values = []
    for batch in batches:
        result = batch.execute()
        all_values.extend(result["value"].tolist())

    # Should be ordered by category then timestamp
    assert all_values == ["a1", "a2", "b1", "b2", "c1"]
