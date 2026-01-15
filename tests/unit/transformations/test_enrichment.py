"""Unit tests for enrichment transformations."""
from __future__ import annotations

from datetime import datetime

import ibis
import pytest
from ibis import _

from egregora.transformations.enrichment import combine_with_enrichment_rows

# Define a consistent schema for testing
TEST_SCHEMA = ibis.schema(
    {
        "msg_id": "string",
        "ts": "timestamp('UTC')",
        "text": "string",
        "enrichment_data": "string",
    }
)


@pytest.fixture
def base_messages() -> list[dict]:
    """Sample messages data."""
    return [
        {"msg_id": "1", "ts": datetime(2024, 1, 1, 12, 0, 0), "text": "Hello"},
        {"msg_id": "2", "ts": datetime(2024, 1, 1, 13, 0, 0), "text": "World"},
    ]


def test_combine_with_empty_new_rows(base_messages: list[dict]):
    """Test that the function correctly handles an empty list of new rows."""
    messages_table = ibis.memtable(base_messages)

    result = combine_with_enrichment_rows(messages_table, [], TEST_SCHEMA)

    assert list(result.columns) == list(TEST_SCHEMA.names)
    assert result.count().execute() == 2

    # Check that the new column is added with null values
    assert "enrichment_data" in result.columns
    enrichment_values = result.enrichment_data.execute().tolist()
    assert all(v is None for v in enrichment_values)


def test_combine_with_new_enrichment_rows(base_messages: list[dict]):
    """Test the successful combination of base messages with new enrichment rows."""
    messages_table = ibis.memtable(base_messages)
    new_rows = [
        {
            "msg_id": "3",
            "ts": datetime(2024, 1, 1, 14, 0, 0),
            "text": "New",
            "enrichment_data": "enriched",
        }
    ]

    result = combine_with_enrichment_rows(messages_table, new_rows, TEST_SCHEMA)

    assert result.count().execute() == 3
    assert list(result.columns) == list(TEST_SCHEMA.names)

    # Verify the table is sorted by timestamp
    timestamps = result.ts.execute().tolist()
    assert timestamps == sorted(timestamps)

    # Check the content of the new row
    new_row_data = result.filter(_.msg_id == "3").execute().to_dict("records")[0]
    assert new_row_data["enrichment_data"] == "enriched"


def test_schema_enforcement_drops_extra_columns(base_messages: list[dict]):
    """Test that columns not in the schema are dropped."""
    # Add an extra column to the base table
    messages_with_extra = [dict(row, extra_col="should be dropped") for row in base_messages]
    messages_table = ibis.memtable(messages_with_extra)

    result = combine_with_enrichment_rows(messages_table, [], TEST_SCHEMA)

    assert "extra_col" not in result.columns
    assert list(result.columns) == list(TEST_SCHEMA.names)
