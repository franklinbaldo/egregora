from unittest.mock import MagicMock

from egregora.agents.formatting import (  # type: ignore[import-not-found]
    build_conversation_xml,
    load_journal_memory,
)
from egregora.data_primitives.document import DocumentType  # type: ignore[import-not-found]
from egregora.output_sinks.exceptions import DocumentNotFoundError  # type: ignore[import-not-found]


def test_load_journal_memory_handles_document_not_found_error() -> None:
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
    output_sink.get.side_effect = DocumentNotFoundError("journal", "test-journal")

    # Act
    result = load_journal_memory(output_sink)

    # Assert
    output_sink.list.assert_called_once_with(DocumentType.JOURNAL)
    output_sink.get.assert_called_once_with(DocumentType.JOURNAL, "test-journal")
    assert result == ""


def test_build_conversation_xml_empty_input() -> None:
    """
    Given empty input data
    When build_conversation_xml is called
    Then it should return an empty chat tag.
    """
    result = build_conversation_xml([], None)
    assert result == "<chat></chat>"


def test_build_conversation_xml_basic_message() -> None:
    """
    Given a single message
    When build_conversation_xml is called
    Then it should return correct XML structure.
    """
    data = [
        {
            "msg_id": "msg1",
            "author": "Alice",
            "timestamp": "2023-01-01 10:00:00",
            "text": "Hello world",
        }
    ]
    result = build_conversation_xml(data, None)

    expected_snippet = '<m id="msg1" author="Alice" ts="2023-01-01 10:00:00">Hello world</m>'
    assert expected_snippet in result
    assert result.startswith("<chat>")
    assert result.endswith("</chat>")


def test_build_conversation_xml_with_annotations() -> None:
    """
    Given a message with annotations
    When build_conversation_xml is called
    Then it should include note tags.
    """
    data = [
        {
            "msg_id": "msg1",
            "author": "Bob",
            "timestamp": "2023-01-01 10:05:00",
            "text": "Foo bar",
        }
    ]

    mock_store = MagicMock()
    mock_annotation = MagicMock()
    mock_annotation.id = "anno1"
    mock_annotation.commentary = "This is a note"

    # Mock return for msg1
    mock_store.list_annotations_for_message.return_value = [mock_annotation]

    result = build_conversation_xml(data, mock_store)

    assert '<m id="msg1" author="Bob" ts="2023-01-01 10:05:00">Foo bar' in result
    assert '<note id="anno1">This is a note</note>' in result


def test_build_conversation_xml_escaping() -> None:
    """
    Given content with special XML characters
    When build_conversation_xml is called
    Then it should escape them.
    """
    data = [
        {
            "msg_id": "msg1",
            "author": "Eve",
            "timestamp": "2023-01-01 12:00:00",
            "text": "I say <script>alert(1)</script> & things",
        }
    ]
    result = build_conversation_xml(data, None)

    # Jinja autoescape should handle this
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result
    assert "&amp; things" in result
    assert "<script>" not in result


def test_build_conversation_xml_handles_ibis_table_like_object() -> None:
    """
    Given an object that looks like an Ibis/Arrow table
    When build_conversation_xml is called
    Then it should process it correctly.
    """

    # Mocking a simple table structure
    class MockTable:
        def __init__(self) -> None:
            self.column_names = ["msg_id", "author", "text", "ts"]
            self.num_rows = 1

        def column(self, idx: int) -> MagicMock:
            mock_col = MagicMock()
            if idx == 0:
                val = ["msg100"]
            elif idx == 1:
                val = ["Dave"]
            elif idx == 2:
                val = ["Testing table"]
            elif idx == 3:
                val = ["2023-01-02"]
            else:
                val = []

            mock_col.to_pylist.return_value = val
            return mock_col

    table = MockTable()
    result = build_conversation_xml(table, None)

    assert '<m id="msg100" author="Dave" ts="2023-01-02">Testing table</m>' in result
