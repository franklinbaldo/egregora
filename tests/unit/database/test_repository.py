"""Unit tests for the ContentRepository."""

from unittest.mock import MagicMock

import pytest
from ibis.common.exceptions import IbisError

from egregora.data_primitives.document import DocumentType
from egregora.database.exceptions import (
    DocumentNotFoundError,
    RepositoryQueryError,
    UnsupportedDocumentTypeError,
)
from egregora.database.repository import ContentRepository


@pytest.fixture
def mock_db_manager():
    """Fixture for a mocked DuckDBStorageManager."""
    return MagicMock()


@pytest.fixture
def repository(mock_db_manager):
    """Fixture for a ContentRepository with a mocked DB manager."""
    return ContentRepository(mock_db_manager)


def test_get_table_for_type_unsupported(repository):
    """Test that _get_table_for_type raises for an unsupported type."""
    # Create a mock unsupported DocumentType
    unsupported_type = MagicMock(spec=DocumentType)
    unsupported_type.name = "UNSUPPORTED"
    with pytest.raises(UnsupportedDocumentTypeError):
        repository._get_table_for_type(unsupported_type)


def test_get_document_not_found(repository, mock_db_manager):
    """Test that get() raises DocumentNotFoundError when no document is found."""
    mock_table = MagicMock()
    mock_table.filter.return_value.limit.return_value.execute.return_value.empty = True
    mock_db_manager.read_table.return_value = mock_table

    with pytest.raises(DocumentNotFoundError):
        repository.get(DocumentType.POST, "non-existent-id")


def test_get_repository_query_error(repository, mock_db_manager):
    """Test that get() raises RepositoryQueryError on a database error."""
    mock_db_manager.read_table.side_effect = IbisError("DB connection failed")

    with pytest.raises(RepositoryQueryError):
        repository.get(DocumentType.POST, "any-id")


def test_list_unsupported_type_raises_error(repository):
    """Test that list() raises UnsupportedDocumentTypeError for an invalid type."""
    # Create a mock unsupported DocumentType
    unsupported_type = MagicMock(spec=DocumentType)
    unsupported_type.name = "UNSUPPORTED"
    with pytest.raises(UnsupportedDocumentTypeError):
        # The method returns an iterator, so we need to consume it to trigger the potential error.
        list(repository.list(unsupported_type))
