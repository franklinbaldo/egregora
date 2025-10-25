from __future__ import annotations

from datetime import UTC, datetime

import ibis
import ibis.expr.datatypes as dt

from egregora.schema import ensure_message_schema

# A much simpler schema for testing, focusing only on the timestamp and text
# columns that matter for the schema normalisation logic.
SIMPLE_SCHEMA = {
    "timestamp": dt.Timestamp(timezone="UTC", scale=9),
    "author": dt.String(),
    "message": dt.String(),
}

# An empty frame with the desired final schema.
EMPTY_FRAME = ibis.memtable([], schema=ibis.schema(SIMPLE_SCHEMA))


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
    df = ibis.memtable(data)

    # Apply the schema function
    result = ensure_message_schema(df)

    # Check the timestamp column's dtype
    timestamp_dtype = result.schema()["timestamp"]
    assert isinstance(timestamp_dtype, dt.Timestamp)
    assert timestamp_dtype.timezone == "UTC"


def test_ensure_message_schema_with_tz_aware_datetime():
    """
    Test that ensure_message_schema correctly handles a DataFrame
    with a timezone-aware timestamp column, converting it to UTC
    and nanosecond precision.
    """
    from zoneinfo import ZoneInfo

    # Create a DataFrame with a timezone-aware timestamp (12:00 Amsterdam = 11:00 UTC)
    data = {
        "timestamp": [datetime(2025, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))],
        "author": ["test"],
        "message": ["hello"],
    }
    df = ibis.memtable(data)

    # Cast to microsecond precision timestamp with Amsterdam timezone
    df = df.mutate(
        timestamp=df.timestamp.cast(dt.Timestamp(timezone="Europe/Amsterdam", scale=6))
    )

    # Apply the schema function - should convert to UTC
    result = ensure_message_schema(df)

    # Check the timestamp column's dtype and value
    timestamp_dtype = result.schema()["timestamp"]
    assert timestamp_dtype == dt.Timestamp(timezone="UTC", scale=9)
    # 12:00 Amsterdam should become 11:00 UTC
    result_value = result.timestamp.execute().iloc[0]
    # Convert pandas Timestamp to datetime for comparison
    assert result_value.to_pydatetime().replace(microsecond=0) == datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)
