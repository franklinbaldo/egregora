from __future__ import annotations

import unittest.mock
from unittest.mock import MagicMock

import pytest
from ibis.common.exceptions import IbisError

from egregora.data_primitives.document import DocumentType
from egregora.database.exceptions import (
    DatabaseOperationError,
    DocumentNotFoundError,
    UnsupportedDocumentTypeError,
)
from egregora.database.repository import ContentRepository


@pytest.fixture
def mock_db_manager():
    """Fixture for a mocked DuckDBStorageManager."""
    return MagicMock()


@pytest.fixture
def content_repository(mock_db_manager):
    """Fixture for a ContentRepository with a mocked DB manager."""
    return ContentRepository(db=mock_db_manager)


def test_get_raises_unsupported_document_type_error(content_repository):
    """Verify get() raises UnsupportedDocumentTypeError for an invalid doc type."""
    unsupported_type = unittest.mock.create_autospec(DocumentType)
    unsupported_type.value = "UNSUPPORTED"
    with pytest.raises(UnsupportedDocumentTypeError):
        content_repository.get(unsupported_type, "some-id")


def test_get_raises_document_not_found_error(content_repository, mock_db_manager):
    """Verify get() raises DocumentNotFoundError when no document is found."""
    # Mock the Ibis table and execute to return an empty DataFrame
    mock_table = MagicMock()
    mock_table.filter.return_value.limit.return_value.execute.return_value.empty = True
    mock_db_manager.read_table.return_value = mock_table

    with pytest.raises(DocumentNotFoundError):
        content_repository.get(DocumentType.POST, "non-existent-id")


def test_get_raises_database_operation_error_on_ibis_error(content_repository, mock_db_manager):
    """Verify get() raises DatabaseOperationError when Ibis raises an error."""
    # Mock the Ibis connection to raise an IbisError
    mock_db_manager.read_table.side_effect = IbisError("Connection failed")

    with pytest.raises(DatabaseOperationError):
        content_repository.get(DocumentType.POST, "any-id")


def test_list_raises_unsupported_document_type_error(content_repository):
    """Verify list() raises UnsupportedDocumentTypeError for an invalid doc type."""
    with pytest.raises(UnsupportedDocumentTypeError):
        # list() returns an iterator, so we need to consume it to trigger the exception.
        list(content_repository.list(doc_type="UNSUPPORTED"))


def test_list_with_doc_type_returns_correct_data(content_repository, mock_db_manager):
    """Verify list() with a doc_type returns the expected data."""
    # Mock the Ibis table and the data it returns
    mock_table = MagicMock()
    mock_arrow_table = MagicMock()
    expected_data = [{"id": "1", "title": "Test Post"}]
    mock_arrow_table.to_pylist.return_value = expected_data
    mock_table.execute.return_value.fetch_arrow_table.return_value = mock_arrow_table
    mock_db_manager.read_table.return_value = mock_table

    # Call the list method
    result = list(content_repository.list(doc_type=DocumentType.POST))

    # Verify the correct table was read and the data is correct
    mock_db_manager.read_table.assert_called_once_with("posts")
    assert result == expected_data


def test_list_handles_ibis_error_and_falls_back(content_repository, mock_db_manager):
    """Verify list() falls back to manual query on IbisError."""
    # Simulate IbisError on reading the view
    mock_db_manager.read_table.side_effect = IbisError("View not found")

    # Mock the fallback execute call
    mock_relation = MagicMock()
    mock_relation.description = [("id",), ("type",), ("content",), ("created_at",), ("title",), ("slug",), ("subject_uuid",)]
    mock_rows = [
        ("1", "post", "content1", "2023-01-01", "title1", "slug1", None),
        ("2", "profile", "content2", "2023-01-02", "title2", None, "uuid2"),
    ]
    mock_relation.fetchall.return_value = mock_rows
    mock_db_manager.execute.return_value = mock_relation

    # Call the list method (without doc_type to trigger the view logic)
    result = list(content_repository.list())

    # Verify the fallback was used
    mock_db_manager.execute.assert_called_once_with("SELECT * FROM documents_view")
    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[1]["type"] == "profile"
