# tests/unit/metadata/test_publishable_metadata_tz.py

import pytest
from datetime import datetime, timezone
from egregora.data_primitives.document import Document, DocumentType
from egregora.metadata.publishable import PublishableMetadata

class TestPublishableMetadataTimezone:
    """Tests for timezone handling in PublishableMetadata."""

    def test_from_document_handles_naive_created_at(self) -> None:
        """Test that a naive created_at is treated as UTC in the output date string."""
        naive_dt = datetime(2025, 1, 15, 12, 0, 0)  # No tzinfo
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={"slug": "test"},
            created_at=naive_dt,
        )

        meta = PublishableMetadata.from_document(doc)

        # Should contain offset info (e.g. +00:00 or Z)
        assert meta.date == "2025-01-15T12:00:00+00:00"

    def test_from_document_preserves_aware_created_at(self) -> None:
        """Test that an aware created_at preserves its timezone."""
        aware_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        doc = Document(
            content="Content",
            type=DocumentType.POST,
            metadata={"slug": "test"},
            created_at=aware_dt,
        )

        meta = PublishableMetadata.from_document(doc)

        assert meta.date == "2025-01-15T12:00:00+00:00"
