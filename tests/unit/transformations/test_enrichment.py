"""Behavioral tests for enrichment transformations."""

from datetime import datetime

import ibis

from egregora.transformations.enrichment import combine_with_enrichment_rows


def test_combine_basic_functionality():
    """Verify basic union of existing table and new rows."""
    # Given
    schema = ibis.schema({"id": "int64", "val": "string", "ts": "timestamp"})

    data = [
        {"id": 1, "val": "a", "ts": datetime(2023, 1, 1, 10, 0, 0)},
    ]
    table = ibis.memtable(data, schema=schema)

    new_rows = [{"id": 2, "val": "b", "ts": datetime(2023, 1, 1, 11, 0, 0)}]

    # When
    result = combine_with_enrichment_rows(table, new_rows, schema)

    # Then
    res = result.to_pyarrow().to_pylist()
    assert len(res) == 2
    # Sort order is not guaranteed by default unless function sorts it.
    # The function sorts by "ts".
    assert res[0]["id"] == 1
    assert res[1]["id"] == 2


def test_missing_columns_adaptation():
    """Verify that columns in schema but missing from input table are added as nulls."""
    # Given: Input table lacks 'extra' column present in schema
    input_schema = ibis.schema({"id": "int64", "ts": "timestamp"})
    target_schema = ibis.schema({"id": "int64", "ts": "timestamp", "extra": "string"})

    data = [{"id": 1, "ts": datetime(2023, 1, 1)}]
    table = ibis.memtable(data, schema=input_schema)

    new_rows = [{"id": 2, "ts": datetime(2023, 1, 2), "extra": "foo"}]

    # When
    result = combine_with_enrichment_rows(table, new_rows, target_schema)

    # Then
    res = result.to_pyarrow().to_pylist()
    assert "extra" in res[0]
<<<<<<< HEAD
    # First row (from table) should be None
=======
    # First row (from table) should be None/NaN
>>>>>>> origin/pr/2658
    assert res[0]["extra"] is None
    # Second row (from new_rows) should be "foo"
    assert res[1]["extra"] == "foo"


def test_timestamp_normalization_ts():
    """Verify timestamp normalization when column is named 'ts'."""
    # Given
    schema = ibis.schema({"id": "int64", "ts": "timestamp"})

    data = [{"id": 1, "ts": datetime(2023, 1, 1, 10, 0)}]
    table = ibis.memtable(data, schema=schema)

    new_rows = []

    # When
    result = combine_with_enrichment_rows(table, new_rows, schema)

    # Then
    # Execute to verify no errors in casting
<<<<<<< HEAD
    res = result.to_pyarrow().to_pylist()
=======
    res = result.to_pyarrow()
>>>>>>> origin/pr/2658
    assert len(res) == 1


def test_empty_new_rows():
    """Verify behavior when no new rows are provided."""
    # Given
    schema = ibis.schema({"id": "int64", "ts": "timestamp"})
    data = [{"id": 1, "ts": datetime(2023, 1, 1)}]
    table = ibis.memtable(data, schema=schema)

    # When
    result = combine_with_enrichment_rows(table, [], schema)

    # Then
    assert result.count().execute() == 1


def test_ordering():
    """Verify that the result is ordered by timestamp."""
    # Given
    schema = ibis.schema({"id": "int64", "ts": "timestamp"})

    # Later timestamp in existing table
    data = [{"id": 2, "ts": datetime(2023, 1, 2)}]
    table = ibis.memtable(data, schema=schema)

    # Earlier timestamp in new rows
    new_rows = [{"id": 1, "ts": datetime(2023, 1, 1)}]

    # When
    result = combine_with_enrichment_rows(table, new_rows, schema)

    # Then
    res = result.to_pyarrow().to_pylist()
    assert res[0]["id"] == 1  # Should be first due to earlier timestamp
    assert res[1]["id"] == 2


def test_supports_alternate_timestamp_column():
    """Verify support for 'timestamp' column name instead of 'ts'."""
    # Given: Schema using "timestamp" instead of "ts"
    schema = ibis.schema({"id": "int64", "timestamp": "timestamp"})
    data = [{"id": 1, "timestamp": datetime(2023, 1, 1)}]
    table = ibis.memtable(data, schema=schema)

    new_rows = [{"id": 2, "timestamp": datetime(2023, 1, 2)}]

    # When
    result = combine_with_enrichment_rows(table, new_rows, schema)

    # Then
    res = result.to_pyarrow().to_pylist()
    assert len(res) == 2
    assert res[1]["id"] == 2


def test_no_timestamp_column():
    """Verify behavior when neither 'ts' nor 'timestamp' column is present."""
    # Given
    schema = ibis.schema({"id": "int64", "val": "string"})
    data = [{"id": 1, "val": "a"}]
    table = ibis.memtable(data, schema=schema)

    # When
    result = combine_with_enrichment_rows(table, [], schema)

    # Then
    assert result.count().execute() == 1
