from unittest.mock import MagicMock

from egregora.data_primitives.document import DocumentType
from egregora.output_adapters.db_sink import DbOutputSink


def test_read_document_returns_none_for_missing_document():
    """
    Given a DbOutputSink with a repository that returns None
    When read_document is called
    Then it should return None (backward-compatible with callers expecting optional documents).
    """
    # Arrange
    mock_repo = MagicMock()
    mock_repo.get.return_value = None
    sink = DbOutputSink(repository=mock_repo)

    doc_type = DocumentType.POST
    identifier = "test-id"

    # Act
    result = sink.read_document(doc_type, identifier)

    # Assert
    assert result is None
