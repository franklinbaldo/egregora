"""MkDocs site generation logic (Separation of Concerns).

This module handles the "presentation" layer of the MkDocs output adapter:
- Generating site statistics (word counts, author activity)
- Collecting recent media for the sidebar
- Generating author profile cards
- Updating the main landing page

It relies on the data provided by the OutputAdapter but owns the logic
for how that data is presented in the final static site.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from egregora.output_adapters.mkdocs.adapter import MkDocsAdapter

logger = logging.getLogger(__name__)


def get_site_stats(adapter: MkDocsAdapter) -> dict[str, Any]:
    """Calculate statistics for the site (posts, words, authors)."""
    posts = list(adapter.list_documents(DocumentType.POST))
    profiles = list(adapter.list_documents(DocumentType.PROFILE))
    media = list(adapter.list_documents(DocumentType.MEDIA))

    total_words = 0
    for doc in posts:
        # Simple word count approximation
        content = doc.content or ""
        total_words += len(content.split())

    # Get recent post date
    last_updated = "Never"
    if posts:
        dates = []
        for p in posts:
            d = p.metadata.get("date")
            if d:
                with contextlib.suppress(ValueError, TypeError):
                    dates.append(datetime.fromisoformat(d))
        if dates:
            last_updated = max(dates).strftime("%Y-%m-%d")

    return {
        "post_count": len(posts),
        "author_count": len(profiles),
        "media_count": len(media),
        "total_words": total_words,
        "last_updated": last_updated,
    }


def get_profiles_data(adapter: MkDocsAdapter) -> list[dict[str, Any]]:
    """Get data for all author profiles for templating."""
    profiles_data = []
    for doc in adapter.list_documents(DocumentType.PROFILE):
        data = doc.metadata.copy()
        data["content"] = doc.content
        data["id"] = doc.document_id
        # Add derived fields if needed
        profiles_data.append(data)

    # Sort by name if available, else ID
    profiles_data.sort(key=lambda x: x.get("name", x.get("id", "")))
    return profiles_data


def get_recent_media(adapter: MkDocsAdapter, limit: int = 5) -> list[dict[str, Any]]:
    """Get recent media items for display."""
    media_docs = list(adapter.list_documents(DocumentType.MEDIA))
    # Filter for images usually
    images = [d for d in media_docs if d.metadata.get("media_type", "").startswith("image/")]

    # Sort by date descending (assuming 'created_at' or 'date' in metadata)
    def get_date(d: Document) -> str:
        return str(d.metadata.get("created_at") or d.metadata.get("date") or "1970-01-01")

    images.sort(key=get_date, reverse=True)

    return [
        {
            "path": doc.metadata.get("path", ""),
            "caption": doc.metadata.get("caption", "") or doc.document_id,
            "date": get_date(doc),
        }
        for doc in images[:limit]
    ]


def _append_author_cards(content: str, adapter: MkDocsAdapter) -> str:
    """Append author cards to the content."""
    # This logic was previously inside MkDocsAdapter
    # It constructs a markdown section with author avatars/names

    profiles = get_profiles_data(adapter)
    if not profiles:
        return content

    cards_section = '\n\n## Contributors\n\n<div class="grid cards" markdown>\n'

    for profile in profiles:
        name = profile.get("name", "Unknown Author")
        avatar = profile.get("avatar_path") or profile.get("avatar_url", "")
        # bio = profile.get("bio", "") # unused in simple card

        # Relative path fixup might be needed depending on where this content is rendered
        # For now, assume avatar path is site-relative

        cards_section += f"-   **{name}**\n\n"
        if avatar:
            cards_section += f"    ![{name}]({avatar})\n\n"
        cards_section += f"    [:octicons-arrow-right-24: Profile](profiles/{profile.get('id')}.md)\n\n"

    cards_section += "</div>\n"

    return content + cards_section
