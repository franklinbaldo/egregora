"""Unit tests for UrlConvention implementations.

Tests verify that UrlConvention uses ONLY string operations,
no Path or filesystem dependencies.
"""

import inspect

import pytest

import egregora.output_sinks.conventions as conventions_module
from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.output_sinks.conventions import StandardUrlConvention, _remove_url_extension


class TestUrlExtensionRemoval:
    """Test pure string-based extension removal."""

    def test_removes_extension_from_simple_path(self):
        assert _remove_url_extension("file.md") == "file"
        assert _remove_url_extension("image.png") == "image"

    def test_removes_extension_from_nested_path(self):
        assert _remove_url_extension("media/images/foo.png") == "media/images/foo"
        assert _remove_url_extension("posts/2025-01-10.md") == "posts/2025-01-10"

    def test_preserves_dots_in_directory_names(self):
        assert _remove_url_extension("some.dir/file.md") == "some.dir/file"
        assert _remove_url_extension("v1.0/api.json") == "v1.0/api"

    def test_handles_no_extension(self):
        assert _remove_url_extension("posts/hello") == "posts/hello"
        assert _remove_url_extension("media/video") == "media/video"

    def test_handles_multiple_dots(self):
        assert _remove_url_extension("archive.tar.gz") == "archive.tar"
        assert _remove_url_extension("path/to/file.backup.md") == "path/to/file.backup"

    def test_preserves_dotfiles(self):
        """Dotfiles (starting with .) should be preserved, not treated as extensions."""
        assert _remove_url_extension(".config") == ".config"
        assert _remove_url_extension(".gitignore") == ".gitignore"
        assert _remove_url_extension("path/.config") == "path/.config"
        assert _remove_url_extension("path/.gitignore") == "path/.gitignore"
        assert _remove_url_extension("media/.htaccess") == "media/.htaccess"


class TestStandardUrlConventionPurity:
    """Verify StandardUrlConvention uses only strings, no Path operations."""

    @pytest.fixture
    def convention(self):
        return StandardUrlConvention()

    @pytest.fixture
    def ctx(self):
        return UrlContext(base_url="https://example.com", site_prefix="blog")

    def test_post_url_is_pure_string(self, convention, ctx):
        doc = Document(
            type=DocumentType.POST,
            content="Test post",
            metadata={"slug": "hello-world", "date": "2025-01-10"},
        )
        url = convention.canonical_url(doc, ctx)
        assert url == "https://example.com/blog/posts/2025-01-10-hello-world/"
        assert isinstance(url, str)

    def test_enrichment_url_removes_extension_via_string_ops(self, convention, ctx):
        """Verify extension removal uses string ops, not Path.with_suffix()."""
        doc = Document(
            type=DocumentType.ENRICHMENT_URL,
            content="Enrichment",
            suggested_path="media/urls/article.html",
        )
        url = convention.canonical_url(doc, ctx)
        # Should remove .html extension via string manipulation
        assert ".html" not in url
        assert "article" in url

    def test_media_enrichment_preserves_path_structure(self, convention, ctx):
        """Verify path manipulation uses string ops, not Path.as_posix()."""
        parent = Document(
            type=DocumentType.MEDIA,
            content=b"image data",
            suggested_path="media/images/photo.jpg",
        )
        doc = Document(
            type=DocumentType.ENRICHMENT_MEDIA,
            content="Photo description",
            parent=parent,
        )
        url = convention.canonical_url(doc, ctx)
        # Should use parent path structure via string ops
        assert "media/images/photo" in url
        assert ".jpg" not in url  # Extension removed via string ops

    def test_profile_url_generation(self, convention, ctx):
        """Test profile URL generation uses string operations only."""
        doc = Document(
            type=DocumentType.PROFILE,
            content="Profile content",
            metadata={"uuid": "abc123", "subject": "abc123", "slug": "bio"},
        )
        url = convention.canonical_url(doc, ctx)
        assert url == "https://example.com/blog/profiles/abc123/bio/"
        assert isinstance(url, str)

    def test_journal_url_generation(self, convention, ctx):
        """Test journal URL generation uses string operations only."""
        doc = Document(
            type=DocumentType.JOURNAL,
            content="Journal entry",
            metadata={"window_label": "2025-W01"},
        )
        url = convention.canonical_url(doc, ctx)
        assert "journal" in url
        assert isinstance(url, str)


