from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from egregora.agents.shared.annotations import AnnotationStore
from egregora.data_primitives.document import DocumentType


class TestAnnotationStorePersistence:
    @pytest.fixture
    def mock_storage(self):
        storage = MagicMock()
        storage.ibis_conn = MagicMock()
        storage.next_sequence_value = MagicMock(return_value=1)

        # Mock connection context manager
        mock_conn = MagicMock()
        storage.connection = MagicMock()
        storage.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        storage.connection.return_value.__exit__ = MagicMock(return_value=False)

        # Mock methods used during initialization
        storage.ensure_sequence = MagicMock()
        storage.ensure_sequence_default = MagicMock()
        storage.sync_sequence_with_table = MagicMock()

        return storage

    def test_save_annotation_persists_document(self, mock_storage) -> None:
        mock_output_sink = MagicMock()

        # Patch the database schema functions used during initialization
        with (
            patch("egregora.agents.shared.annotations.database_schema.create_table_if_not_exists"),
            patch("egregora.agents.shared.annotations.database_schema.add_primary_key"),
        ):
            store = AnnotationStore(storage=mock_storage, output_sink=mock_output_sink)

        annotation = store.save_annotation(
            parent_id="msg-123",
            parent_type="message",
            commentary="Important observation.",
        )

        # Verify annotation was created with correct values
        assert isinstance(annotation.id, str)
        assert annotation.parent_id == "msg-123"
        assert annotation.parent_type == "message"
        assert annotation.commentary == "Important observation."
        assert annotation.author == "egregora"

        # Verify insert was called on backend
        mock_storage.ibis_conn.insert.assert_called_once()
        insert_call_args = mock_storage.ibis_conn.insert.call_args
        assert insert_call_args[0][0] == "annotations"

        # Verify document was persisted to output sink
        mock_output_sink.persist.assert_called_once()
        saved_doc = mock_output_sink.persist.call_args[0][0]
        assert saved_doc.type == DocumentType.ANNOTATION
        assert "Important observation." in saved_doc.content
        assert saved_doc.metadata["parent_id"] == "msg-123"
        assert saved_doc.metadata["author"] == "egregora"
        assert saved_doc.metadata["categories"] == ["Annotations"]

    def test_list_annotations_for_message(self, mock_storage) -> None:
        # Mock connection and cursor for SQL execution
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("id",),
            ("parent_id",),
            ("parent_type",),
            ("author",),
            ("commentary",),
            ("created_at",),
        ]
        mock_cursor.fetchall.return_value = [
            (1, "msg-1", "message", "egregora", "test annotation", datetime.now(UTC))
        ]

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        # Patch the database schema functions used during initialization
        with (
            patch("egregora.agents.shared.annotations.database_schema.create_table_if_not_exists"),
            patch("egregora.agents.shared.annotations.database_schema.add_primary_key"),
        ):
            store = AnnotationStore(storage=mock_storage)

        annotations = store.list_annotations_for_message("msg-1")

        assert len(annotations) == 1
        assert annotations[0].id == "1"
        assert annotations[0].parent_id == "msg-1"
        assert annotations[0].parent_type == "message"
        assert annotations[0].author == "egregora"
        assert annotations[0].commentary == "test annotation"

        # Verify SQL query was executed with correct parameters
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "msg-1" in call_args[0][1]
