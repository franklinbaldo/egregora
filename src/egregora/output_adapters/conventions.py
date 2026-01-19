"""Standard URL conventions for Egregora output adapters.

SEPARATION OF CONCERNS (2025-11-29):
=====================================

This module implements UrlConvention protocol - PURELY LOGICAL URL GENERATION.

What UrlConvention does:
- Given a Document, return what URL readers should use
- Pure string manipulation only
- No filesystem knowledge (no Path, no docs_dir, no file extensions as filesystem concept)
- Uses only doc.type, slug, tags, date metadata

What UrlConvention does NOT do:
- Filesystem path resolution (that's OutputAdapter's job)
- File layout decisions (index.md vs foo.md)
- Directory structure (docs/, media/, etc.)

Examples:
    >>> convention = StandardUrlConvention()
    >>> ctx = UrlContext(base_url="https://example.com", site_prefix="blog")
    >>> doc = Document(type=DocumentType.POST, metadata={"slug": "hello", "date": "2025-01-10"})
    >>> convention.canonical_url(doc, ctx)
    'https://example.com/blog/posts/2025-01-10-hello/'

The OutputAdapter then converts this URL to a filesystem path:
    >>> adapter.persist(doc)  # Internally: URL -> Path("docs/posts/2025-01-10-hello.md")

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from egregora.data_primitives.document import Document, DocumentType, UrlConvention
from egregora.data_primitives.text import InvalidInputError, slugify

if TYPE_CHECKING:
    from egregora.data_primitives.document import UrlContext


EXPECTED_PARTS_WITH_PATH = 2


def _remove_url_extension(url_path: str) -> str:
    """Remove file extension from URL path segment.

    This is URL logic (removing trailing .html, .md, etc. from URLs),
    not filesystem logic (Path.with_suffix). URLs may contain dots
    that aren't extensions, so we only remove extensions from the
    last path segment.

    Dotfiles (files starting with a dot like '.config') are preserved
    as they don't have an extension to remove.

    Args:
        url_path: URL path like 'media/images/foo.png' or 'posts/bar'

    Returns:
        URL path without extension: 'media/images/foo' or 'posts/bar'

    Examples:
        >>> _remove_url_extension("media/images/foo.png")
        'media/images/foo'
        >>> _remove_url_extension("posts/bar")
        'posts/bar'
        >>> _remove_url_extension("some.dir/file.md")
        'some.dir/file'
        >>> _remove_url_extension(".config")
        '.config'
        >>> _remove_url_extension("path/.gitignore")
        'path/.gitignore'

    """
    if "." not in url_path:
        return url_path

    # Split on last slash to get the last segment
    parts = url_path.rsplit("/", 1)

    if len(parts) == EXPECTED_PARTS_WITH_PATH and "." in parts[1]:
        # Has a path and a filename with extension
        # Remove extension from the filename only
        basename_without_ext = parts[1].rsplit(".", 1)[0]
        # Check if this is a dotfile (basename would be empty after split)
        if not basename_without_ext:
            # This is a dotfile, preserve it
            return url_path
        return f"{parts[0]}/{basename_without_ext}"
    if "." in parts[0]:
        # Just a filename with extension (no slashes)
        basename_without_ext = parts[0].rsplit(".", 1)[0]
        # Check if this is a dotfile (basename would be empty after split)
        if not basename_without_ext:
            # This is a dotfile, preserve it
            return url_path
        return basename_without_ext

    return url_path


@dataclass
class RouteConfig:
    """Configuration for URL routing segments."""

    posts_prefix: str = "posts"
    profiles_prefix: str = "profiles"
    # ADR-001: Media goes inside posts directory
    media_prefix: str = "posts/media"
    journal_prefix: str = "posts"
    annotations_prefix: str = "posts/annotations"
    # Defines if dates should be part of the URL structure: /2025-01-01-slug/ vs /slug/
    date_in_url: bool = True


class StandardUrlConvention(UrlConvention):
    """The default, opinionated URL scheme for Egregora sites.

    **Role: Single Source of Truth for Document Persistence**

    This class is the **authoritative source** for how documents are addressed
    and persisted to the filesystem. All document writes flow through the
    `canonical_url()` method, which generates deterministic URLs based on
    document type and metadata.

    **Document Flow:**
    ```
    Document → canonical_url() → URL → adapter._url_to_path() → filesystem
    ```

    **Per-Type URL Rules:**
    - PROFILE: /profiles/{uuid} (uses full UUID from metadata)
    - POST: /posts/{slug} (filename includes date prefix: {date}-{slug}.md)
    - JOURNAL: /journal/{label} (slugified window label)
    - MEDIA: /media/{type}/{hash}.{ext} (hash-based naming)
    - ENRICHMENT_MEDIA: /media/{type}/{parent_slug} (paired with media file)
    - ENRICHMENT_URL: /media/urls/{identifier}/ (uses suggested_path if available)

    **Contract with Adapters:**
    - Adapters **must** use `canonical_url()` to generate URLs
    - Adapters **must not** manually construct file paths
    - URL → path translation is adapter-specific (_url_to_path())
    - This ensures consistency across all document references

    **Configuration:**
    - Route prefixes can be customized via `RouteConfig`
    - Subclass to implement entirely different URL schemes
    - Version tracked for migration/compatibility

    See: ``docs/architecture/url-conventions.md`` for complete documentation.
    """

    def __init__(self, routes: RouteConfig | None = None) -> None:
        self.routes = routes or RouteConfig()

    @property
    def name(self) -> str:
        return "standard-v1"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _build_base(self, ctx: UrlContext) -> tuple[str, list[str]]:
        base = (ctx.base_url or "").rstrip("/")
        prefix = (ctx.site_prefix or "").strip("/")
        segments: list[str] = []
        if prefix:
            segments.extend(prefix.split("/"))
        return base, segments

    def _join(self, ctx: UrlContext, *segments: str, trailing_slash: bool = True) -> str:
        base, prefix_segments = self._build_base(ctx)
        clean_segments = [seg.strip("/") for seg in segments if seg]
        path_segments = prefix_segments + clean_segments
        path = "/".join(path_segments)
        # Restore leading slash to make paths root-relative when base is empty
        url = f"{base}/{path}" if base else f"/{path}"
        if trailing_slash:
            return url.rstrip("/") + "/"
        return url

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Generate a canonical URL based on the standard convention."""
        handlers = {
            DocumentType.POST: self._format_post_url,
            DocumentType.PROFILE: self._format_profile_url,
            DocumentType.JOURNAL: self._format_journal_url,
            DocumentType.MEDIA: self._format_media_url,
            DocumentType.ENRICHMENT_MEDIA: self._format_media_enrichment_url,
            DocumentType.ENRICHMENT_IMAGE: lambda ctx, doc: self._format_typed_media_enrichment_url(
                ctx, doc, "images"
            ),
            DocumentType.ENRICHMENT_VIDEO: lambda ctx, doc: self._format_typed_media_enrichment_url(
                ctx, doc, "videos"
            ),
            DocumentType.ENRICHMENT_AUDIO: lambda ctx, doc: self._format_typed_media_enrichment_url(
                ctx, doc, "audio"
            ),
            DocumentType.ENRICHMENT_URL: self._format_url_enrichment_url,
            DocumentType.ANNOTATION: self._format_annotation_url,
        }

        handler = handlers.get(document.type)
        if handler:
            return handler(ctx, document)

        # Fallback
        return self._join(ctx, "documents", document.document_id)

    def _format_profile_url(self, ctx: UrlContext, document: Document) -> str:
        subject_uuid = (
            document.metadata.get("subject")
            or document.metadata.get("uuid")
            or document.metadata.get("author_uuid")
        )
        slug_value = (
            document.metadata.get("slug")
            or document.metadata.get("profile_aspect")
            or document.document_id[:8]
        )
        try:
            safe_slug = slugify(slug_value)
        except InvalidInputError:
            safe_slug = document.document_id[:8]

        if not subject_uuid:
            return self._join(ctx, self.routes.posts_prefix, safe_slug)
        return self._join(ctx, self.routes.profiles_prefix, str(subject_uuid), safe_slug)

    def _format_journal_url(self, ctx: UrlContext, document: Document) -> str:
        window_label = document.metadata.get("window_label")
        if window_label:
            try:
                safe_label = slugify(window_label)
                return self._join(ctx, self.routes.journal_prefix, f"journal-{safe_label}")
            except InvalidInputError:
                pass  # Fallback to slug_value

        slug_value = document.metadata.get("slug")
        if slug_value:
            try:
                safe_label = slugify(slug_value)
                return self._join(ctx, self.routes.journal_prefix, f"journal-{safe_label}")
            except InvalidInputError:
                pass  # Fallback to posts_prefix

        # Fallback: no window_label or slug, use document ID with journal- prefix
        fallback_slug = f"journal-{document.document_id[:8]}"
        return self._join(ctx, self.routes.posts_prefix, fallback_slug)

    def _format_url_enrichment_url(self, ctx: UrlContext, document: Document) -> str:
        if document.suggested_path:
            # Pure string manipulation - no Path operations
            clean_path = _remove_url_extension(document.suggested_path.strip("/"))
            return self._join(ctx, clean_path, trailing_slash=True)
        url_slug = self._slug_with_identifier(document)
        return self._join(
            ctx,
            self.routes.media_prefix,
            "urls",
            url_slug,
        )

    def _format_annotation_url(self, ctx: UrlContext, document: Document) -> str:
        slug = document.metadata.get("slug", document.document_id[:8])
        try:
            safe_slug = slugify(slug)
        except InvalidInputError:
            safe_slug = document.document_id[:8]
        return self._join(ctx, self.routes.annotations_prefix, safe_slug)

    def _format_post_url(self, ctx: UrlContext, document: Document) -> str:
        slug = document.metadata.get("slug", document.document_id[:8])
        try:
            normalized_slug = slugify(slug)
        except InvalidInputError:
            normalized_slug = document.document_id[:8]

        if self.routes.date_in_url:
            date_val = document.metadata.get("date", "")
            if date_val:
                date_str = _date_to_iso_date(date_val)
                return self._join(ctx, self.routes.posts_prefix, f"{date_str}-{normalized_slug}")

        return self._join(ctx, self.routes.posts_prefix, normalized_slug)

    def _format_media_url(self, ctx: UrlContext, document: Document) -> str:
        """Resolve canonical URL for media assets."""
        if document.suggested_path:
            clean_path = document.suggested_path.strip("/")
            return self._join(ctx, clean_path, trailing_slash=False)

        # Legacy/Fallback: Infer subdirectory from extension
        from egregora.ops.media import get_media_subfolder

        filename = document.metadata.get("filename")
        path_segment = filename or f"{document.document_id}"

        # Extract extension using string manipulation (not Path)
        extension = ""
        if "." in path_segment:
            extension = "." + path_segment.rsplit(".", 1)[1]
        media_subdir = get_media_subfolder(extension)

        # New robust path: {media_prefix}/{subdir}/{filename}
        return self._join(ctx, self.routes.media_prefix, media_subdir, path_segment, trailing_slash=False)

    def _format_media_enrichment_url(self, ctx: UrlContext, document: Document) -> str:
        """Mirror parent media path but swap extension for markdown."""
        parent_path = None
        if document.parent and document.parent.suggested_path:
            parent_path = document.parent.suggested_path
        elif document.metadata.get("parent_path"):
            parent_path = document.metadata["parent_path"]

        if parent_path:
            # Pure string manipulation - no Path operations
            enrichment_path = _remove_url_extension(parent_path.strip("/"))
            # Strip any existing site_prefix or media_prefix to avoid duplication
            # when _join adds them again
            site_prefix = (ctx.site_prefix or "").strip("/")
            media_prefix = self.routes.media_prefix.strip("/")
            for prefix in [f"{site_prefix}/{media_prefix}", site_prefix, media_prefix]:
                if prefix and enrichment_path.startswith(prefix + "/"):
                    enrichment_path = enrichment_path[len(prefix) + 1 :]
                    break

            # Fix: Check for partial overlap (e.g., prefix "posts/media", path "media/images/...")
            # This handles cases where the source path assumes a "media/" root.
            if "/" in media_prefix:
                last_segment = media_prefix.rsplit("/", 1)[-1]
                if enrichment_path.startswith(f"{last_segment}/"):
                    enrichment_path = enrichment_path[len(last_segment) + 1 :]
            return self._join(ctx, self.routes.media_prefix, enrichment_path, trailing_slash=True)

        if document.suggested_path:
            # Pure string manipulation - no Path operations
            clean_path = _remove_url_extension(document.suggested_path.strip("/"))
            return self._join(ctx, clean_path, trailing_slash=True)

        fallback = f"{self._slug_with_identifier(document)}"
        return self._join(ctx, self.routes.media_prefix, fallback, trailing_slash=True)

    def _format_typed_media_enrichment_url(self, ctx: UrlContext, document: Document, subfolder: str) -> str:
        """Format URL for typed media enrichment (images, videos, audio).

        Args:
            ctx: URL context
            document: The enrichment document
            subfolder: Target subfolder (e.g., "images", "videos", "audio")

        """
        slug = self._slug_with_identifier(document)
        return self._join(ctx, self.routes.media_prefix, subfolder, slug, trailing_slash=True)

    def _slug_with_identifier(self, document: Document) -> str:
        """Return slug augmented with a deterministic identifier."""
        slug_value = document.slug
        suffix = document.document_id[:8]
        if slug_value.endswith(suffix):
            return slug_value
        return f"{slug_value}-{suffix}"


def _date_to_iso_date(value: datetime | str) -> str:
    """Return ISO date (YYYY-MM-DD) from datetime/string."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value)
    if "T" in text:
        return text.split("T", 1)[0]
    if " " in text:
        return text.split(" ", 1)[0]
    return text
