from unittest.mock import MagicMock

from egregora.agents.writer_helpers import load_profiles_context
from egregora.data_primitives.document import DocumentType
from egregora.output_sinks.exceptions import DocumentNotFoundError


def test_load_profiles_context_handles_document_not_found_error():
    """
    Given an output sink that raises DocumentNotFoundError
    When load_profiles_context is called
    Then it should handle the error and continue.
    """
    # Arrange
    output_sink = MagicMock()
    output_sink.get.side_effect = DocumentNotFoundError("profile", "test-author")
    active_authors = ["test-author"]

    # Act
    result = load_profiles_context(active_authors, output_sink)

    # Assert
    output_sink.get.assert_called_once_with(DocumentType.PROFILE, "test-author")
    assert "test-author" in result
    assert "(No profile yet - first appearance)" in result
