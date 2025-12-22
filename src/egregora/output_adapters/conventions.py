"""Standard URL generation conventions for the Egregora static site.

This module defines the `StandardUrlConvention`, which implements the logic
for creating canonical, predictable, and semantic URLs for different
document types (e.g., posts, profiles, media).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from egregora.data_primitives.document import Document, DocumentType
from egregora.data_primitives.protocols import UrlConvention
from egregora.utils.paths import slugify

if TYPE_CHECKING:
    from egregora.data_primitives.protocols import UrlContext


def _remove_url_extension(url_path: str) -> str:
    """Remove extension from the last segment of a URL path, preserving dotfiles."""
    parts = url_path.rsplit("/", 1)
    filename = parts[-1]
    if "." in filename and not filename.startswith("."):
        parts[-1] = filename.rsplit(".", 1)[0]
    return "/".join(parts)


@dataclass(frozen=True)
class RouteConfig:
    posts_prefix: str = "posts"
    profiles_prefix: str = "profiles"
    media_prefix: str = "posts/media"
    journal_prefix: str = "journal"
    annotations_prefix: str = "posts/annotations"
    date_in_url: bool = True


class StandardUrlConvention(UrlConvention):
    name, version = "standard-v1", "1.1.0"

    def __init__(self, routes: RouteConfig | None = None) -> None:
        self.routes = routes or RouteConfig()

    def _join(self, ctx: UrlContext, *segments: str, trailing_slash: bool = True) -> str:
        base = (ctx.base_url or "").rstrip("/")
        prefix = (ctx.site_prefix or "").strip("/")

        # Build path segments filtering empty strings
        all_parts = [p for p in prefix.split("/") if p] + [s.strip("/") for s in segments if s]
        path = "/".join(all_parts)

        url = f"{base}/{path}" if base else f"/{path}"
        return url.rstrip("/") + "/" if trailing_slash else url.rstrip("/")

    def _get_slug(self, doc: Document) -> str:
        return slugify(doc.metadata.get("slug", doc.document_id[:8]))

    def canonical_url(self, doc: Document, ctx: UrlContext) -> str:
        handlers = {
            DocumentType.POST: self._format_post,
            DocumentType.PROFILE: self._format_profile,
            DocumentType.ANNOUNCEMENT: self._format_announcement,
            DocumentType.JOURNAL: self._format_journal,
            DocumentType.MEDIA: self._format_media,
            DocumentType.ENRICHMENT_URL: self._format_url_enrichment,
            DocumentType.ANNOTATION: self._format_annotation,
            DocumentType.ENRICHMENT_MEDIA: lambda c, d: self._format_enrichment(c, d),
            DocumentType.ENRICHMENT_IMAGE: lambda c, d: self._format_enrichment(c, d, "images"),
            DocumentType.ENRICHMENT_VIDEO: lambda c, d: self._format_enrichment(c, d, "videos"),
            DocumentType.ENRICHMENT_AUDIO: lambda c, d: self._format_enrichment(c, d, "audio"),
        }
        return handlers.get(doc.type, lambda c, d: self._join(c, "docs", d.document_id))(ctx, doc)

    def _format_post(self, ctx: UrlContext, doc: Document) -> str:
        slug = self._get_slug(doc)
        if self.routes.date_in_url and (date_val := doc.metadata.get("date")):
            date_str = date_val.date().isoformat() if isinstance(date_val, datetime) else str(date_val)[:10]
            slug = f"{date_str}-{slug}"
        return self._join(ctx, self.routes.posts_prefix, slug)

    def _format_profile(self, ctx: UrlContext, doc: Document) -> str:
        m = doc.metadata
        uid = m.get("subject") or m.get("uuid") or m.get("author_uuid")
        slug = slugify(m.get("slug") or m.get("profile_aspect") or doc.document_id[:8])
        return (
            self._join(ctx, self.routes.profiles_prefix, str(uid), slug)
            if uid
            else self._join(ctx, self.routes.posts_prefix, slug)
        )

    def _format_announcement(self, ctx: UrlContext, doc: Document) -> str:
        """Format URL for ANNOUNCEMENT documents (user command events).

        ANNOUNCEMENT documents with 'subject' metadata route to the author's profile feed:
        /profiles/{subject_uuid}/{slug}/

        This creates a unified feed showing both:
        - PROFILE posts (Egregora's analyses)
        - ANNOUNCEMENT posts (user actions/commands)
        """
        subject_uuid = doc.metadata.get("subject") or doc.metadata.get("actor")
        if not subject_uuid:
            # Fallback: route to announcements directory if no subject
            slug = doc.metadata.get("slug", doc.document_id[:8])
            return self._join(ctx, self.routes.posts_prefix, "announcements", slugify(slug))

        # Route to author's profile feed
        slug_value = doc.metadata.get("slug") or doc.document_id[:8]
        return self._join(ctx, self.routes.profiles_prefix, str(subject_uuid), slugify(str(slug_value)))

    def _format_journal(self, ctx: UrlContext, doc: Document) -> str:
        label = doc.metadata.get("window_label") or doc.metadata.get("slug")
        return (
            self._join(ctx, self.routes.journal_prefix, slugify(label))
            if label
            else self._join(ctx, self.routes.journal_prefix)
        )

    def _format_media(self, ctx: UrlContext, doc: Document) -> str:
        if doc.suggested_path:
            return self._join(ctx, doc.suggested_path, trailing_slash=False)

        from egregora.ops.media import get_media_subfolder

        # Prefer semantic slug, then filename, then document_id
        slug_base = doc.metadata.get("slug")
        fname = doc.metadata.get("filename", doc.document_id)

        # Use the slug as the name if we have it, otherwise fallback to filename/ID
        name_segment = slug_base or fname

        # Ensure we have an extension if possible
        ext = f".{fname.rsplit('.', 1)[-1]}" if "." in fname else ""
        if not name_segment.endswith(ext) and ext:
            name_segment = f"{name_segment}{ext}"

        return self._join(
            ctx, self.routes.media_prefix, get_media_subfolder(ext), name_segment, trailing_slash=False
        )

    def _format_enrichment(self, ctx: UrlContext, doc: Document, subfolder: str | None = None) -> str:
        """Generic handler for all media enrichment types."""
        # 1. Try parent path logic
        parent_path = (doc.parent.suggested_path if doc.parent else None) or doc.metadata.get("parent_path")
        if parent_path:
            path = _remove_url_extension(parent_path.strip("/"))
            # Clean redundancy: remove base/site prefixes from the string if present
            prefixes = [
                f"{(ctx.site_prefix or '').strip('/')}/{self.routes.media_prefix.strip('/')}",
                self.routes.media_prefix.strip("/"),
                "media",
                "posts/media",
            ]
            for p in prefixes:
                if path.startswith(p + "/"):
                    path = path.removeprefix(p + "/").strip("/")
                    break
            return self._join(ctx, self.routes.media_prefix, path)

        # 2. Try document's own suggested path
        if doc.suggested_path:
            return self._join(ctx, _remove_url_extension(doc.suggested_path), trailing_slash=True)

        # 3. Fallback to slug-based
        slug = f"{doc.slug}-{doc.document_id[:8]}" if not doc.slug.endswith(doc.document_id[:8]) else doc.slug
        parts = [self.routes.media_prefix, subfolder, slug] if subfolder else [self.routes.media_prefix, slug]
        return self._join(ctx, *parts)

    def _format_url_enrichment(self, ctx: UrlContext, doc: Document) -> str:
        if doc.suggested_path:
            return self._join(ctx, _remove_url_extension(doc.suggested_path))
        slug = f"{doc.slug}-{doc.document_id[:8]}" if not doc.slug.endswith(doc.document_id[:8]) else doc.slug
        return self._join(ctx, self.routes.media_prefix, "urls", slug)

    def _format_annotation(self, ctx: UrlContext, doc: Document) -> str:
        return self._join(ctx, self.routes.annotations_prefix, self._get_slug(doc))
