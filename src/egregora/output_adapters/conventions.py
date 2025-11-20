"""Standard URL conventions for Egregora output adapters."""

from __future__ import annotations

from dataclasses import dataclass
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

    def canonical_url(self, document: Document, ctx: UrlContext) -> str:
        """Generate a canonical URL based on the standard convention."""
        base = ctx.base_url.rstrip("/")

        # 1. Blog Posts
        if document.type == DocumentType.POST:
            return self._format_post_url(base, document)

        # 2. Author Profiles
        if document.type == DocumentType.PROFILE:
            author_uuid = document.metadata.get("uuid") or document.metadata.get("author_uuid")
            if not author_uuid:
                # Fallback to document ID if metadata missing, though rare
                author_uuid = document.document_id
            return f"{base}/{self.routes.profiles_prefix}/{author_uuid}/"

        # 3. Journals (Agent Memory)
        if document.type == DocumentType.JOURNAL:
            window_label = document.metadata.get("window_label", document.source_window or "unlabeled")
            safe_label = slugify(window_label)
            # Often journals are kept under posts, or a separate section
            return f"{base}/{self.routes.posts_prefix}/{self.routes.journal_prefix}/{safe_label}/"

        # 4. Enrichments & Media
        if document.type in (
            DocumentType.ENRICHMENT_URL,
            DocumentType.ENRICHMENT_MEDIA,
            DocumentType.MEDIA,
        ):
            # Enrichments usually mirror the media file structure
            # We use the suggested_path if available, or fallback to ID
            if document.suggested_path:
                # suggested_path usually comes relative to site root (e.g., "media/images/x.jpg")
                # Ensure it handles the prefix correctly
                clean_path = document.suggested_path.strip("/")
                return f"{base}/{clean_path}"

            return f"{base}/{self.routes.media_prefix}/{document.document_id}/"

        # Fallback
        return f"{base}/documents/{document.document_id}/"

    def _format_post_url(self, base: str, document: Document) -> str:
        slug = document.metadata.get("slug", document.document_id[:8])
        normalized_slug = slugify(slug)

        prefix = f"{base}/{self.routes.posts_prefix}"

        if self.routes.date_in_url:
            date_val = document.metadata.get("date", "")
            if date_val:
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val).split(" ")[0]  # Safety chop
                return f"{prefix}/{date_str}-{normalized_slug}/"

        return f"{prefix}/{normalized_slug}/"
