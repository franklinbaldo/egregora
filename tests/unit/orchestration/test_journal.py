
import pytest
from unittest.mock import Mock, MagicMock
from uuid import uuid4
from datetime import datetime, UTC

from egregora.data_primitives.document import DocumentType, Document, DocumentMetadata
from egregora.orchestration.journal import window_already_processed, create_journal_document

class TestJournalUtils:

    def test_window_not_processed_yet(self):
        """Test that returns False when no journal with signature exists."""
        mock_output_sink = Mock()
        # Mock list() to return an empty iterator or iterator with unrelated documents
        mock_output_sink.list.return_value = iter([
            DocumentMetadata(
                identifier="journal-other",
                doc_type=DocumentType.JOURNAL,
                metadata={"window_signature": "different-signature"}
            )
        ])

        result = window_already_processed(mock_output_sink, "target-signature")

        assert result is False
        mock_output_sink.list.assert_called_once_with(DocumentType.JOURNAL)

    def test_window_already_processed(self):
        """Test that returns True when journal with signature exists."""
        mock_output_sink = Mock()
        mock_output_sink.list.return_value = iter([
            DocumentMetadata(
                identifier="journal-target",
                doc_type=DocumentType.JOURNAL,
                metadata={"window_signature": "target-signature"}
            )
        ])

        result = window_already_processed(mock_output_sink, "target-signature")

        assert result is True
        mock_output_sink.list.assert_called_once_with(DocumentType.JOURNAL)

    def test_window_processed_check_handles_exception(self):
        """Test that exception during check is handled gracefully (returns False)."""
        mock_output_sink = Mock()
        mock_output_sink.list.side_effect = Exception("Sink error")

        result = window_already_processed(mock_output_sink, "any-signature")

        assert result is False

    def test_create_journal_document_structure(self):
        """Test creation of Journal document with correct fields."""
        run_id = uuid4()
        now = datetime.now(UTC)
        signature = "abc123456789"

        doc = create_journal_document(
            signature=signature,
            run_id=run_id,
            window_start=now,
            window_end=now,
            model="gpt-4",
            posts_generated=5,
            profiles_updated=2
        )

        assert isinstance(doc, Document)
        assert doc.type == DocumentType.JOURNAL
        assert doc.id == "journal-abc123456789"
        assert doc.metadata["window_signature"] == signature
        assert doc.metadata["run_id"] == str(run_id)
        assert doc.metadata["model"] == "gpt-4"
        assert doc.metadata["posts_generated"] == 5
        assert doc.metadata["profiles_updated"] == 2
