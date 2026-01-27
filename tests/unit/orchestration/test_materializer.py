from unittest.mock import MagicMock

from egregora.data_primitives.document import DocumentType
from egregora.orchestration.materializer import materialize_site
from egregora.output_sinks.exceptions import DocumentNotFoundError


def test_materialize_site_handles_document_not_found_error():
    """
    Given a source sink that raises DocumentNotFoundError
    When materialize_site is called
    Then it should handle the error and continue.
    """
    # Arrange
    source_sink = MagicMock()
    destination_sink = MagicMock()

    meta = MagicMock()
    meta.doc_type = DocumentType.POST
    meta.identifier = "test-post"

    source_sink.list.return_value = [meta]
    source_sink.get.side_effect = DocumentNotFoundError("post", "test-post")

    # Act
    materialize_site(source_sink, destination_sink)

    # Assert
    assert source_sink.list.call_count == 5
    assert source_sink.get.call_count == 5
    destination_sink.persist.assert_not_called()
