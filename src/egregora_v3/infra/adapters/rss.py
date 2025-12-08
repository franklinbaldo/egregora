"""RSS/Atom feed adapter for parsing web feeds into Entry objects.

Supports:
- Atom 1.0 (RFC 4287)
- RSS 2.0
"""

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import TracebackType

import httpx
from lxml import etree
from pydantic import ValidationError

from egregora_v3.core.types import Author, Entry, Link

logger = logging.getLogger(__name__)

# Atom namespace
ATOM_NS = "http://www.w3.org/2005/Atom"
ATOM_NSMAP = {None: ATOM_NS}


class RSSAdapter:
    """Parses RSS/Atom feeds into Entry objects.

    Supports Atom 1.0 and RSS 2.0 feeds from local files or HTTP(S) URLs.

    Usage:
        # Preferred: Use as context manager for deterministic cleanup
        with RSSAdapter() as adapter:
            entries = list(adapter.parse_url("https://example.com/feed.xml"))

        # Alternative: Manual cleanup
        adapter = RSSAdapter()
        try:
            entries = list(adapter.parse_url("https://example.com/feed.xml"))
        finally:
            adapter.close()
    """

    def __init__(self, timeout: float = 30.0) -> None:
        """Initialize RSS adapter.

        Args:
            timeout: HTTP request timeout in seconds (default: 30.0)

        """
        self.timeout = timeout
        self._http_client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "RSSAdapter":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager and close HTTP client."""
        self.close()

    def close(self) -> None:
        """Close HTTP client and release resources."""
        if hasattr(self, "_http_client"):
            self._http_client.close()

    def parse(self, source: Path) -> Iterator[Entry]:
        """Parse RSS/Atom feed from local file.

        Args:
            source: Path to local feed file

        Yields:
            Entry objects parsed from feed

        Raises:
            FileNotFoundError: If source file doesn't exist
            etree.XMLSyntaxError: If feed XML is malformed

        """
        if not source.exists():
            msg = f"Feed file not found: {source}"
            raise FileNotFoundError(msg)

        try:
            # Security note: Using lxml.etree for XML parsing. While lxml is more
            # resistant to XML bombs than stdlib xml.etree, parsing untrusted XML
            # always carries some risk. lxml disables DTDs and entity expansion by
            # default, making it safer for processing external feeds.
            # See: https://lxml.de/FAQ.html#how-do-i-use-lxml-safely-as-a-web-service-endpoint
            # We explicitly enforce safe parsing settings
            parser = etree.XMLParser(resolve_entities=False, no_network=True)
            tree = etree.parse(str(source), parser=parser)
            root = tree.getroot()
        except etree.XMLSyntaxError:
            logger.exception("Failed to parse XML from %s", source)
            raise

        yield from self._parse_feed_element(root)

    def parse_url(self, url: str) -> Iterator[Entry]:
        """Parse RSS/Atom feed from HTTP(S) URL.

        Args:
            url: HTTP(S) URL to feed

        Yields:
            Entry objects parsed from feed

        Raises:
            httpx.HTTPStatusError: If HTTP request fails (4xx, 5xx)
            httpx.ConnectError: If connection fails
            etree.XMLSyntaxError: If feed XML is malformed

        """
        response = self._http_client.get(url)
        response.raise_for_status()

        try:
            # Security note: Using lxml.etree for XML parsing. While lxml is more
            # resistant to XML bombs than stdlib xml.etree, parsing untrusted XML
            # always carries some risk. lxml disables DTDs and entity expansion by
            # default, making it safer for processing external feeds.
            # See: https://lxml.de/FAQ.html#how-do-i-use-lxml-safely-as-a-web-service-endpoint
            # We explicitly enforce safe parsing settings
            parser = etree.XMLParser(resolve_entities=False, no_network=True)
            root = etree.fromstring(response.content, parser=parser)
        except etree.XMLSyntaxError:
            logger.exception("Failed to parse XML from %s", url)
            raise

        yield from self._parse_feed_element(root)

    def _parse_feed_element(self, root: etree._Element) -> Iterator[Entry]:
        """Parse feed root element and yield entries.

        Args:
            root: XML root element

        Yields:
            Entry objects

        """
        # Detect feed type
        if root.tag == f"{{{ATOM_NS}}}feed":
            # Atom feed
            yield from self._parse_atom_feed(root)
        elif root.tag == "rss":
            # RSS 2.0 feed
            yield from self._parse_rss2_feed(root)
        else:
            logger.warning("Unknown feed type: %s", root.tag)

    # ========== Atom 1.0 Parsing ==========

    def _parse_atom_feed(self, feed_elem: etree._Element) -> Iterator[Entry]:
        """Parse Atom 1.0 feed.

        Args:
            feed_elem: Atom feed element

        Yields:
            Entry objects

        """
        for entry_elem in feed_elem.findall(f"{{{ATOM_NS}}}entry"):
            try:
                entry = self._parse_atom_entry(entry_elem)
                yield entry
            except (ValueError, ValidationError) as e:
                logger.warning("Skipping invalid Atom entry: %s", e)
                continue
            except (TypeError, AttributeError, IndexError) as e:
                logger.warning("Skipping Atom entry due to error: %s", e)
                continue

    def _parse_atom_entry(self, entry_elem: etree._Element) -> Entry:
        """Parse single Atom entry.

        Args:
            entry_elem: Atom entry element

        Returns:
            Entry object

        Raises:
            ValidationError: If required fields are missing or invalid

        """
        # Required fields (per RFC 4287)
        entry_id = self._get_text(entry_elem, f"{{{ATOM_NS}}}id")
        title = self._get_text(entry_elem, f"{{{ATOM_NS}}}title")
        updated_str = self._get_text(entry_elem, f"{{{ATOM_NS}}}updated")

        if not entry_id or not title or not updated_str:
            msg = "Atom entry missing required fields (id, title, or updated)"
            raise ValueError(msg)

        # Parse datetime
        updated = self._parse_iso8601(updated_str)

        # Optional fields
        content = self._get_atom_content(entry_elem)
        summary = self._get_text(entry_elem, f"{{{ATOM_NS}}}summary")

        # Use content if available, otherwise use summary
        entry_content = content or summary or ""

        # Authors
        authors = self._parse_atom_authors(entry_elem)

        # Links
        links = self._parse_atom_links(entry_elem)

        # Create Entry
        return Entry(
            id=entry_id,
            title=title,
            updated=updated,
            content=entry_content,
            authors=authors,
            links=links,
        )

    def _get_atom_content(self, entry_elem: etree._Element) -> str | None:
        """Extract content from Atom entry, handling type attribute.

        Args:
            entry_elem: Atom entry element

        Returns:
            Content text or None

        """
        content_elem = entry_elem.find(f"{{{ATOM_NS}}}content")
        if content_elem is None:
            return None

        # Handle different content types
        content_type = content_elem.get("type", "text")

        if content_type in ("text", "html"):
            # Return text content
            return content_elem.text or ""
        if content_type == "xhtml":
            # Serialize XHTML content
            return etree.tostring(content_elem, encoding="unicode", method="html")

        # Other types (e.g., base64) - just return text
        return content_elem.text or ""

    def _parse_atom_authors(self, entry_elem: etree._Element) -> list[Author]:
        """Parse authors from Atom entry.

        Args:
            entry_elem: Atom entry element

        Returns:
            List of Author objects

        """
        authors = []
        for author_elem in entry_elem.findall(f"{{{ATOM_NS}}}author"):
            name = self._get_text(author_elem, f"{{{ATOM_NS}}}name")
            email = self._get_text(author_elem, f"{{{ATOM_NS}}}email")
            uri = self._get_text(author_elem, f"{{{ATOM_NS}}}uri")

            if name:
                authors.append(Author(name=name, email=email, uri=uri))

        return authors

    def _parse_atom_links(self, entry_elem: etree._Element) -> list[Link]:
        """Parse links from Atom entry.

        Args:
            entry_elem: Atom entry element

        Returns:
            List of Link objects

        """
        links = []
        for link_elem in entry_elem.findall(f"{{{ATOM_NS}}}link"):
            href = link_elem.get("href")
            if not href:
                continue

            rel = link_elem.get("rel", "alternate")
            type_ = link_elem.get("type")
            length_str = link_elem.get("length")

            length = int(length_str) if length_str else None

            links.append(Link(href=href, rel=rel, type=type_, length=length))

        return links

    # ========== RSS 2.0 Parsing ==========

    def _parse_rss2_feed(self, rss_elem: etree._Element) -> Iterator[Entry]:
        """Parse RSS 2.0 feed.

        Args:
            rss_elem: RSS root element

        Yields:
            Entry objects

        """
        channel = rss_elem.find("channel")
        if channel is None:
            logger.warning("RSS feed missing <channel> element")
            return

        for item_elem in channel.findall("item"):
            try:
                entry = self._parse_rss2_item(item_elem)
                yield entry
            except (ValueError, ValidationError) as e:
                logger.warning("Skipping invalid RSS item: %s", e)
                continue
            except (TypeError, AttributeError, IndexError) as e:
                logger.warning("Skipping RSS item due to error: %s", e)
                continue

    def _parse_rss2_item(self, item_elem: etree._Element) -> Entry:
        """Parse single RSS 2.0 item.

        Args:
            item_elem: RSS item element

        Returns:
            Entry object

        Raises:
            ValidationError: If required fields are missing

        """
        # Extract fields
        title = self._get_text(item_elem, "title")
        link = self._get_text(item_elem, "link")
        description = self._get_text(item_elem, "description")
        guid = self._get_text(item_elem, "guid")
        pub_date_str = self._get_text(item_elem, "pubDate")

        # ID: use guid if available, otherwise use link
        entry_id = guid or link

        if not entry_id or not title:
            msg = "RSS item missing required fields (title and guid/link)"
            raise ValueError(msg)

        # Parse pubDate (RFC 822 format)
        if pub_date_str:
            try:
                updated = parsedate_to_datetime(pub_date_str)
                # Ensure UTC
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=UTC)
                else:
                    updated = updated.astimezone(UTC)
            except (ValueError, TypeError, AttributeError):
                logger.warning("Failed to parse pubDate: %s", pub_date_str)
                updated = datetime.now(UTC)
        else:
            updated = datetime.now(UTC)

        # Content (from description)
        content = description or ""

        # Links
        links = []
        if link:
            links.append(Link(href=link, rel="alternate"))

        # Create Entry
        return Entry(
            id=entry_id,
            title=title,
            updated=updated,
            content=content,
            links=links,
        )

    # ========== Utility Methods ==========

    def _get_text(self, elem: etree._Element, tag: str) -> str | None:
        """Get text content of child element.

        Args:
            elem: Parent element
            tag: Child tag name

        Returns:
            Text content or None

        """
        child = elem.find(tag)
        if child is not None:
            return child.text
        return None

    def _parse_iso8601(self, dt_str: str) -> datetime:
        """Parse ISO 8601 datetime string.

        Args:
            dt_str: ISO 8601 datetime string

        Returns:
            Datetime object with UTC timezone

        Raises:
            ValueError: If parsing fails

        """
        # Python 3.11+ supports fromisoformat with 'Z'
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"

        dt = datetime.fromisoformat(dt_str)

        # Ensure UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        else:
            dt = dt.astimezone(UTC)

        return dt

