import calendar
import hashlib
import uuid
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
                message = f"Feed file not found: {source}"
                raise FileNotFoundError(message)
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
                message = f"Failed to parse feed: {feed.bozo_exception}"
                raise ValueError(message)
            message = "Failed to parse feed"
            raise ValueError(message)

        for item in feed.entries:
            yield self._map_item_to_entry(item)

    def _map_item_to_entry(self, item: feedparser.FeedParserDict) -> Entry:
        """Maps a feedparser item to an Egregora Entry."""
        entry_id = self._resolve_entry_id(item)
        updated, published = self._parse_dates(item)
        content, summary = self._parse_content(item)
        authors = self._parse_authors(item)
        links = self._parse_links(item)
        original_data = self._sanitize_original_data(item)

        return Entry(
            id=entry_id,
            title=item.get("title", "Untitled"),
            updated=updated,
            published=published,
            content=content,
            summary=summary,
            authors=authors,
            links=links,
            # Extensions can capture raw extra data if needed
            extensions={"feedparser_original": original_data},
        )

    def _resolve_entry_id(self, item: feedparser.FeedParserDict) -> str:
        entry_id = item.get("id") or item.get("link")
        if entry_id:
            return entry_id

        hasher = hashlib.sha256()
        hasher.update((item.get("title") or "").encode("utf-8"))
        hasher.update((item.get("summary") or "").encode("utf-8"))

        if "content" in item and item.content:
            hasher.update((item.content[0].get("value") or "").encode("utf-8"))

        return str(uuid.uuid5(uuid.NAMESPACE_DNS, hasher.hexdigest()))

    def _parse_dates(self, item: feedparser.FeedParserDict) -> tuple[datetime, datetime | None]:
        updated_parsed = item.get("updated_parsed") or item.get("published_parsed")
        published_parsed = item.get("published_parsed")

        updated = self._struct_time_to_datetime(updated_parsed) if updated_parsed else datetime.now(UTC)
        published = self._struct_time_to_datetime(published_parsed) if published_parsed else None
        return updated, published

    def _parse_content(self, item: feedparser.FeedParserDict) -> tuple[str | None, str | None]:
        summary = item.get("summary")
        if "content" in item:
            content_obj = item.content[0]
            return content_obj.get("value"), summary
        return None, summary

    def _parse_authors(self, item: feedparser.FeedParserDict) -> list[Author]:
        if "authors" in item:
            return [Author(name=a.get("name", "Unknown"), email=a.get("email")) for a in item.authors]
        if "author" in item:
            return [Author(name=item.author)]
        return []

    def _parse_links(self, item: feedparser.FeedParserDict) -> list[Link]:
        links: list[Link] = []
        if "links" not in item:
            return links

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

        return links

    def _sanitize_original_data(self, item: feedparser.FeedParserDict) -> dict[str, Any]:
        return {k: v for k, v in item.items() if k not in ("title", "id") and not k.endswith("_parsed")}

    @staticmethod
    def _struct_time_to_datetime(st: Any) -> datetime:
        """Converts time.struct_time to timezone-aware datetime (UTC)."""
        # mktime -> epoch -> datetime
        # feedparser returns UTC struct_time (usually), so we should use timegm
        # to get the correct epoch timestamp from it.
        return datetime.fromtimestamp(calendar.timegm(st), tz=UTC)
