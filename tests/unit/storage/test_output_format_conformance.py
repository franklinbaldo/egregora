"""Conformance tests for OutputFormat protocol.

These tests should pass for ANY OutputFormat implementation.
They verify that the format correctly implements the protocol contract.
"""

from datetime import datetime

import pytest

from egregora.core.document import Document, DocumentType
from egregora.storage.url_convention import UrlContext


class OutputFormatConformanceTests:
    """Base conformance tests for OutputFormat implementations.

    Subclass this and provide the output_format, url_convention, and ctx fixtures
    to run conformance tests for your OutputFormat implementation.

    Example:
        class TestMyFormatConformance(OutputFormatConformanceTests):
            @pytest.fixture
            def output_format(self):
                return MyOutputFormat(...)

            @pytest.fixture
            def url_convention(self):
                return MyUrlConvention()

            @pytest.fixture
            def ctx(self):
                return UrlContext(base_url="https://example.com")
    """

    @pytest.fixture
    def sample_doc(self):
        """Create sample document for testing."""
        return Document(
            content="Test content",
            type=DocumentType.POST,
            metadata={"slug": "test-post", "date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime(2025, 1, 11),
            source_window=None,
            suggested_path=None,
        )

    @pytest.fixture
    def sample_profile(self):
        """Create sample profile document."""
        return Document(
            content="Profile content",
            type=DocumentType.PROFILE,
            metadata={"uuid": "test-author-123"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

    @pytest.fixture
    def sample_media(self):
        """Create sample media document."""
        # Note: Using text content since Document.document_id doesn't handle bytes properly
        return Document(
            content="fake-image-data",
            type=DocumentType.MEDIA,
            metadata={"filename": "photo.jpg", "mime_type": "image/jpeg"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path="photo.jpg",
        )

    def test_convention_name_and_version(self, output_format):
        """OutputFormat exposes convention name and version."""
        convention = output_format.url_convention

        assert convention.name
        assert isinstance(convention.name, str)
        assert convention.version
        assert isinstance(convention.version, str)

    def test_url_determinism(self, url_convention, ctx, sample_doc):
        """Same document always returns same URL from convention."""
        url1 = url_convention.canonical_url(sample_doc, ctx)
        url2 = url_convention.canonical_url(sample_doc, ctx)

        assert url1 == url2
        assert isinstance(url1, str)
        assert len(url1) > 0

    def test_idempotency(self, output_format, sample_doc):
        """Multiple serve() calls are safe no-ops."""
        # First call - should persist document
        output_format.serve(sample_doc)

        # Second call should be no-op (no error, no duplicate)
        output_format.serve(sample_doc)

        # Third call for good measure
        output_format.serve(sample_doc)

        # Format-specific check that document is actually served
        # (subclasses may override this with format-specific verification)

    def test_serve_returns_none(self, output_format, sample_doc):
        """serve() returns None (void function)."""
        result = output_format.serve(sample_doc)

        assert result is None

    def test_different_documents_different_urls(self, url_convention, ctx):
        """Different documents get different URLs."""
        doc1 = Document(
            content="Content A",
            type=DocumentType.POST,
            metadata={"slug": "post-a", "date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        doc2 = Document(
            content="Content B",
            type=DocumentType.POST,
            metadata={"slug": "post-b", "date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url1 = url_convention.canonical_url(doc1, ctx)
        url2 = url_convention.canonical_url(doc2, ctx)

        assert url1 != url2

    def test_core_and_format_use_same_convention(self, url_convention, output_format, sample_doc, ctx):
        """Core and format calculate same URL from same convention."""
        # Core calculates URL
        url_from_core = url_convention.canonical_url(sample_doc, ctx)

        # Format calculates URL (internally via serve)
        output_format.serve(sample_doc)

        # Both should result in same URL when using format's convention
        url_from_format = output_format.url_convention.canonical_url(sample_doc, ctx)

        # URLs should match (both use same convention)
        assert url_from_core == url_from_format

    def test_media_documents(self, url_convention, output_format, ctx, sample_media):
        """Media documents work same as other documents."""
        # Core calculates URL
        url = url_convention.canonical_url(sample_media, ctx)

        assert isinstance(url, str)
        assert len(url) > 0
        # Media URL should contain filename or reference to content
        assert "photo" in url.lower() or "jpg" in url.lower()

        # Format serves document (should not raise)
        output_format.serve(sample_media)

    def test_all_document_types(self, url_convention, output_format, ctx):
        """All document types generate valid URLs and can be served."""
        test_docs = [
            # POST
            Document(
                content="Post",
                type=DocumentType.POST,
                metadata={"slug": "test", "date": datetime(2025, 1, 11)},
                parent_id=None,
                created_at=datetime.now(),
                source_window=None,
                suggested_path=None,
            ),
            # PROFILE
            Document(
                content="Profile",
                type=DocumentType.PROFILE,
                metadata={"uuid": "author-123"},
                parent_id=None,
                created_at=datetime.now(),
                source_window=None,
                suggested_path=None,
            ),
            # JOURNAL
            Document(
                content="Journal",
                type=DocumentType.JOURNAL,
                metadata={"window_label": "Window 1"},
                parent_id=None,
                created_at=datetime.now(),
                source_window=None,
                suggested_path=None,
            ),
            # ENRICHMENT_URL
            Document(
                content="URL description",
                type=DocumentType.ENRICHMENT_URL,
                metadata={},
                parent_id="parent-123",
                created_at=datetime.now(),
                source_window=None,
                suggested_path=None,
            ),
            # ENRICHMENT_MEDIA
            Document(
                content="Media description",
                type=DocumentType.ENRICHMENT_MEDIA,
                metadata={},
                parent_id=None,
                created_at=datetime.now(),
                source_window=None,
                suggested_path="photo.jpg",
            ),
            # MEDIA (using text content since Document.document_id doesn't handle bytes)
            Document(
                content="binary-data",
                type=DocumentType.MEDIA,
                metadata={"mime_type": "image/jpeg"},
                parent_id=None,
                created_at=datetime.now(),
                source_window=None,
                suggested_path="image.jpg",
            ),
        ]

        for doc in test_docs:
            # Should generate valid URL
            url = url_convention.canonical_url(doc, ctx)
            assert isinstance(url, str)
            assert len(url) > 0

            # Should be servable
            output_format.serve(doc)

    def test_convention_compatibility_check(self, url_convention, output_format):
        """Convention names match between Core and Format."""
        # In real usage, Core would check:
        # assert output_format.url_convention.name == core_convention.name

        # Here we just verify format exposes the convention
        assert output_format.url_convention.name == url_convention.name
        assert output_format.url_convention.version == url_convention.version


# Helper for format-specific tests to extend
class OutputFormatTestHelper:
    """Helper methods for format-specific conformance tests."""

    @staticmethod
    def assert_document_served(output_format, document, ctx):
        """Assert that document is actually served (format-specific).

        Subclasses should implement this to check format-specific storage.

        Args:
            output_format: The OutputFormat instance
            document: The document that should be served
            ctx: The UrlContext used

        Raises:
            AssertionError: If document is not properly served
        """
        raise NotImplementedError("Subclass should implement format-specific verification")
