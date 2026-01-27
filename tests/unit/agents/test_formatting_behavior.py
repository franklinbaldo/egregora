import math
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.formatting import (
    _compute_message_id,
    _stringify_value,
    _table_to_records,
    build_conversation_xml,
    load_journal_memory,
)
from egregora.agents.shared.annotations import Annotation, AnnotationStore
from egregora.data_primitives.document import Document, DocumentMetadata, DocumentType
from egregora.output_sinks.base import OutputSink
from egregora.output_sinks.exceptions import DocumentNotFoundError


class TestLoadJournalMemory:
    @pytest.fixture
    def mock_sink(self):
        return MagicMock(spec=OutputSink)

    def test_load_journal_memory_returns_latest_content(self, mock_sink):
        # Arrange
        # Setup list return values (metadata only)
        # Using identifiers that sort chronologically/lexicographically
        docs = [
            DocumentMetadata(identifier="journal-2023-01-01", doc_type=DocumentType.JOURNAL, metadata={}),
            DocumentMetadata(identifier="journal-2023-01-02", doc_type=DocumentType.JOURNAL, metadata={}),
            DocumentMetadata(identifier="journal-2022-12-31", doc_type=DocumentType.JOURNAL, metadata={}),
        ]
        mock_sink.list.return_value = iter(docs)

        # Setup get return value for the latest one
        latest_doc = Document(content="Latest Content", type=DocumentType.JOURNAL)
        mock_sink.get.return_value = latest_doc

        # Act
        content = load_journal_memory(mock_sink)

        # Assert
        assert content == "Latest Content"
        mock_sink.list.assert_called_once_with(DocumentType.JOURNAL)
        mock_sink.get.assert_called_once_with(DocumentType.JOURNAL, "journal-2023-01-02")

    def test_load_journal_memory_returns_empty_when_no_journals(self, mock_sink):
        # Arrange
        mock_sink.list.return_value = iter([])

        # Act
        content = load_journal_memory(mock_sink)

        # Assert
        assert content == ""
        mock_sink.get.assert_not_called()

    def test_load_journal_memory_returns_empty_on_not_found(self, mock_sink):
        # Arrange
        docs = [
            DocumentMetadata(identifier="journal-1", doc_type=DocumentType.JOURNAL, metadata={}),
        ]
        mock_sink.list.return_value = iter(docs)
        mock_sink.get.side_effect = DocumentNotFoundError(DocumentType.JOURNAL, "journal-1")

        # Act
        content = load_journal_memory(mock_sink)

        # Assert
        assert content == ""


class TestStringifyValue:
    def test_stringify_value_basics(self):
        assert _stringify_value("hello") == "hello"
        assert _stringify_value(123) == "123"
        assert _stringify_value(None) == ""
        assert _stringify_value(math.nan) == ""

    def test_stringify_value_pyarrow_scalar(self):
        # Mocking a pyarrow-like scalar object
        mock_scalar = MagicMock()
        mock_scalar.is_valid = True
        mock_scalar.as_py.return_value = "converted"
        assert _stringify_value(mock_scalar) == "converted"

    def test_stringify_value_pyarrow_scalar_invalid(self):
        mock_scalar = MagicMock()
        mock_scalar.is_valid = False
        assert _stringify_value(mock_scalar) == ""

    def test_stringify_value_recursive(self):
        # Test recursion handling if needed, though simple recursion for as_py result
        mock_scalar = MagicMock()
        mock_scalar.is_valid = True
        mock_scalar.as_py.return_value = 123
        assert _stringify_value(mock_scalar) == "123"


