"""Standard URL conventions for Egregora output adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlConvention
from egregora.utils.paths import slugify

if TYPE_CHECKING:
    from egregora.data_primitives.protocols import UrlContext


@dataclass
class RouteConfig:
    """Configuration for URL routing segments."""

    posts_prefix: str = "posts"
    profiles_prefix: str = "profiles"
    media_prefix: str = "media"
    journal_prefix: str = "journal"
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
        url = f"{base}/{path}" if base else f"/{path}"
        if trailing_slash:
            return url.rstrip("/") + "/"
        return url

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:  # noqa: PLR0911
        """Generate a canonical URL based on the standard convention."""
        # 1. Blog Posts
        if document.type == DocumentType.POST:
            return self._format_post_url(ctx, document)

        # 2. Author Profiles
        if document.type == DocumentType.PROFILE:
            author_uuid = document.metadata.get("uuid") or document.metadata.get("author_uuid")
            if not author_uuid:
                # Fallback to document ID if metadata missing, though rare
                author_uuid = document.document_id
            return self._join(ctx, self.routes.profiles_prefix, author_uuid)

        # 3. Journals (Agent Memory)
        if document.type == DocumentType.JOURNAL:
            window_label = document.metadata.get("window_label")
            if window_label:
                safe_label = slugify(window_label)
                return self._join(ctx, self.routes.journal_prefix, safe_label)
            slug_value = document.metadata.get("slug")
            if slug_value:
                safe_label = slugify(slug_value)
                return self._join(ctx, self.routes.journal_prefix, safe_label)
            # Fallback: no window_label or slug, return journal root
            return self._join(ctx, self.routes.journal_prefix)

        if document.type == DocumentType.MEDIA:
            return self._format_media_url(ctx, document)

        if document.type == DocumentType.ENRICHMENT_MEDIA:
            return self._format_media_enrichment_url(ctx, document)

        if document.type == DocumentType.ENRICHMENT_URL:
            if document.suggested_path:
                clean_path = Path(document.suggested_path.strip("/")).with_suffix("").as_posix()
                return self._join(ctx, clean_path, trailing_slash=True)
            url_slug = self._slug_with_identifier(document)
            return self._join(
                ctx,
                self.routes.media_prefix,
                "urls",
                url_slug,
            )

        # Fallback
        return self._join(ctx, "documents", document.document_id)

    def _format_post_url(self, ctx: UrlContext, document: Document) -> str:
        slug = document.metadata.get("slug", document.document_id[:8])
        normalized_slug = slugify(slug)

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
        # Default to /media/{doc_id}
        filename = document.metadata.get("filename")
        path_segment = filename or f"{document.document_id}"
        return self._join(ctx, self.routes.media_prefix, path_segment, trailing_slash=False)

    def _format_media_enrichment_url(self, ctx: UrlContext, document: Document) -> str:
        """Mirror parent media path but swap extension for markdown."""
        parent_path = None
        if document.parent and document.parent.suggested_path:
            parent_path = document.parent.suggested_path
        elif document.metadata.get("parent_path"):
            parent_path = document.metadata["parent_path"]

        if parent_path:
            enrichment_path = Path(parent_path).with_suffix("").as_posix()
            return self._join(ctx, enrichment_path.strip("/"), trailing_slash=True)

        if document.suggested_path:
            clean_path = Path(document.suggested_path.strip("/")).with_suffix("").as_posix()
            return self._join(ctx, clean_path, trailing_slash=True)

        fallback = f"{self._slug_with_identifier(document)}"
        return self._join(ctx, self.routes.media_prefix, fallback, trailing_slash=True)

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
