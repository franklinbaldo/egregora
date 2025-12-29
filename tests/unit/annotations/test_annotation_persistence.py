from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from egregora.agents.shared.annotations import AnnotationStore
from egregora.data_primitives.document import DocumentType


class TestAnnotationStorePersistence:
    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.db = MagicMock()
        repo.db.ibis_conn = MagicMock()
        return repo

    def test_save_annotation_persists_document(self, mock_repo) -> None:
        store = AnnotationStore(repository=mock_repo)

        doc = store.save_annotation(
            parent_id="msg-123",
            parent_type="message",
            commentary="Important observation.",
        )

        mock_repo.save.assert_called_once()
        saved_doc = mock_repo.save.call_args[0][0]
        assert saved_doc.type == DocumentType.ANNOTATION
        assert saved_doc.content == "Important observation."
        assert saved_doc.metadata["parent_id"] == "msg-123"
        assert saved_doc.metadata["author_id"] == "egregora"
        assert saved_doc.metadata["category"] == "Annotations"

        assert doc == saved_doc

    def test_list_annotations_for_message(self, mock_repo) -> None:
        store = AnnotationStore(repository=mock_repo)

        # Mock DB response
        mock_table = MagicMock()
        mock_repo.db.read_table.return_value = mock_table
        mock_res = MagicMock()
        mock_res.empty = False
        mock_res.to_dict.return_value = [
            {
                "id": "ann-1",
                "content": "test",
                "created_at": datetime.now(UTC),
                "parent_id": "msg-1",
                "parent_type": "message",
            }
        ]
        mock_table.filter.return_value.order_by.return_value.execute.return_value = mock_res

        # Mock repository _row_to_document
        mock_repo._row_to_document.side_effect = lambda row, doc_type: MagicMock(id=row["id"])

        annotations = store.list_annotations_for_message("msg-1")

        assert len(annotations) == 1
        mock_repo.db.read_table.assert_called_with("annotations")
