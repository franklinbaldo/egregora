from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from ibis.common.exceptions import IbisError

from egregora.data_primitives.document import Document, DocumentType
from egregora.database.exceptions import (
    DatabaseOperationError,
    DocumentNotFoundError,
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


def test_get_raises_document_not_found_error(content_repository, mock_db_manager):
    """Verify get() raises DocumentNotFoundError when no document is found."""
    # Mock the Ibis table and execute to return an empty DataFrame
    mock_table = MagicMock()
    mock_table.filter.return_value.limit.return_value.execute.return_value.empty = True
    # The chain is filter(type).filter(id).limit(1).execute()
    # So we need to mock the chain properly
    mock_table.filter.return_value.filter.return_value.limit.return_value.execute.return_value.empty = True

    mock_db_manager.read_table.return_value = mock_table

    with pytest.raises(DocumentNotFoundError):
        content_repository.get(DocumentType.POST, "non-existent-id")


def test_get_raises_database_operation_error_on_ibis_error(content_repository, mock_db_manager):
    """Verify get() raises DatabaseOperationError when Ibis raises an error."""
    # Mock the Ibis connection to raise an IbisError
    mock_db_manager.read_table.side_effect = IbisError("Connection failed")

    with pytest.raises(DatabaseOperationError):
        content_repository.get(DocumentType.POST, "any-id")


def test_save_inserts_into_documents_table(content_repository, mock_db_manager):
    """Verify save() inserts into the documents table."""
    doc = Document(
        content="Test Content",
        type=DocumentType.POST,
        metadata={"title": "Test Title", "slug": "test-slug", "status": "draft"},
    )

    content_repository.save(doc)

    # Check that insert was called on the connection
    mock_db_manager.ibis_conn.insert.assert_called_once()
    args, _ = mock_db_manager.ibis_conn.insert.call_args
    assert args[0] == "documents"
    assert args[1][0]["doc_type"] == "post"
    assert args[1][0]["title"] == "Test Title"


def test_list_filters_by_doc_type(content_repository, mock_db_manager):
    """Verify list() filters by document type when provided."""
    mock_table = MagicMock()
    mock_db_manager.read_table.return_value = mock_table

    # Consume the iterator
    list(content_repository.list(doc_type=DocumentType.POST))

    # Verify filter was called
    # We can't easily check the exact expression passed to filter because it's an Ibis expression
    # But we can verify filter was called
    mock_table.filter.assert_called_once()


def test_list_returns_all_when_no_type(content_repository, mock_db_manager):
    """Verify list() does not filter when no type is provided."""
    mock_table = MagicMock()
    mock_db_manager.read_table.return_value = mock_table

    list(content_repository.list())

    # Verify filter was NOT called
    mock_table.filter.assert_not_called()
    mock_table.execute.assert_called_once()
