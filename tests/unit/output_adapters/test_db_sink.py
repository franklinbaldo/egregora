from unittest.mock import MagicMock
import pytest

from egregora.data_primitives.document import DocumentType
from egregora.output_adapters.db_sink import DbOutputSink
from egregora.output_adapters.exceptions import DocumentNotFoundError


def test_read_document_raises_not_found_error():
    """
    Given a DbOutputSink with a repository that returns None
    When read_document is called
    Then it should raise a DocumentNotFoundError.
    """
    # Arrange
    mock_repo = MagicMock()
    mock_repo.get.return_value = None
    sink = DbOutputSink(repository=mock_repo)

    doc_type = DocumentType.POST
    identifier = "test-id"

    # Act & Assert
    with pytest.raises(DocumentNotFoundError) as excinfo:
        sink.read_document(doc_type, identifier)

    assert excinfo.value.doc_type == doc_type.value
    assert excinfo.value.identifier == identifier