class TestUrlConventionNoFilesystemDependency:
    """Ensure UrlConvention has NO filesystem dependencies."""

    def test_no_path_import_in_conventions_module(self):
        """Verify conventions.py does not import pathlib.Path."""
        # Check module doesn't have Path in its namespace
        assert not hasattr(conventions_module, "Path")

        # Verify by checking source
        source = inspect.getsource(conventions_module)
        assert "from pathlib import Path" not in source
        assert "import pathlib" not in source

    def test_no_path_operations_in_canonical_url(self):
        """Verify canonical_url method doesn't use Path operations."""
        source = inspect.getsource(StandardUrlConvention.canonical_url)
        # Should not contain Path constructor calls
        assert "Path(" not in source
        # Should not contain filesystem-specific methods
        assert ".with_suffix(" not in source
        assert ".as_posix(" not in source

    def test_no_path_operations_in_helper_methods(self):
        """Verify helper methods don't use Path operations."""
        methods = [
            "_format_post_url",
            "_format_media_url",
            "_format_url_enrichment_url",
            "_format_media_enrichment_url",
        ]
        for method_name in methods:
            method = getattr(StandardUrlConvention, method_name)
            source = inspect.getsource(method)
            assert "Path(" not in source, f"{method_name} contains Path operations"
            assert ".with_suffix(" not in source, f"{method_name} uses .with_suffix()"
            assert ".as_posix(" not in source, f"{method_name} uses .as_posix()"


class TestStandardUrlConventionFallbacks:
    """Test fallback logic for URL generation when metadata is missing."""

    @pytest.fixture
    def convention(self):
        return StandardUrlConvention()

    @pytest.fixture
    def ctx(self):
        return UrlContext()

    def test_format_profile_url_fallback(self, convention, ctx):
        """Test _format_profile_url fallback when slug is None."""
        doc = Document(
            type=DocumentType.PROFILE,
            content="Test",
            metadata={"subject": "author-uuid", "slug": None},
        )
        # Without a slug, it should use the document ID's first 8 chars
        fallback_slug = doc.document_id[:8]
        url = convention.canonical_url(doc, ctx)
        assert f"/{convention.routes.profiles_prefix}/author-uuid/{fallback_slug}/" in url

    def test_format_journal_url_fallback(self, convention, ctx):
        """Test _format_journal_url fallback when labels are missing."""
        doc = Document(type=DocumentType.JOURNAL, content="Test")
        # Without window_label or slug, it should fall back to posts/journal-{id}
        url = convention.canonical_url(doc, ctx)
        assert f"/{convention.routes.posts_prefix}/journal-" in url

    def test_format_annotation_url_fallback(self, convention, ctx):
        """Test _format_annotation_url fallback when slug is None."""
        doc = Document(
            type=DocumentType.ANNOTATION,
            content="Test",
            metadata={"slug": None},
        )
        # slugify(None) raises, so it should fall back to the document ID's first 8 chars
        fallback_slug = doc.document_id[:8]
        url = convention.canonical_url(doc, ctx)
        assert f"/{convention.routes.annotations_prefix}/{fallback_slug}/" in url

    def test_format_post_url_fallback(self, convention, ctx):
        """Test _format_post_url fallback when slug is None."""
        doc = Document(
            type=DocumentType.POST,
            content="Test",
            metadata={"slug": None, "date": "2025-01-10"},
        )
        # slugify(None) raises, so it should fall back to the document ID's first 8 chars
        fallback_slug = doc.document_id[:8]
        url = convention.canonical_url(doc, ctx)
        assert f"/posts/2025-01-10-{fallback_slug}/" in url
