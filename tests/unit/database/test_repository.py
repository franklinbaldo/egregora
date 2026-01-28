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


def test_get_raises_document_not_found_error(content_repository, mock_db_manager):
    """Verify get() raises DocumentNotFoundError when no document is found."""
    # Mock the Ibis table and execute to return an empty DataFrame
    mock_table = MagicMock()
    # Chain: filter().limit().execute().empty = True
    # The new get() calls filter twice (for Posts slug lookup), or once.
    # We need to ensure both checks fail if it's a POST.

    mock_res = MagicMock()
    mock_res.empty = True

    # Setup mock to return empty result
    mock_table.filter.return_value.execute.return_value = mock_res
    mock_table.filter.return_value.limit.return_value.execute.return_value = mock_res

    mock_db_manager.read_table.return_value = mock_table

    with pytest.raises(DocumentNotFoundError):
        content_repository.get(DocumentType.POST, "non-existent-id")


def test_get_raises_database_operation_error_on_ibis_error(content_repository, mock_db_manager):
    """Verify get() raises DatabaseOperationError when Ibis raises an error."""
    # Mock the Ibis connection to raise an IbisError
    mock_db_manager.read_table.side_effect = IbisError("Connection failed")

    with pytest.raises(DatabaseOperationError):
        content_repository.get(DocumentType.POST, "any-id")


def test_list_raises_database_operation_error_for_invalid_type(content_repository, mock_db_manager):
    """Verify list() raises DatabaseOperationError if doc_type is not a valid enum."""
    # The new code assumes doc_type has .value
    with pytest.raises(DatabaseOperationError):
        list(content_repository.list(doc_type="UNSUPPORTED"))  # type: ignore[arg-type]


# Removed: test_list_handles_ibis_error_and_falls_back
# The fallback logic was for the 'documents_view' which is gone.


def test_save_calls_replace_rows(content_repository, mock_db_manager):
    """Verify save() calls replace_rows with correct arguments."""
    doc = Document(
        content="Test Content",
        type=DocumentType.POST,
        metadata={"title": "Test Title", "slug": "test-slug", "status": "draft"},
    )

    content_repository.save(doc)

    # Check that replace_rows was called
    mock_db_manager.replace_rows.assert_called_once()
    args, kwargs = mock_db_manager.replace_rows.call_args

    assert args[0] == "documents"
    row = args[1][0]
    assert row["doc_type"] == "post"
    assert row["title"] == "Test Title"
    assert kwargs.get("by_keys") == {"id": row["id"]}
