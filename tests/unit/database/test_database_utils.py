"""Unit tests for database utility functions."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from src.egregora.database.utils import frame_to_records, iter_table_batches


class TestFrameToRecords:
    """Tests for the frame_to_records function."""

    def test_with_to_dict_method(self):
        """Test with a mock object that has a to_dict method (like pandas)."""
        mock_frame = Mock()
        mock_frame.to_dict.return_value = [{"a": 1}, {"a": 2}]
        result = frame_to_records(mock_frame)
        assert result == [{"a": 1}, {"a": 2}]
        mock_frame.to_dict.assert_called_once_with("records")

    def test_with_to_pylist_method(self):
        """Test with a mock object that has a to_pylist method."""
        mock_frame = Mock()
        # Mock away `to_dict` to ensure `to_pylist` is called
        del mock_frame.to_dict
        mock_frame.to_pylist.return_value = [{"a": 1}, {"a": 2}]
        result = frame_to_records(mock_frame)
        assert result == [{"a": 1}, {"a": 2}]
        mock_frame.to_pylist.assert_called_once()

    def test_with_simple_iterable(self):
        """Test with a simple iterable of objects."""
        class Row:
            def __init__(self, data):
                self._data = data
            def __iter__(self):
                return iter(self._data.items())

        frame = [Row({"a": 1}), Row({"a": 2})]
        result = frame_to_records(frame)
        assert result == [{"a": 1}, {"a": 2}]

    def test_with_empty_frame(self):
        """Test with an empty frame."""
        mock_frame = Mock()
        mock_frame.to_dict.return_value = []
        result = frame_to_records(mock_frame)
        assert result == []


class TestIterTableBatches:
    """Tests for the iter_table_batches function."""

    @pytest.mark.parametrize(
        "num_records, batch_size, expected_batches",
        [
            (10, 3, [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]),
            (9, 3, [[0, 1, 2], [3, 4, 5], [6, 7, 8]]),
            (2, 5, [[0, 1]]),
            (0, 5, []),
        ],
    )
    def test_batching_logic(self, num_records, batch_size, expected_batches):
        """Test the batching logic with different record counts and batch sizes."""
        records = [{"id": i} for i in range(num_records)]

        # Mock Ibis table and its execution result
        mock_table = MagicMock()
        mock_table.execute.return_value = records
        # Prevent trying to find a backend
        mock_table._find_backend.side_effect = AttributeError

        batches = list(iter_table_batches(mock_table, batch_size=batch_size))

        expected_result = [[{"id": i} for i in batch] for batch in expected_batches]

        assert batches == expected_result
        mock_table.execute.assert_called_once()

    def test_empty_table(self):
        """Test with an empty table."""
        mock_table = MagicMock()
        mock_table.execute.return_value = []
        mock_table._find_backend.side_effect = AttributeError

        batches = list(iter_table_batches(mock_table))
        assert batches == []
