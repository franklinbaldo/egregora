from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from egregora.data_primitives.document import DocumentType
from egregora.output_adapters.db_sink import DbOutputSink
from egregora.output_adapters.exceptions import DocumentNotFoundError


@pytest.fixture
def mock_repository() -> MagicMock:
    """Provides a mock ContentRepository."""
    return MagicMock()


def test_read_document_raises_not_found_error(mock_repository: MagicMock):
    """
    Given a DbOutputSink with a repository that returns None
    When read_document is called
    Then it should raise DocumentNotFoundError.
    """
    # Arrange
    mock_repository.get.return_value = None
    sink = DbOutputSink(repository=mock_repository)
    doc_type = DocumentType.POST
    identifier = "non-existent-id"

    # Act & Assert
    with pytest.raises(DocumentNotFoundError):
        sink.read_document(doc_type, identifier)
