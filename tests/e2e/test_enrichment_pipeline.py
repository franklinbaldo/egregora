"""E2E test for the enrichment pipeline.

This test verifies that:
1. The enrichment pipeline can be run with a mock client.
2. The `combine_with_enrichment_rows` function is correctly called and a
   new column is added to the messages table.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import ibis
from ibis import schema

from egregora.transformations.enrichment import combine_with_enrichment_rows

if TYPE_CHECKING:
    from pathlib import Path


def test_enrichment_pipeline_with_mock_client(tmp_path: Path):
    """Test the enrichment pipeline with a mock client."""
    # 1. Setup a mock site with a messages table
    db_path = tmp_path / "test.db"
    conn = ibis.connect(f"duckdb:///{db_path}")
    messages = [
        {"id": 1, "ts": "2024-01-01T12:00:00Z", "message": "Hello"},
        {"id": 2, "ts": "2024-01-01T12:01:00Z", "message": "World"},
    ]
    messages_table = ibis.memtable(messages)
    conn.create_table("messages", messages_table)

    # 2. Simulate the enrichment process.
    enriched_rows = [
        {"id": 1, "enriched_content": "This is a mock enrichment."},
        {"id": 2, "enriched_content": "This is another mock enrichment."},
    ]

    # 3. Combine the original messages with the enriched data
    sch = schema(
        {
            "id": "int64",
            "ts": "timestamp('UTC')",
            "message": "string",
            "enriched_content": "string",
        }
    )
    result = combine_with_enrichment_rows(conn.table("messages"), enriched_rows, sch)

    # 4. Verify the results
    assert result.count().execute() == 4
    assert "enriched_content" in result.columns

    enriched_data = result.filter(result.enriched_content.notnull()).execute()
    assert len(enriched_data) == 2
    assert enriched_data["enriched_content"].tolist() == [
        "This is a mock enrichment.",
        "This is another mock enrichment.",
    ]


def test_enrichment_pipeline_with_no_new_rows(tmp_path: Path):
    """Test the enrichment pipeline when there are no new rows to add."""
    # 1. Setup a mock site with a messages table
    db_path = tmp_path / "test.db"
    conn = ibis.connect(f"duckdb:///{db_path}")
    messages = [
        {"id": 1, "ts": "2024-01-01T12:00:00Z", "message": "Hello"},
        {"id": 2, "ts": "2024-01-01T12:01:00Z", "message": "World"},
    ]
    messages_table = ibis.memtable(messages)
    conn.create_table("messages", messages_table)

    # 2. Simulate the enrichment process with no new rows.
    enriched_rows = []

    # 3. Combine the original messages with the enriched data
    sch = schema(
        {
            "id": "int64",
            "ts": "timestamp('UTC')",
            "message": "string",
            "enriched_content": "string",
        }
    )
    result = combine_with_enrichment_rows(conn.table("messages"), enriched_rows, sch)

    # 4. Verify the results
    assert result.count().execute() == 2
    assert "enriched_content" in result.columns
    enriched_data = result.filter(result.enriched_content.notnull()).execute()
    assert len(enriched_data) == 0


def test_enrichment_pipeline_with_timestamp_column(tmp_path: Path):
    """Test the enrichment pipeline with a 'timestamp' column."""
    # 1. Setup a mock site with a messages table
    db_path = tmp_path / "test.db"
    conn = ibis.connect(f"duckdb:///{db_path}")
    messages = [
        {"id": 1, "timestamp": "2024-01-01T12:00:00Z", "message": "Hello"},
        {"id": 2, "timestamp": "2024-01-01T12:01:00Z", "message": "World"},
    ]
    messages_table = ibis.memtable(messages)
    conn.create_table("messages", messages_table)

    # 2. Simulate the enrichment process.
    enriched_rows = []

    # 3. Combine the original messages with the enriched data
    sch = schema(
        {
            "id": "int64",
            "timestamp": "timestamp('UTC', 9)",
            "message": "string",
        }
    )
    result = combine_with_enrichment_rows(conn.table("messages"), enriched_rows, sch)

    # 4. Verify the results
    assert result.count().execute() == 2
    assert "timestamp" in result.columns
