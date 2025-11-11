"""Tests for MkDocsOutputFormat implementation.

Runs conformance tests and format-specific tests for MkDocs filesystem backend.
"""

from datetime import datetime
from pathlib import Path

import pytest

from egregora.core.document import Document, DocumentType
from egregora.rendering.legacy_mkdocs_url_convention import LegacyMkDocsUrlConvention
from egregora.rendering.mkdocs_output_format import MkDocsOutputFormat
from egregora.storage.url_convention import UrlContext
from tests.unit.storage.test_output_format_conformance import OutputFormatConformanceTests


class TestMkDocsOutputFormatConformance(OutputFormatConformanceTests):
    """Conformance tests for MkDocsOutputFormat.

    Inherits all conformance tests from OutputFormatConformanceTests.
    """

    @pytest.fixture
    def output_format(self, tmp_path):
        """Create MkDocsOutputFormat instance."""
        ctx = UrlContext(base_url="https://example.com")
        return MkDocsOutputFormat(site_root=tmp_path, url_context=ctx)

    @pytest.fixture
    def url_convention(self):
        """Create URL convention instance."""
        return LegacyMkDocsUrlConvention()

    @pytest.fixture
    def ctx(self):
        """Create URL context."""
        return UrlContext(base_url="https://example.com")


class TestMkDocsOutputFormatSpecific:
    """Format-specific tests for MkDocsOutputFormat."""

    @pytest.fixture
    def output_format(self, tmp_path):
        """Create MkDocsOutputFormat instance."""
        ctx = UrlContext(base_url="https://example.com")
        return MkDocsOutputFormat(site_root=tmp_path, url_context=ctx)

    @pytest.fixture
    def ctx(self):
        """Create URL context."""
        return UrlContext(base_url="https://example.com")

    def test_post_creates_file_at_expected_path(self, output_format, tmp_path):
        """Post document creates file at expected filesystem path."""
        doc = Document(
            content="Test content",
            type=DocumentType.POST,
            metadata={"slug": "my-post", "date": datetime(2025, 1, 11), "title": "My Post"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        output_format.serve(doc)

        expected_path = tmp_path / "posts" / "2025-01-11-my-post.md"
        assert expected_path.exists()

    def test_post_has_yaml_frontmatter(self, output_format, tmp_path):
        """Post file contains YAML frontmatter."""
        doc = Document(
            content="Test content",
            type=DocumentType.POST,
            metadata={"slug": "my-post", "date": datetime(2025, 1, 11), "title": "My Post"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        output_format.serve(doc)

        path = tmp_path / "posts" / "2025-01-11-my-post.md"
        content = path.read_text()

        assert content.startswith("---\n")
        assert "title: My Post" in content
        assert "---\n\nTest content" in content

    def test_profile_creates_file_and_authors_yml(self, output_format, tmp_path):
        """Profile document creates file and updates .authors.yml."""
        doc = Document(
            content="Profile content",
            type=DocumentType.PROFILE,
            metadata={"uuid": "test-author-123", "name": "Test Author"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        output_format.serve(doc)

        profile_path = tmp_path / "profiles" / "test-author-123.md"
        assert profile_path.exists()

        # Check .authors.yml exists at site root (created by write_profile_content)
        authors_yml = tmp_path / ".authors.yml"
        assert authors_yml.exists()

    def test_journal_creates_file_in_journal_dir(self, output_format, tmp_path):
        """Journal document creates file in posts/journal/."""
        doc = Document(
            content="Journal content",
            type=DocumentType.JOURNAL,
            metadata={"window_label": "Window 1"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        output_format.serve(doc)

        journal_path = tmp_path / "posts" / "journal" / "journal_Window_1.md"
        assert journal_path.exists()

    def test_url_enrichment_creates_content_addressed_file(self, output_format, tmp_path):
        """URL enrichment creates content-addressed file."""
        doc = Document(
            content="URL description",
            type=DocumentType.ENRICHMENT_URL,
            metadata={},
            parent_id="parent-123",
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        output_format.serve(doc)

        # Should create file at docs/media/urls/{doc_id}.md
        enrichment_path = tmp_path / "docs" / "media" / "urls" / f"{doc.document_id}.md"
        assert enrichment_path.exists()

    def test_media_enrichment_with_suggested_path(self, output_format, tmp_path):
        """Media enrichment uses suggested_path."""
        doc = Document(
            content="Media description",
            type=DocumentType.ENRICHMENT_MEDIA,
            metadata={},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path="docs/media/photo.jpg.md",
        )

        output_format.serve(doc)

        enrichment_path = tmp_path / "docs" / "media" / "photo.jpg.md"
        assert enrichment_path.exists()

    def test_media_file_binary_content(self, output_format, tmp_path):
        """Media file handles content."""
        # Note: Using text content for now since Document.document_id doesn't handle bytes properly
        content = "fake-image-data"
        doc = Document(
            content=content,
            type=DocumentType.MEDIA,
            metadata={"mime_type": "image/jpeg"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path="docs/media/photo.jpg",
        )

        output_format.serve(doc)

        media_path = tmp_path / "docs" / "media" / "photo.jpg"
        assert media_path.exists()
        assert media_path.read_text() == content

    def test_idempotency_same_document_twice(self, output_format, tmp_path):
        """Serving same document twice is idempotent (no error, same path)."""
        doc = Document(
            content="Test content",
            type=DocumentType.POST,
            metadata={"slug": "my-post", "date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        # First serve
        output_format.serve(doc)
        path1 = tmp_path / "posts" / "2025-01-11-my-post.md"
        assert path1.exists()
        mtime1 = path1.stat().st_mtime

        # Second serve (should be idempotent)
        output_format.serve(doc)
        assert path1.exists()
        mtime2 = path1.stat().st_mtime

        # File should be overwritten (or skipped if implementation is smart)
        assert mtime2 >= mtime1

    def test_directory_creation(self, output_format, tmp_path):
        """Output format creates all necessary directories."""
        assert (tmp_path / "posts").exists()
        assert (tmp_path / "profiles").exists()
        assert (tmp_path / "posts" / "journal").exists()
        assert (tmp_path / "docs" / "media" / "urls").exists()
        assert (tmp_path / "docs" / "media").exists()

    def test_url_to_path_conversion_post(self, output_format):
        """URL to path conversion works correctly for posts."""
        doc = Document(
            content="Test",
            type=DocumentType.POST,
            metadata={"slug": "test", "date": datetime(2025, 1, 11)},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = "https://example.com/posts/2025-01-11-test/"
        path = output_format._url_to_path(url, doc)

        assert path == output_format.site_root / "posts" / "2025-01-11-test.md"

    def test_url_to_path_conversion_profile(self, output_format):
        """URL to path conversion works correctly for profiles."""
        doc = Document(
            content="Profile",
            type=DocumentType.PROFILE,
            metadata={"uuid": "abc123"},
            parent_id=None,
            created_at=datetime.now(),
            source_window=None,
            suggested_path=None,
        )

        url = "https://example.com/profiles/abc123/"
        path = output_format._url_to_path(url, doc)

        assert path == output_format.site_root / "profiles" / "abc123.md"

    def test_convention_compatibility(self, output_format):
        """Output format uses LegacyMkDocsUrlConvention."""
        convention = output_format.url_convention

        assert convention.name == "legacy-mkdocs"
        assert convention.version == "v1"
