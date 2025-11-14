"""Tests for URL convention protocol and implementations."""

from datetime import datetime

import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlContext
from egregora.output_adapters.mkdocs import LegacyMkDocsUrlConvention


class TestLegacyMkDocsUrlConvention:
    """Tests for LegacyMkDocsUrlConvention."""

    @pytest.fixture
    def convention(self):
        """Create convention instance."""
        return LegacyMkDocsUrlConvention()

    @pytest.fixture
    def ctx(self):
        """Create URL context."""
        return UrlContext(base_url="https://example.com")

    @pytest.fixture
    def ctx_no_base(self):
        """Create URL context without base URL."""
        return UrlContext(base_url="")

    def test_convention_identity(self, convention):
        """Convention has name and version."""
        assert convention.name == "legacy-mkdocs"
        assert convention.version == "v1"

    def test_post_url_with_date(self, convention, ctx):
        """Post with date generates correct URL."""
        doc = Document(
            content="Test post",
            type=DocumentType.POST,
            metadata={"slug": "my-post", "date": datetime(2025, 1, 11), "title": "My Post"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/posts/2025-01-11-my-post/"

    def test_post_url_without_date(self, convention, ctx):
        """Post without date generates URL with just slug."""
        doc = Document(
            content="Test post",
            type=DocumentType.POST,
            metadata={"slug": "my-post", "title": "My Post"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/posts/my-post/"

    def test_post_url_slugifies_title(self, convention, ctx):
        """Post URL slugifies title to create safe slug."""
        doc = Document(
            content="Test post",
            type=DocumentType.POST,
            metadata={"slug": "My Post Title!", "date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/posts/2025-01-11-my-post-title/"

    def test_post_url_uses_doc_id_fallback(self, convention, ctx):
        """Post URL falls back to document_id if no slug."""
        doc = Document(
            content="Test post",
            type=DocumentType.POST,
            metadata={"date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        # Should use first 8 chars of document_id
        assert url.startswith("https://example.com/posts/2025-01-11-")
        assert len(url.split("/")[-2].split("-")[-1]) == 8  # 8 char ID after date

    def test_profile_url(self, convention, ctx):
        """Profile generates correct URL."""
        doc = Document(
            content="Profile content",
            type=DocumentType.PROFILE,
            metadata={"uuid": "abc123"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/profiles/abc123/"

    def test_profile_url_author_uuid_fallback(self, convention, ctx):
        """Profile falls back to author_uuid."""
        doc = Document(
            content="Profile content",
            type=DocumentType.PROFILE,
            metadata={"author_uuid": "xyz789"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/profiles/xyz789/"

    def test_profile_url_missing_uuid_raises(self, convention, ctx):
        """Profile without uuid raises ValueError."""
        doc = Document(
            content="Profile content",
            type=DocumentType.PROFILE,
            metadata={},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        with pytest.raises(ValueError, match="uuid.*author_uuid"):
            convention.canonical_url(doc, ctx)

    def test_journal_url(self, convention, ctx):
        """Journal generates correct URL."""
        doc = Document(
            content="Journal content",
            type=DocumentType.JOURNAL,
            metadata={"window_label": "Window 1"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/posts/journal/journal_Window_1/"

    def test_journal_url_sanitizes_label(self, convention, ctx):
        """Journal URL sanitizes window label."""
        doc = Document(
            content="Journal content",
            type=DocumentType.JOURNAL,
            metadata={"window_label": "Window: 2"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/posts/journal/journal_Window-_2/"

    def test_journal_url_fallback_to_source_window(self, convention, ctx):
        """Journal falls back to source_window."""
        doc = Document(
            content="Journal content",
            type=DocumentType.JOURNAL,
            metadata={},
            parent_id=None,
            created_at=datetime.now(),
            source_window="window-0",
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/posts/journal/journal_window-0/"

    def test_url_enrichment_url(self, convention, ctx):
        """URL enrichment generates content-addressed URL."""
        doc = Document(
            content="URL description",
            type=DocumentType.ENRICHMENT_URL,
            metadata={},
            parent_id="parent-123",
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == f"https://example.com/docs/media/urls/{doc.document_id}/"

    def test_media_enrichment_url_with_suggested_path(self, convention, ctx):
        """Media enrichment uses suggested_path."""
        doc = Document(
            content="Media description",
            type=DocumentType.ENRICHMENT_MEDIA,
            metadata={"filename": "photo.jpg"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path="docs/media/photo.jpg",
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/docs/media/photo.jpg"

    def test_media_enrichment_url_strips_prefix(self, convention, ctx):
        """Media enrichment strips docs/media/ prefix."""
        doc = Document(
            content="Media description",
            type=DocumentType.ENRICHMENT_MEDIA,
            metadata={},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path="docs/media/subfolder/photo.jpg",
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/docs/media/subfolder/photo.jpg"

    def test_media_enrichment_url_fallback_to_doc_id(self, convention, ctx):
        """Media enrichment falls back to document_id."""
        doc = Document(
            content="Media description",
            type=DocumentType.ENRICHMENT_MEDIA,
            metadata={},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == f"https://example.com/docs/media/{doc.document_id}.md"

    def test_media_url_with_suggested_path(self, convention, ctx):
        """Media file uses suggested_path."""
        doc = Document(
            content=b"binary content",
            type=DocumentType.MEDIA,
            metadata={"mime_type": "image/jpeg"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path="docs/media/photo.jpg",
        )

        url = convention.canonical_url(doc, ctx)

        assert url == "https://example.com/docs/media/photo.jpg"

    def test_media_url_fallback_to_doc_id(self, convention, ctx):
        """Media file falls back to document_id."""
        doc = Document(
            content="text content",  # Use text to avoid bytes.encode() error
            type=DocumentType.MEDIA,
            metadata={"mime_type": "image/jpeg"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx)

        assert url == f"https://example.com/docs/media/{doc.document_id}"

    def test_url_determinism(self, convention, ctx):
        """Same document always produces same URL."""
        doc = Document(
            content="Test post",
            type=DocumentType.POST,
            metadata={"slug": "my-post", "date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url1 = convention.canonical_url(doc, ctx)
        url2 = convention.canonical_url(doc, ctx)

        assert url1 == url2

    def test_url_without_base_url(self, convention, ctx_no_base):
        """URLs work without base_url (relative URLs)."""
        doc = Document(
            content="Test post",
            type=DocumentType.POST,
            metadata={"slug": "my-post", "date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = convention.canonical_url(doc, ctx_no_base)

        assert url == "/posts/2025-01-11-my-post/"

    def test_slugify_complex_text(self, convention):
        """Slugify handles complex text correctly."""
        assert convention._slugify("My Post Title!") == "my-post-title"
        assert convention._slugify("Post #2: Test") == "post-2-test"
        assert convention._slugify("  Multiple   Spaces  ") == "multiple-spaces"
        assert convention._slugify("CamelCase") == "camelcase"
        # Underscore is removed (only alphanumeric + hyphens allowed)
        assert convention._slugify("under_score") == "underscore"
        assert convention._slugify("---multiple---hyphens---") == "multiple-hyphens"
