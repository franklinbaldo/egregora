"""Tests for egregora.transformations.enrichment."""

from __future__ import annotations

from datetime import UTC, datetime

import ibis
import pandas as pd
import pytest
from ibis import schema


@pytest.fixture
def base_messages_table() -> ibis.Table:
    """Fixture for a base table of messages."""
    return ibis.memtable(
        [
            {"id": 1, "ts": datetime(2023, 1, 1, 12, 0, 0), "text": "message 1"},
            {"id": 2, "ts": datetime(2023, 1, 1, 12, 5, 0), "text": "message 2"},
        ],
        schema=schema({"id": "int", "ts": "timestamp", "text": "string"}),
    )


@pytest.fixture
def enrichment_rows() -> list[dict]:
    """Fixture for a list of enrichment rows."""
    return [
        {"id": 3, "ts": datetime(2023, 1, 1, 12, 2, 0), "text": "enriched message"},
        {"id": 4, "ts": datetime(2023, 1, 1, 12, 7, 0), "text": "another one"},
    ]


class TestCombineWithEnrichmentRows:
    """Tests for the combine_with_enrichment_rows function."""

    def test_combines_tables_and_sorts(self, base_messages_table, enrichment_rows):
        """Should combine the base table with new rows and sort by timestamp."""
        from egregora.transformations.enrichment import combine_with_enrichment_rows

        combined = combine_with_enrichment_rows(
            base_messages_table, enrichment_rows, base_messages_table.schema()
        )

        assert combined.count().execute() == 4

        result_df = combined.execute()
        result_data = result_df.to_dict("records")

        timestamps = [row["ts"] for row in result_data]
        assert timestamps == sorted(timestamps)

    def test_handles_empty_enrichment_rows(self, base_messages_table):
        """Should return the original table if enrichment rows are empty."""
        from egregora.transformations.enrichment import combine_with_enrichment_rows

        combined = combine_with_enrichment_rows(
            base_messages_table, [], base_messages_table.schema()
        )

        assert combined.count().execute() == 2

        # The function casts to UTC, so we expect the output to have UTC timestamps.
        expected_df = pd.DataFrame(
            [
                {
                    "id": 1,
                    "ts": datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
                    "text": "message 1",
                },
                {
                    "id": 2,
                    "ts": datetime(2023, 1, 1, 12, 5, 0, tzinfo=UTC),
                    "text": "message 2",
                },
            ]
        )
        # Ensure the 'ts' column is of the correct type for comparison
        expected_df["ts"] = pd.to_datetime(expected_df["ts"])

        pd.testing.assert_frame_equal(
            combined.execute().reset_index(drop=True),
            expected_df.reset_index(drop=True),
            check_dtype=False,
        )

    def test_casts_to_provided_schema(self, base_messages_table, enrichment_rows):
        """Should cast the final table to the provided schema."""
        from egregora.transformations.enrichment import combine_with_enrichment_rows

        target_schema = schema(
            {"id": "string", "ts": "timestamp('UTC')", "text": "string"}
        )

        combined = combine_with_enrichment_rows(
            base_messages_table, enrichment_rows, target_schema
        )

        assert combined.schema() == target_schema
        assert combined.count().execute() == 4

        result_data = combined.execute().to_dict("records")
        assert all(isinstance(row["id"], str) for row in result_data)

    def test_handles_different_column_names_for_timestamp(self):
        """Should work correctly if the timestamp column is named 'timestamp'."""
        from egregora.transformations.enrichment import combine_with_enrichment_rows

        base_table = ibis.memtable(
            [{"id": 1, "timestamp": datetime(2023, 1, 1, 10, 0, 0), "msg": "a"}],
            schema=schema({"id": "int", "timestamp": "timestamp", "msg": "string"}),
        )

        new_rows = [{"id": 2, "timestamp": datetime(2023, 1, 1, 9, 0, 0), "msg": "b"}]

        combined = combine_with_enrichment_rows(
            base_table, new_rows, base_table.schema()
        )

        assert combined.count().execute() == 2

        result_data = combined.execute().to_dict("records")
        timestamps = [row["timestamp"] for row in result_data]
        assert timestamps == sorted(timestamps)

    def test_handles_missing_columns_in_enrichment_rows(self, base_messages_table):
        """Should handle enrichment rows with missing columns by filling with null."""
        from egregora.transformations.enrichment import combine_with_enrichment_rows

        enrichment_rows_missing_text = [
            {"id": 3, "ts": datetime(2023, 1, 1, 12, 3, 0)},
        ]

        combined = combine_with_enrichment_rows(
            base_messages_table,
            enrichment_rows_missing_text,
            base_messages_table.schema(),
        )

        assert combined.count().execute() == 3

        result_df = combined.order_by(ibis.desc("id")).limit(1).execute()
        last_row = result_df.to_dict("records")[0]

        assert last_row["id"] == 3
        assert last_row["text"] is None
