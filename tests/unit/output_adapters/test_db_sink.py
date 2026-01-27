from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from egregora.data_primitives.document import DocumentMetadata, DocumentType
from egregora.output_sinks.db_sink import DbOutputSink
from egregora.output_sinks.exceptions import (
    DocumentIterationError,
    DocumentNotFoundError,
)


@pytest.fixture
def mock_repository() -> MagicMock:
    """Provides a mock ContentRepository."""
    return MagicMock()


def test_get_raises_not_found_error(mock_repository: MagicMock):
    """
    Given a DbOutputSink with a repository that returns None
    When get is called
    Then it should raise DocumentNotFoundError.
    """
    # Arrange
    mock_repository.get.return_value = None
    sink = DbOutputSink(repository=mock_repository)
    doc_type = DocumentType.POST
    identifier = "non-existent-id"

    # Act & Assert
    with pytest.raises(DocumentNotFoundError):
        sink.get(doc_type, identifier)


def test_documents_raises_iteration_error_on_missing_document():
    """Test that DbOutputSink.documents() raises DocumentIterationError."""
    # Arrange
    mock_repo = MagicMock()
    sink = DbOutputSink(repository=mock_repo)

    doc_type = DocumentType.POST
    identifier = "test-post-1"
    metadata = DocumentMetadata(
        identifier=identifier,
        doc_type=doc_type,
        metadata={"id": identifier, "type": "post"},
    )

    sink.list = MagicMock(return_value=[metadata])
    sink.get = MagicMock(side_effect=DocumentNotFoundError(doc_type.value, identifier))

    # Act & Assert
    with pytest.raises(DocumentIterationError) as exc_info:
        # Consume the iterator to trigger the exception
        list(sink.documents())

    assert exc_info.value.doc_type == doc_type.value
    assert exc_info.value.identifier == identifier
