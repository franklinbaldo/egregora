from unittest.mock import MagicMock

from egregora.agents.formatting import load_journal_memory
from egregora.data_primitives.document import DocumentType
from egregora.output_adapters.exceptions import DocumentNotFoundError


def test_load_journal_memory_handles_document_not_found_error():
    """
    Given an output sink that raises DocumentNotFoundError
    When load_journal_memory is called
    Then it should handle the error and return an empty string.
    """
    # Arrange
    output_sink = MagicMock()
    meta = MagicMock()
    meta.identifier = "test-journal"
    output_sink.list.return_value = [meta]
    output_sink.read_document.side_effect = DocumentNotFoundError(
        "journal", "test-journal"
    )

    # Act
    result = load_journal_memory(output_sink)

    # Assert
    output_sink.list.assert_called_once_with(DocumentType.JOURNAL)
    output_sink.read_document.assert_called_once_with(
        DocumentType.JOURNAL, "test-journal"
    )
    assert result == ""
