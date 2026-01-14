"""Unit tests for enrichment transformations."""

from __future__ import annotations

from datetime import datetime

import ibis
import pytest

from egregora.transformations.enrichment import combine_with_enrichment_rows


@pytest.fixture
def sample_messages_rows() -> list[dict[str, str]]:
    """Return a sample list of message rows."""
    return [
        {"id": "1", "ts": "2024-01-01T12:00:00", "text": "Hello"},
        {"id": "2", "ts": "2024-01-01T13:00:00", "text": "World"},
    ]


@pytest.fixture
def sample_messages_table(sample_messages_rows: list[dict[str, str]]) -> ibis.Table:
    """Return a sample Ibis table of messages."""
    return ibis.memtable(sample_messages_rows)


class TestCombineWithEnrichmentRows:
    """Tests for the combine_with_enrichment_rows function."""

    def test_combine_with_no_new_rows(self, sample_messages_table: ibis.Table):
        """Should return the original table cast to the new schema when new_rows is empty."""
        schema = ibis.schema({"id": "string", "ts": "timestamp('UTC')"})
        result_table = combine_with_enrichment_rows(sample_messages_table, [], schema)

        assert result_table.count().execute() == 2
        assert result_table.schema() == schema

    def test_combine_with_new_rows(self, sample_messages_table: ibis.Table):
        """Should correctly union the base table with new enrichment rows."""
        new_rows = [
            {"id": "3", "ts": datetime(2024, 1, 1, 14, 0, 0), "text": "New"},
            {"id": "4", "ts": datetime(2024, 1, 1, 11, 0, 0), "text": "Row"},
        ]
        schema = ibis.schema({"id": "string", "ts": "timestamp('UTC')", "text": "string"})

        result_table = combine_with_enrichment_rows(sample_messages_table, new_rows, schema)

        assert result_table.count().execute() == 4
        ids = result_table.id.execute().tolist()
        assert "3" in ids
        assert "4" in ids

    def test_sorting_by_timestamp(self, sample_messages_table: ibis.Table):
        """Should sort the combined table by the timestamp column."""
        new_rows = [{"id": "3", "ts": datetime(2024, 1, 1, 11, 0, 0)}]  # Earlier time
        schema = ibis.schema({"id": "string", "ts": "timestamp('UTC')"})

        result_table = combine_with_enrichment_rows(sample_messages_table, new_rows, schema)

        sorted_ids = result_table.order_by("ts").id.execute().tolist()
        assert sorted_ids == ["3", "1", "2"]

    def test_handles_timestamp_column_name(self):
        """Should handle schemas with 'timestamp' instead of 'ts'."""
        rows = [{"id": "1", "timestamp": "2024-01-01T12:00:00"}]
        table = ibis.memtable(rows)
        new_rows = [{"id": "2", "timestamp": datetime(2024, 1, 1, 11, 0, 0)}]
        schema = ibis.schema({"id": "string", "timestamp": "timestamp('UTC', 9)"})

        result_table = combine_with_enrichment_rows(table, new_rows, schema)
        assert result_table.count().execute() == 2
        sorted_ids = result_table.order_by("timestamp").id.execute().tolist()
        assert sorted_ids == ["2", "1"]

    def test_ignores_extra_columns_in_new_rows(self, sample_messages_table: ibis.Table):
        """Should ignore columns in new_rows that are not in the schema."""
        new_rows = [{"id": "3", "ts": datetime(2024, 1, 1, 14, 0, 0), "extra": "data"}]
        schema = ibis.schema({"id": "string", "ts": "timestamp('UTC')"})
        result_table = combine_with_enrichment_rows(sample_messages_table, new_rows, schema)
        assert "extra" not in result_table.columns
        assert result_table.count().execute() == 3

    def test_handles_empty_initial_table(self):
        """Should work correctly when the initial messages table is empty."""
        empty_schema = ibis.schema({"id": "string", "ts": "timestamp('UTC')", "text": "string"})
        empty_table = ibis.memtable([], schema=empty_schema)
        new_rows = [{"id": "1", "ts": datetime(2024, 1, 1, 12, 0, 0), "text": "First"}]
        schema = ibis.schema({"id": "string", "ts": "timestamp('UTC')", "text": "string"})

        result_table = combine_with_enrichment_rows(empty_table, new_rows, schema)
        assert result_table.count().execute() == 1
        assert result_table.id.execute().iloc[0] == "1"
