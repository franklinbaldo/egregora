import calendar
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import feedparser

from egregora_v3.core.ports import InputAdapter
from egregora_v3.core.types import Author, Entry, Link


class RSSAdapter(InputAdapter):
    """Parses RSS/Atom feeds into a stream of Entries.

    Uses `feedparser` to normalize differences between RSS 1.0, 2.0, and Atom.
    """

    def parse(self, source: Path | str) -> Iterator[Entry]:
        """Parses a local feed file or URL.

        Args:
            source: Path to the RSS/Atom XML file, or a URL string.

        Yields:
            Entry: Normalized Atom-compliant entry.

        Raises:
            ValueError: If the feed is malformed or cannot be parsed.
        """
        # If source is a Path, ensure it exists
        if isinstance(source, Path):
            if not source.exists():
                raise FileNotFoundError(f"Feed file not found: {source}")
            # Convert Path to str for feedparser (it handles file paths correctly)
            source_arg = str(source)
        else:
            # Assume it's a URL or XML string. feedparser handles URLs.
            # If it's a raw XML string, feedparser handles that too.
            # However, standard practice for 'parse' taking 'source' usually implies a location.
            source_arg = source

        feed = feedparser.parse(source_arg)

        if feed.bozo:
            # feedparser sets bozo=1 if there's an error (XML parsing, etc.)
            # We treat this as a failure for strictness, unless it's a minor encoding issue.
            # For this implementation, we'll raise.
            # Note: bozo_exception might be present.
            if hasattr(feed, "bozo_exception"):
                raise ValueError(f"Failed to parse feed: {feed.bozo_exception}")

        for item in feed.entries:
            yield self._map_item_to_entry(item)

    def _map_item_to_entry(self, item: feedparser.FeedParserDict) -> Entry:
        """Maps a feedparser item to an Egregora Entry."""
        # ID: Prefer id, fall back to link
        entry_id = item.get("id") or item.get("link")
        if not entry_id:
            # Fallback: Generate deterministic ID from title or content
            # If both are missing, use random UUID (last resort)
            import hashlib
            import uuid

            hasher = hashlib.sha256()

            # Mix available data to ensure uniqueness
            hasher.update((item.get("title") or "").encode("utf-8"))
            hasher.update((item.get("summary") or "").encode("utf-8"))

            # If we have content, mix it in
            if "content" in item and item.content:
                 hasher.update((item.content[0].get("value") or "").encode("utf-8"))

            entry_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, hasher.hexdigest()))

        # Title
        title = item.get("title", "Untitled")

        # Dates: published vs updated
        # feedparser returns time.struct_time
        updated_parsed = item.get("updated_parsed") or item.get("published_parsed")
        published_parsed = item.get("published_parsed")

        updated = self._struct_time_to_datetime(updated_parsed) if updated_parsed else datetime.now(UTC)
        published = self._struct_time_to_datetime(published_parsed) if published_parsed else None

        # Content
        # Prefer content (full), then summary
        content = None
        summary = item.get("summary")

        if "content" in item:
            # item.content is a list of dicts: [{'type': 'text/html', 'value': '...'}]
            # We take the first one
            content_obj = item.content[0]
            content = content_obj.get("value")

        # Authors
        authors = []
        if "authors" in item:
            for a in item.authors:
                authors.append(Author(name=a.get("name", "Unknown"), email=a.get("email")))
        elif "author" in item:
            authors.append(Author(name=item.author))

        # Links
        links = []
        if "links" in item:
            for link in item.links:
                length = link.get("length")
                if length:
                    try:
                        length = int(length)
                    except (ValueError, TypeError):
                        length = None

                links.append(
                    Link(
                        href=link.get("href"),
                        rel=link.get("rel"),
                        type=link.get("type"),
                        title=link.get("title"),
                        length=length,
                        hreflang=link.get("hreflang"),
                    )
                )

        # Sanitize feedparser item for extensions (remove struct_time objects)
        # feedparser returns struct_time in keys ending with '_parsed'
        original_data = {
            k: v
            for k, v in item.items()
            if k not in ("title", "id") and not k.endswith("_parsed")
        }

        return Entry(
            id=entry_id,
            title=title,
            updated=updated,
            published=published,
            content=content,
            summary=summary,
            authors=authors,
            links=links,
            # Extensions can capture raw extra data if needed
            extensions={"feedparser_original": original_data},
        )

    @staticmethod
    def _struct_time_to_datetime(st: Any) -> datetime:
        """Converts time.struct_time to timezone-aware datetime (UTC)."""
        # mktime -> epoch -> datetime
        # feedparser returns UTC struct_time (usually), so we should use timegm
        # to get the correct epoch timestamp from it.
        dt = datetime.fromtimestamp(calendar.timegm(st), tz=UTC)
        return dt
