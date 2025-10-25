from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from egregora.schema import ensure_message_schema

# A much simpler schema for testing, focusing only on the timestamp and text
# columns that matter for the schema normalisation logic.
SIMPLE_SCHEMA = {
    "timestamp": pl.Datetime(time_unit="ns", time_zone="UTC"),
    "author": pl.String,
    "message": pl.String,
}

# An empty frame with the desired final schema.
EMPTY_FRAME = pl.DataFrame(schema=SIMPLE_SCHEMA)


def test_ensure_message_schema_with_datetime_objects():
    """
    Test that ensure_message_schema correctly handles a DataFrame
    where the timestamp column is of type object, containing Python
    datetime objects.
    """
    # Create a DataFrame with Python datetime objects
    data = {
        "timestamp": [datetime(2025, 1, 1, 12, 0, 0)],
        "author": ["test"],
        "message": ["hello"],
    }
    df = pl.DataFrame(data)

    # Apply the schema function
    result = ensure_message_schema(df)

    # Check the timestamp column's dtype
    assert isinstance(result["timestamp"].dtype, pl.Datetime)
    assert result["timestamp"].dtype.time_zone == "UTC"


def test_ensure_message_schema_with_tz_aware_datetime():
    """
    Test that ensure_message_schema correctly handles a DataFrame
    with a timezone-aware timestamp column, converting it to UTC
    and nanosecond precision.
    """
    # Create a DataFrame with a timezone-aware timestamp column
    data = {
        "timestamp": [datetime(2025, 1, 1, 12, 0, 0)],
        "author": ["test"],
        "message": ["hello"],
    }
    df = pl.DataFrame(data).with_columns(
        pl.col("timestamp").dt.replace_time_zone("Europe/Amsterdam")
    )

    # Cast to microseconds to test the time unit conversion
    df = df.with_columns(
        pl.col("timestamp").cast(pl.Datetime(time_unit="us", time_zone="Europe/Amsterdam"))
    )

    # Apply the schema function
    result = ensure_message_schema(df)

    # Check the timestamp column's dtype and value
    assert result["timestamp"].dtype == pl.Datetime(time_unit="ns", time_zone="UTC")
    # 11:00 UTC is 12:00 in Amsterdam in January
    assert result["timestamp"][0] == datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)
