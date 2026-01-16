import ibis
import pandas as pd
import pytest
from ibis import _
import datetime

from egregora.transformations.enrichment import combine_with_enrichment_rows

def test_combine_with_enrichment_rows_basic():
    """Test basic combination of existing table and new rows."""
    # Given
    schema = ibis.schema({"id": "int64", "value": "string", "ts": "timestamp"})

    initial_data = pd.DataFrame({
        "id": [1],
        "value": ["old"],
        "ts": [pd.Timestamp("2023-01-01 10:00:00", tz="UTC")]
    })
    table = ibis.memtable(initial_data, schema=schema)

    new_rows = [
        {"id": 2, "value": "new", "ts": datetime.datetime(2023, 1, 1, 11, 0, 0, tzinfo=datetime.timezone.utc)}
    ]

    # When
    result_table = combine_with_enrichment_rows(table, new_rows, schema)
    result_df = result_table.execute()

    # Then
    assert len(result_df) == 2
    assert result_df.iloc[0]["id"] == 1
    assert result_df.iloc[1]["id"] == 2
    assert str(result_df.iloc[1]["value"]) == "new"

def test_combine_with_enrichment_rows_missing_columns():
    """Test that missing columns in base table are filled with nulls."""
    # Given
    # Schema has 'extra', but input table does not
    schema = ibis.schema({"id": "int64", "extra": "string", "ts": "timestamp"})

    initial_data = pd.DataFrame({
        "id": [1],
        "ts": [pd.Timestamp("2023-01-01 10:00:00", tz="UTC")]
    })
    # Create table without 'extra' column
    table = ibis.memtable(initial_data)

    new_rows = [
        {"id": 2, "extra": "filled", "ts": datetime.datetime(2023, 1, 1, 11, 0, 0, tzinfo=datetime.timezone.utc)}
    ]

    # When
    result_table = combine_with_enrichment_rows(table, new_rows, schema)
    result_df = result_table.execute()

    # Then
    assert "extra" in result_df.columns
    # ibis/pandas null handling can be tricky, check first row is None/NaN
    assert pd.isna(result_df.iloc[0]["extra"])
    assert result_df.iloc[1]["extra"] == "filled"

def test_combine_with_enrichment_rows_utc_normalization_ts():
    """Test that 'ts' column is cast to UTC."""
    # Given
    schema = ibis.schema({"id": "int64", "ts": "timestamp('UTC')"})

    # Input with naive timestamp (implied local or ambiguous)
    initial_data = pd.DataFrame({
        "id": [1],
        "ts": [pd.Timestamp("2023-01-01 10:00:00")] # Naive
    })
    table = ibis.memtable(initial_data)

    new_rows = []

    # When
    result_table = combine_with_enrichment_rows(table, new_rows, schema)
    result_df = result_table.execute()

    # Then
    # Check timezone. Pandas series .dt.tz should be UTC
    assert str(result_df["ts"].dtype).startswith("datetime64[ns, UTC]") or str(result_df["ts"].dt.tz) == "UTC"

def test_combine_with_enrichment_rows_utc_normalization_timestamp():
    """Test that 'timestamp' column is cast to UTC."""
    # Given
    schema = ibis.schema({"id": "int64", "timestamp": "timestamp('UTC')"})

    initial_data = pd.DataFrame({
        "id": [1],
        "timestamp": [pd.Timestamp("2023-01-01 10:00:00")]
    })
    table = ibis.memtable(initial_data)

    new_rows = []

    # When
    result_table = combine_with_enrichment_rows(table, new_rows, schema)
    result_df = result_table.execute()

    # Then
    assert str(result_df["timestamp"].dt.tz) == "UTC"

def test_combine_with_enrichment_rows_empty_new_rows():
    """Test behavior when new_rows is empty."""
    # Given
    schema = ibis.schema({"id": "int64", "ts": "timestamp"})
    initial_data = pd.DataFrame({
        "id": [1],
        "ts": [pd.Timestamp("2023-01-01 10:00:00", tz="UTC")]
    })
    table = ibis.memtable(initial_data, schema=schema)

    # When
    result_table = combine_with_enrichment_rows(table, [], schema)
    result_df = result_table.execute()

    # Then
    assert len(result_df) == 1
    assert result_df.iloc[0]["id"] == 1

def test_combine_with_enrichment_rows_ordering():
    """Test that results are ordered by timestamp."""
    # Given
    schema = ibis.schema({"id": "int64", "ts": "timestamp"})

    initial_data = pd.DataFrame({
        "id": [2],
        "ts": [pd.Timestamp("2023-01-01 12:00:00", tz="UTC")]
    })
    table = ibis.memtable(initial_data, schema=schema)

    # Insert earlier row
    new_rows = [
        {"id": 1, "ts": datetime.datetime(2023, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)}
    ]

    # When
    result_table = combine_with_enrichment_rows(table, new_rows, schema)
    result_df = result_table.execute()

    # Then
    assert result_df.iloc[0]["id"] == 1
    assert result_df.iloc[1]["id"] == 2
