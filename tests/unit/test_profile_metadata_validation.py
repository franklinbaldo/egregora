"""Tests for profile metadata validation.

Ensures that all profile Documents include required 'subject' metadata
to prevent routing issues.
"""

import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.orchestration.persistence import validate_profile_document


class TestProfileMetadataValidation:
    """Test suite for profile document validation."""

    def test_valid_profile_document(self):
        """Valid profile document with subject metadata should pass validation."""
        doc = Document(
            content="# Profile Content",
            type=DocumentType.PROFILE,
            metadata={"subject": "test-author-uuid", "slug": "test-profile"},
        )

        # Should not raise
        validate_profile_document(doc)

    def test_profile_missing_subject_metadata(self):
        """Profile document without subject metadata should fail validation."""
        doc = Document(
            content="# Profile Content",
            type=DocumentType.PROFILE,
            metadata={"slug": "test-profile"},  # Missing 'subject'
        )

        with pytest.raises(ValueError, match="missing required 'subject' metadata"):
            validate_profile_document(doc)

    def test_profile_with_empty_subject(self):
        """Profile document with empty subject should fail validation."""
        doc = Document(
            content="# Profile Content",
            type=DocumentType.PROFILE,
            metadata={"subject": "", "slug": "test-profile"},
        )

        with pytest.raises(ValueError, match="missing required 'subject' metadata"):
            validate_profile_document(doc)

    def test_profile_with_none_subject(self):
        """Profile document with None subject should fail validation."""
        doc = Document(
            content="# Profile Content",
            type=DocumentType.PROFILE,
            metadata={"subject": None, "slug": "test-profile"},
        )

        with pytest.raises(ValueError, match="missing required 'subject' metadata"):
            validate_profile_document(doc)

    def test_wrong_document_type(self):
        """Validation should reject non-PROFILE documents."""
        doc = Document(
            content="# Post Content",
            type=DocumentType.POST,
            metadata={"subject": "test-author-uuid", "slug": "test-post"},
        )

        with pytest.raises(ValueError, match="Expected PROFILE document"):
            validate_profile_document(doc)

    def test_profile_with_valid_uuid_format(self):
        """Profile document with properly formatted UUID should pass."""
        doc = Document(
            content="# Profile Content",
            type=DocumentType.PROFILE,
            metadata={
                "subject": "550e8400-e29b-41d4-a716-446655440000",  # Valid UUID
                "slug": "test-profile",
            },
        )

        # Should not raise
        validate_profile_document(doc)

    def test_profile_with_short_uuid(self):
        """Profile document with shortened UUID (first 8 chars) should pass."""
        doc = Document(
            content="# Profile Content",
            type=DocumentType.PROFILE,
            metadata={
                "subject": "550e8400",  # Shortened UUID (first 8)
                "slug": "test-profile",
            },
        )

        # Should not raise (any non-empty string is valid)
        validate_profile_document(doc)


class TestProfilePersistence:
    """Test profile document persistence with validation."""

    def test_persist_profile_document_validates(self):
        """persist_profile_document should validate before persisting."""
        from unittest.mock import Mock

        from egregora.orchestration.persistence import persist_profile_document

        mock_sink = Mock()
        mock_sink.persist = Mock()

        # Should succeed with valid author_uuid
        doc_id = persist_profile_document(mock_sink, "test-uuid", "Profile content")

        # Verify persist was called
        assert mock_sink.persist.called
        assert doc_id is not None

        # Verify the document has subject metadata
        persisted_doc = mock_sink.persist.call_args[0][0]
        assert persisted_doc.metadata.get("subject") == "test-uuid"

    def test_persist_profile_document_empty_uuid(self):
        """persist_profile_document should reject empty author_uuid."""
        from unittest.mock import Mock

        from egregora.orchestration.persistence import persist_profile_document

        mock_sink = Mock()

        with pytest.raises(ValueError, match="author_uuid is required"):
            persist_profile_document(mock_sink, "", "Profile content")

    def test_persist_profile_document_none_uuid(self):
        """persist_profile_document should reject None author_uuid."""
        from unittest.mock import Mock

        from egregora.orchestration.persistence import persist_profile_document

        mock_sink = Mock()

        with pytest.raises(ValueError, match="author_uuid is required"):
            persist_profile_document(mock_sink, None, "Profile content")  # type: ignore


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
