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


<<<<<<< HEAD
# Updated test: UnsupportedDocumentTypeError is likely not raised by get anymore
# if get expects a DocumentType enum.
# But if we pass something that is NOT a DocumentType, it might fail with AttributeError or similar.
# The new code does `t.filter(t.doc_type == doc_type.value)`.
# If `doc_type` has no `value` attribute, it raises AttributeError.
# If `doc_type` IS a DocumentType but not one of the expected ones?
# The repository supports all DocumentTypes generally now via 'documents' table.
# So UnsupportedDocumentTypeError might be obsolete for `get` unless we enforce it.
# Let's check repository.py code. It doesn't raise UnsupportedDocumentTypeError.
# So we should probably remove this test or update expectation.


=======
>>>>>>> origin/pr/2714
def test_get_raises_document_not_found_error(content_repository, mock_db_manager):
    """Verify get() raises DocumentNotFoundError when no document is found."""
    # Mock the Ibis table and execute to return an empty DataFrame
    mock_table = MagicMock()
<<<<<<< HEAD
    # Chain: filter().limit().execute().empty = True
    # The new get() calls filter twice (for Posts slug lookup), or once.
    # We need to ensure both checks fail if it's a POST.

    mock_res = MagicMock()
    mock_res.empty = True

    # Setup mock to return empty result
    mock_table.filter.return_value.execute.return_value = mock_res
    mock_table.filter.return_value.limit.return_value.execute.return_value = mock_res
=======
    mock_table.filter.return_value.limit.return_value.execute.return_value.empty = True
    # The chain is filter(type).filter(id).limit(1).execute()
    # So we need to mock the chain properly
    mock_table.filter.return_value.filter.return_value.limit.return_value.execute.return_value.empty = True
>>>>>>> origin/pr/2714

    mock_db_manager.read_table.return_value = mock_table

    with pytest.raises(DocumentNotFoundError):
        content_repository.get(DocumentType.POST, "non-existent-id")


def test_get_raises_database_operation_error_on_ibis_error(content_repository, mock_db_manager):
    """Verify get() raises DatabaseOperationError when Ibis raises an error."""
    # Mock the Ibis connection to raise an IbisError
    mock_db_manager.read_table.side_effect = IbisError("Connection failed")

    with pytest.raises(DatabaseOperationError):
        content_repository.get(DocumentType.POST, "any-id")


<<<<<<< HEAD
def test_list_raises_database_operation_error_for_invalid_type(content_repository, mock_db_manager):
    """Verify list() raises DatabaseOperationError if doc_type is not a valid enum."""
    # The new code assumes doc_type has .value
    with pytest.raises(DatabaseOperationError):
        list(content_repository.list(doc_type="UNSUPPORTED"))  # type: ignore[arg-type]


# Removed: test_list_handles_ibis_error_and_falls_back
# The fallback logic was for the 'documents_view' which is gone.
=======
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
>>>>>>> origin/pr/2714
