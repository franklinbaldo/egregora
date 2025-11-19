"""Unit tests for writer formatting helpers."""

from __future__ import annotations

import pyarrow as pa
import pytest

from egregora.agents.writer.formatting import _table_to_records


def test_table_to_records_accepts_pyarrow_table():
    """PyArrow tables are converted to column-ordered records."""
    table = pa.table({"msg_id": ["1", "2"], "message": ["hello", "world"]})

    records, columns = _table_to_records(table)

    assert columns == ["msg_id", "message"]
    assert records == [
        {"msg_id": "1", "message": "hello"},
        {"msg_id": "2", "message": "world"},
    ]


def test_table_to_records_accepts_mapping_iterables():
    """Iterables of mapping rows are converted without pandas."""
    rows = [
        {"msg_id": "1", "message": "hello"},
        {"msg_id": "2", "message": "world", "author": "uuid-123"},
    ]

    records, columns = _table_to_records(rows)

    assert columns == ["msg_id", "message", "author"]
    assert records == rows


def test_table_to_records_rejects_non_mapping_iterables():
    """Iterables that are not mapping-based raise helpful errors."""
    with pytest.raises(TypeError, match="Iterable inputs must yield mapping objects"):
        _table_to_records([1, 2, 3])


def test_table_to_records_rejects_single_mapping():
    """A single mapping input is not treated as tabular data."""
    with pytest.raises(TypeError, match="Expected an iterable of mappings"):
        _table_to_records({"msg_id": "1", "message": "orphan"})
