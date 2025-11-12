"""Legacy MkDocs URL convention (v1).

Maintains exact same URL structure as current MkDocsDocumentStorage implementation.
Agents continue to get identical URLs for cross-references - no breaking changes.

URL patterns:
- Posts: /posts/{YYYY-MM-DD}-{slug}/
- Profiles: /profiles/{author_id}/
- Journals: /posts/journal/journal_{window_label}/
- URL enrichments: /docs/media/urls/{doc_id}/
- Media enrichments: /docs/media/{filename}
- Media files: /docs/media/{filename}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document
    from egregora.storage.url_convention import UrlContext

from egregora.data_primitives.document import DocumentType


class LegacyMkDocsUrlConvention:
    """Legacy MkDocs URL convention (v1).

    Reproduces URL structure from original MkDocsDocumentStorage.
    Deterministic and stable - same document always produces same URL.
    """

    @property
    def name(self) -> str:
        """Convention identifier."""
        return "legacy-mkdocs"

    @property
    def version(self) -> str:
        """Convention version."""
        return "v1"

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Generate canonical URL using legacy MkDocs rules.

        Args:
            document: Document to generate URL for
            ctx: Context with base_url, etc.

        Returns:
            Canonical URL as string

        Examples:
            >>> ctx = UrlContext(base_url="https://example.com")
            >>> convention.canonical_url(post_doc, ctx)
            'https://example.com/posts/2025-01-11-my-post/'

        """
        base = ctx.base_url.rstrip("/")

        if document.type == DocumentType.POST:
            return self._post_url(document, base)
        if document.type == DocumentType.PROFILE:
            return self._profile_url(document, base)
        if document.type == DocumentType.JOURNAL:
            return self._journal_url(document, base)
        if document.type == DocumentType.ENRICHMENT_URL:
            return self._url_enrichment_url(document, base)
        if document.type == DocumentType.ENRICHMENT_MEDIA:
            return self._media_enrichment_url(document, base)
        if document.type == DocumentType.MEDIA:
            return self._media_url(document, base)
        # Fallback for unknown types
        return f"{base}/documents/{document.document_id}/"

    def _post_url(self, document: Document, base: str) -> str:
        """Generate URL for post document."""
        # Extract metadata (same logic as _determine_post_path)
        slug = document.metadata.get("slug", document.document_id[:8])
        date = document.metadata.get("date", "")

        # Normalize slug
        normalized_slug = self._slugify(slug)

        # Generate URL pattern: /posts/{date}-{slug}/
        if date:
            # Handle date: can be datetime object or string
            if hasattr(date, "strftime"):
                date_str = date.strftime("%Y-%m-%d")
            else:
                date_str = str(date)
            return f"{base}/posts/{date_str}-{normalized_slug}/"
        return f"{base}/posts/{normalized_slug}/"

    def _profile_url(self, document: Document, base: str) -> str:
        """Generate URL for profile document."""
        author_uuid = document.metadata.get("uuid", document.metadata.get("author_uuid"))
        if not author_uuid:
            msg = "Profile document must have 'uuid' or 'author_uuid' in metadata"
            raise ValueError(msg)

        return f"{base}/profiles/{author_uuid}/"

    def _journal_url(self, document: Document, base: str) -> str:
        """Generate URL for journal entry."""
        window_label = document.metadata.get("window_label", document.source_window or "unlabeled")

        # Sanitize label for URL (same logic as _determine_journal_path)
        safe_label = window_label.replace(" ", "_").replace(":", "-")

        return f"{base}/posts/journal/journal_{safe_label}/"

    def _url_enrichment_url(self, document: Document, base: str) -> str:
        """Generate URL for URL enrichment (content-addressed)."""
        return f"{base}/docs/media/urls/{document.document_id}/"

    def _media_enrichment_url(self, document: Document, base: str) -> str:
        """Generate URL for media enrichment."""
        # Use suggested_path or fall back to document_id
        filename = document.suggested_path or f"{document.document_id}.md"

        # Remove prefix if present (same as _determine_media_enrichment_path)
        filename = filename.removeprefix("docs/media/")

        return f"{base}/docs/media/{filename}"

    def _media_url(self, document: Document, base: str) -> str:
        """Generate URL for media file."""
        # Use suggested_path or fall back to document_id
        filename = document.suggested_path or document.document_id

        # Remove prefix if present (same as _determine_media_path)
        filename = filename.removeprefix("docs/media/")

        return f"{base}/docs/media/{filename}"

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug.

        Same logic as current implementation in _determine_post_path.

        Args:
            text: Text to slugify

        Returns:
            URL-safe slug (lowercase, alphanumeric + hyphens)

        Examples:
            >>> conv._slugify("My Post Title")
            'my-post-title'
            >>> conv._slugify("Post #2!")
            'post-2'

        """
        # Normalize: lowercase, replace spaces with hyphens
        slug = text.lower().replace(" ", "-")

        # Keep only alphanumeric and hyphens
        slug = "".join(c for c in slug if c.isalnum() or c == "-")

        # Remove multiple consecutive hyphens
        while "--" in slug:
            slug = slug.replace("--", "-")

        # Strip hyphens from edges
        return slug.strip("-")
