"""Standard URL conventions for Egregora output adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from egregora.data_primitives.document import DocumentType
from egregora.data_primitives.protocols import UrlConvention
from egregora.utils.paths import slugify

if TYPE_CHECKING:
    from egregora.data_primitives.document import Document
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

    Generates deterministic, canonical URLs based on document content and metadata.
    Adapters can configure prefixes (e.g. 'blog' instead of 'posts') or subclass
    this to change the logic entirely.
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

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
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
            window_label = document.metadata.get("window_label", document.source_window or "unlabeled")
            safe_label = slugify(window_label)
            # Often journals are kept under posts, or a separate section
            return self._join(ctx, self.routes.posts_prefix, self.routes.journal_prefix, safe_label)

        if document.type == DocumentType.MEDIA:
            return self._format_media_url(ctx, document)

        if document.type == DocumentType.ENRICHMENT_MEDIA:
            return self._format_media_enrichment_url(ctx, document)

        if document.type == DocumentType.ENRICHMENT_URL:
            if document.suggested_path:
                clean_path = document.suggested_path.strip("/")
                return self._join(ctx, clean_path, trailing_slash=False)
            return self._join(
                ctx, self.routes.media_prefix, "urls", document.document_id + ".md", trailing_slash=False
            )

        # Fallback
        return self._join(ctx, "documents", document.document_id)

    def _format_post_url(self, ctx: UrlContext, document: Document) -> str:
        slug = document.metadata.get("slug", document.document_id[:8])
        normalized_slug = slugify(slug)

        if self.routes.date_in_url:
            date_val = document.metadata.get("date", "")
            if date_val:
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val).split(" ")[0]  # Safety chop
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
            enrichment_path = Path(parent_path).with_suffix(".md").as_posix()
            return self._join(ctx, enrichment_path.strip("/"), trailing_slash=False)

        if document.suggested_path:
            clean_path = document.suggested_path.strip("/")
            return self._join(ctx, clean_path, trailing_slash=False)

        fallback = f"{document.document_id}.md"
        return self._join(ctx, self.routes.media_prefix, fallback, trailing_slash=False)
