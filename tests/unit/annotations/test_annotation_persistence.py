from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from egregora.agents.shared.annotations import Annotation, AnnotationStore
from egregora.data_primitives.document import DocumentType


class TestAnnotationStorePersistence:

    @pytest.fixture
    def mock_output_sink(self):
        sink = MagicMock()
        sink.persist = MagicMock()
        return sink

    @pytest.fixture
    def mock_db(self):
        # Mocking the storage object which is passed to AnnotationStore
        storage = MagicMock()
        # Mocking ibis_conn and other required methods/attributes
        storage.ibis_conn = MagicMock()
        storage.ibis_conn.table.return_value = MagicMock() # For table creation checks if any
        storage.connection = MagicMock() # For context manager

        # Mock context manager return value for connection()
        conn_context = MagicMock()
        storage.connection.return_value.__enter__.return_value = conn_context

        # Mock next_sequence_value to return an integer
        storage.next_sequence_value.return_value = 1
        return storage

    def test_save_annotation_persists_document_when_sink_provided(
        self, mock_db, mock_output_sink
    ) -> None:
        store = AnnotationStore(storage=mock_db, output_sink=mock_output_sink)

        store.save_annotation(
            parent_id="msg-123",
            parent_type="message",
            commentary="Important observation.",
        )

        mock_output_sink.persist.assert_called_once()
        persisted_doc = mock_output_sink.persist.call_args[0][0]
        assert persisted_doc.type == DocumentType.ANNOTATION
        assert persisted_doc.metadata["categories"] == ["Annotations"]

    def test_save_annotation_works_without_sink(self, mock_db) -> None:
        store = AnnotationStore(storage=mock_db, output_sink=None)

        annotation = store.save_annotation(
            parent_id="msg-456",
            parent_type="message",
            commentary="Another observation.",
        )

        assert annotation is not None

    def test_persist_failure_does_not_fail_save(
        self, mock_db, mock_output_sink
    ) -> None:
        mock_output_sink.persist.side_effect = OSError("Disk full")
        store = AnnotationStore(storage=mock_db, output_sink=mock_output_sink)

        annotation = store.save_annotation(
            parent_id="msg-789",
            parent_type="message",
            commentary="Test observation.",
        )

        assert annotation is not None


class TestAnnotationDocumentConversion:

    def test_to_document_creates_annotation_type(self) -> None:
        annotation = Annotation(
            id=42,
            parent_id="msg-123",
            parent_type="message",
            author="egregora",
            commentary="Test commentary",
            created_at=datetime.now(UTC),
        )

        doc = annotation.to_document()

        assert doc.type == DocumentType.ANNOTATION
        assert doc.metadata["annotation_id"] == "42"
        assert doc.metadata["categories"] == ["Annotations"]