class TestComputeMessageId:
    def test_compute_message_id_uses_message_id_if_present(self):
        row = {"message_id": "explicit-id", "other": "value"}
        assert _compute_message_id(row) == "explicit-id"

    def test_compute_message_id_uses_specific_fields_hash(self):
        # Should use timestamp, author, text
        row1 = {"timestamp": "2023", "author": "me", "text": "hello"}
        row2 = {"timestamp": "2023", "author": "me", "text": "hello"}
        row3 = {"timestamp": "2023", "author": "me", "text": "different"}

        id1 = _compute_message_id(row1)
        id2 = _compute_message_id(row2)
        id3 = _compute_message_id(row3)

        assert id1 == id2
        assert id1 != id3

    def test_compute_message_id_fallback_to_full_content(self):
        # No standard fields
        row1 = {"custom1": "A", "custom2": "B"}
        row2 = {"custom1": "A", "custom2": "B"}
        row3 = {"custom1": "A", "custom2": "C"}

        id1 = _compute_message_id(row1)
        id2 = _compute_message_id(row2)
        id3 = _compute_message_id(row3)

        assert id1 == id2
        assert id1 != id3

    def test_compute_message_id_raises_type_error(self):
        with pytest.raises(TypeError):
            _compute_message_id("not-a-mapping")


class TestTableToRecords:
    def test_table_to_records_list_of_dicts(self):
        data = [{"a": 1}, {"a": 2}]
        records, cols = _table_to_records(data)
        assert records == data
        assert cols == ["a"]

    def test_table_to_records_arrow_like(self):
        # Mocking an Arrow/Ibis Table object
        mock_table = MagicMock()
        mock_table.column_names = ["col1", "col2"]
        mock_table.num_rows = 2

        # Mock columns
        col1 = MagicMock()
        col1.to_pylist.return_value = [1, 3]
        col2 = MagicMock()
        col2.to_pylist.return_value = [2, 4]

        mock_table.column.side_effect = [col1, col2]

        records, cols = _table_to_records(mock_table)

        expected = [{"col1": 1, "col2": 2}, {"col1": 3, "col2": 4}]
        assert records == expected
        assert cols == ["col1", "col2"]

    def test_table_to_records_invalid_input(self):
        with pytest.raises(TypeError, match="Unsupported data source"):
            _table_to_records(123)

        with pytest.raises(TypeError, match="Expected an iterable"):
            _table_to_records({"a": 1})

        with pytest.raises(TypeError, match="Iterable inputs must yield mapping objects"):
            _table_to_records(["not-a-dict"])


class TestBuildConversationXML:
    @pytest.fixture
    def mock_store(self):
        return MagicMock(spec=AnnotationStore)

    def test_build_conversation_xml_empty(self):
        result = build_conversation_xml([], None)
        assert result == "<chat></chat>"

    def test_build_conversation_xml_basic(self):
        data = [
            {"author": "Alice", "text": "Hello", "timestamp": "2023-01-01"},
            {"author": "Bob", "text": "Hi", "timestamp": "2023-01-02"},
        ]

        with patch("egregora.agents.formatting.Environment") as MockEnv:
            mock_tmpl = MagicMock()
            MockEnv.return_value.get_template.return_value = mock_tmpl
            mock_tmpl.render.return_value = "<mocked_xml/>"

            result = build_conversation_xml(data, None)

            assert result == "<mocked_xml/>"

            # Verify data passed to render
            args, kwargs = mock_tmpl.render.call_args
            messages = kwargs["messages"]
            assert len(messages) == 2
            assert messages[0]["author"] == "Alice"
            assert messages[0]["content"] == "Hello"
            assert messages[0]["notes"] == []

    def test_build_conversation_xml_with_annotations(self, mock_store):
        data = [{"msg_id": "msg-1", "author": "Alice", "text": "Hello"}]

        # Mock annotations
        ann = Annotation(
            id="ann-1",
            parent_id="msg-1",
            parent_type="message",
            author="egregora",
            commentary="Note 1",
            created_at=datetime.now(UTC)
        )

        mock_store.list_annotations_for_message.return_value = [ann]

        with patch("egregora.agents.formatting.Environment") as MockEnv:
            mock_tmpl = MagicMock()
            MockEnv.return_value.get_template.return_value = mock_tmpl
            mock_tmpl.render.return_value = "<xml/>"

            build_conversation_xml(data, mock_store)

            args, kwargs = mock_tmpl.render.call_args
            messages = kwargs["messages"]
            assert len(messages) == 1
            assert len(messages[0]["notes"]) == 1
            # Note: Depending on fix, this might be ann.id or ann.document_id if fixed via adapter
            assert messages[0]["notes"][0]["id"] == "ann-1"
            assert messages[0]["notes"][0]["content"] == "Note 1"
