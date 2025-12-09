"""TDD tests for RSSAdapter - written BEFORE implementation.

Following TDD Red-Green-Refactor cycle:
1. RED: Write failing tests
2. GREEN: Implement minimal code to pass
3. REFACTOR: Clean up implementation
"""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
from faker import Faker
from freezegun import freeze_time
from lxml import etree

from egregora_v3.core.types import Entry
from egregora_v3.infra.adapters.rss import RSSAdapter

fake = Faker()


# ========== Fixtures ==========


@pytest.fixture
def rss_adapter() -> RSSAdapter:
    """Create an RSSAdapter instance."""
    return RSSAdapter()


@pytest.fixture
def sample_atom_feed() -> str:
    """Generate a valid Atom feed XML using lxml."""
    atom_ns = "http://www.w3.org/2005/Atom"
    nsmap = {None: atom_ns}

    feed = etree.Element(f"{{{atom_ns}}}feed", nsmap=nsmap)

    # Feed metadata
    title = etree.SubElement(feed, f"{{{atom_ns}}}title")
    title.text = fake.catch_phrase()

    link = etree.SubElement(feed, f"{{{atom_ns}}}link")
    link.set("href", fake.url())

    updated = etree.SubElement(feed, f"{{{atom_ns}}}updated")
    updated.text = "2025-12-06T10:00:00Z"

    # Entry 1
    entry1 = etree.SubElement(feed, f"{{{atom_ns}}}entry")

    entry1_id = etree.SubElement(entry1, f"{{{atom_ns}}}id")
    entry1_id.text = f"urn:uuid:{fake.uuid4()}"

    entry1_title = etree.SubElement(entry1, f"{{{atom_ns}}}title")
    entry1_title.text = fake.sentence()

    entry1_updated = etree.SubElement(entry1, f"{{{atom_ns}}}updated")
    entry1_updated.text = "2025-12-05T09:00:00Z"

    entry1_content = etree.SubElement(entry1, f"{{{atom_ns}}}content")
    entry1_content.set("type", "html")
    entry1_content.text = fake.paragraph()

    entry1_author = etree.SubElement(entry1, f"{{{atom_ns}}}author")
    entry1_author_name = etree.SubElement(entry1_author, f"{{{atom_ns}}}name")
    entry1_author_name.text = fake.name()

    # Entry 2
    entry2 = etree.SubElement(feed, f"{{{atom_ns}}}entry")

    entry2_id = etree.SubElement(entry2, f"{{{atom_ns}}}id")
    entry2_id.text = f"urn:uuid:{fake.uuid4()}"

    entry2_title = etree.SubElement(entry2, f"{{{atom_ns}}}title")
    entry2_title.text = fake.sentence()

    entry2_updated = etree.SubElement(entry2, f"{{{atom_ns}}}updated")
    entry2_updated.text = "2025-12-04T08:00:00Z"

    entry2_content = etree.SubElement(entry2, f"{{{atom_ns}}}content")
    entry2_content.set("type", "text")
    entry2_content.text = fake.text()

    return etree.tostring(feed, encoding="unicode", pretty_print=True)


@pytest.fixture
def sample_rss2_feed() -> str:
    """Generate a valid RSS 2.0 feed XML."""
    rss = etree.Element("rss")
    rss.set("version", "2.0")

    channel = etree.SubElement(rss, "channel")

    title = etree.SubElement(channel, "title")
    title.text = fake.catch_phrase()

    link = etree.SubElement(channel, "link")
    link.text = fake.url()

    description = etree.SubElement(channel, "description")
    description.text = fake.text()

    # Item 1
    item1 = etree.SubElement(channel, "item")

    item1_title = etree.SubElement(item1, "title")
    item1_title.text = fake.sentence()

    item1_link = etree.SubElement(item1, "link")
    item1_link.text = fake.url()

    item1_description = etree.SubElement(item1, "description")
    item1_description.text = fake.paragraph()

    item1_pubdate = etree.SubElement(item1, "pubDate")
    item1_pubdate.text = "Mon, 05 Dec 2025 09:00:00 +0000"

    item1_guid = etree.SubElement(item1, "guid")
    item1_guid.text = fake.url()

    # Item 2
    item2 = etree.SubElement(channel, "item")

    item2_title = etree.SubElement(item2, "title")
    item2_title.text = fake.sentence()

    item2_link = etree.SubElement(item2, "link")
    item2_link.text = fake.url()

    item2_description = etree.SubElement(item2, "description")
    item2_description.text = fake.text()

    return etree.tostring(rss, encoding="unicode", pretty_print=True)


# ========== Test Atom Feed Parsing ==========


def test_parse_atom_feed_from_url(rss_adapter: RSSAdapter, sample_atom_feed: str) -> None:
    """Test parsing Atom feed from HTTP URL."""
    feed_url = "https://example.com/feed.atom"

    with respx.mock:
        respx.get(feed_url).mock(return_value=httpx.Response(200, text=sample_atom_feed))

        entries = list(rss_adapter.parse_url(feed_url))

    assert len(entries) == 2
    assert all(isinstance(e, Entry) for e in entries)
    assert entries[0].title is not None
    assert entries[0].content is not None
    assert entries[0].updated is not None


def test_parse_atom_feed_from_file(rss_adapter: RSSAdapter, sample_atom_feed: str, tmp_path: Path) -> None:
    """Test parsing Atom feed from local file."""
    feed_file = tmp_path / "feed.atom"
    feed_file.write_text(sample_atom_feed)

    entries = list(rss_adapter.parse(feed_file))

    assert len(entries) == 2
    assert all(isinstance(e, Entry) for e in entries)


def test_atom_entry_fields_mapped_correctly(
    rss_adapter: RSSAdapter, sample_atom_feed: str, tmp_path: Path
) -> None:
    """Test that Atom entry fields are correctly mapped to Entry model."""
    feed_file = tmp_path / "feed.atom"
    feed_file.write_text(sample_atom_feed)

    entries = list(rss_adapter.parse(feed_file))
    first_entry = entries[0]

    # Required fields
    assert first_entry.id.startswith("urn:uuid:")
    assert len(first_entry.title) > 0
    assert isinstance(first_entry.updated, datetime)
    assert first_entry.updated.tzinfo == UTC

    # Content
    assert first_entry.content is not None
    assert len(first_entry.content) > 0

    # Authors
    assert len(first_entry.authors) == 1
    assert first_entry.authors[0].name is not None


# ========== Test RSS 2.0 Feed Parsing ==========


def test_parse_rss2_feed_from_url(rss_adapter: RSSAdapter, sample_rss2_feed: str) -> None:
    """Test parsing RSS 2.0 feed from HTTP URL."""
    feed_url = "https://example.com/feed.rss"

    with respx.mock:
        respx.get(feed_url).mock(return_value=httpx.Response(200, text=sample_rss2_feed))

        entries = list(rss_adapter.parse_url(feed_url))

    assert len(entries) == 2
    assert all(isinstance(e, Entry) for e in entries)


def test_parse_rss2_feed_from_file(rss_adapter: RSSAdapter, sample_rss2_feed: str, tmp_path: Path) -> None:
    """Test parsing RSS 2.0 feed from local file."""
    feed_file = tmp_path / "feed.rss"
    feed_file.write_text(sample_rss2_feed)

    entries = list(rss_adapter.parse(feed_file))

    assert len(entries) == 2
    assert all(isinstance(e, Entry) for e in entries)


def test_rss2_item_fields_mapped_correctly(
    rss_adapter: RSSAdapter, sample_rss2_feed: str, tmp_path: Path
) -> None:
    """Test that RSS 2.0 item fields are correctly mapped to Entry model."""
    feed_file = tmp_path / "feed.rss"
    feed_file.write_text(sample_rss2_feed)

    entries = list(rss_adapter.parse(feed_file))
    first_entry = entries[0]

    # Required fields
    assert first_entry.id is not None  # Derived from guid or link
    assert len(first_entry.title) > 0
    assert isinstance(first_entry.updated, datetime)

    # Content (from description)
    assert first_entry.content is not None
    assert len(first_entry.content) > 0


# ========== Test Edge Cases ==========


def test_parse_empty_feed(rss_adapter: RSSAdapter, tmp_path: Path) -> None:
    """Test parsing feed with no entries."""
    empty_atom = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Empty Feed</title>
        <link href="https://example.com"/>
        <updated>2025-12-06T00:00:00Z</updated>
    </feed>"""

    feed_file = tmp_path / "empty.atom"
    feed_file.write_text(empty_atom)

    entries = list(rss_adapter.parse(feed_file))

    assert len(entries) == 0


def test_parse_malformed_xml_raises_error(rss_adapter: RSSAdapter, tmp_path: Path) -> None:
    """Test that malformed XML raises appropriate error."""
    malformed_xml = "<feed><entry>missing closing tags"

    feed_file = tmp_path / "malformed.xml"
    feed_file.write_text(malformed_xml)

    with pytest.raises(etree.XMLSyntaxError):
        list(rss_adapter.parse(feed_file))


def test_parse_missing_required_fields_skips_entry(rss_adapter: RSSAdapter, tmp_path: Path) -> None:
    """Test that entries missing required fields are skipped with warning."""
    incomplete_atom = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Test Feed</title>
        <link href="https://example.com"/>
        <updated>2025-12-06T00:00:00Z</updated>

        <entry>
            <!-- Missing id, title, updated -->
            <content>Some content</content>
        </entry>

        <entry>
            <id>valid-entry</id>
            <title>Valid Entry</title>
            <updated>2025-12-05T00:00:00Z</updated>
            <content>Valid content</content>
        </entry>
    </feed>"""

    feed_file = tmp_path / "incomplete.atom"
    feed_file.write_text(incomplete_atom)

    entries = list(rss_adapter.parse(feed_file))

    # Only the valid entry should be returned
    assert len(entries) == 1
    assert entries[0].id == "valid-entry"


# ========== Test HTTP Error Handling ==========


def test_parse_url_http_404_raises_error(rss_adapter: RSSAdapter) -> None:
    """Test that 404 response raises appropriate error."""
    feed_url = "https://example.com/not-found.atom"

    with respx.mock:
        respx.get(feed_url).mock(return_value=httpx.Response(404))

        with pytest.raises(httpx.HTTPStatusError):
            list(rss_adapter.parse_url(feed_url))


def test_parse_url_network_error_raises_error(rss_adapter: RSSAdapter) -> None:
    """Test that network errors are propagated."""
    feed_url = "https://example.com/feed.atom"

    with respx.mock:
        respx.get(feed_url).mock(side_effect=httpx.ConnectError("Connection failed"))

        with pytest.raises(httpx.ConnectError):
            list(rss_adapter.parse_url(feed_url))


# ========== Test Content Type Handling ==========


@freeze_time("2025-12-06 10:00:00")
def test_atom_content_type_html_preserved(rss_adapter: RSSAdapter, tmp_path: Path) -> None:
    """Test that HTML content type is preserved in Entry."""
    atom_with_html = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Test Feed</title>
        <link href="https://example.com"/>
        <updated>2025-12-06T10:00:00Z</updated>

        <entry>
            <id>html-entry</id>
            <title>HTML Entry</title>
            <updated>2025-12-06T10:00:00Z</updated>
            <content type="html">&lt;p&gt;HTML content&lt;/p&gt;</content>
        </entry>
    </feed>"""

    feed_file = tmp_path / "html.atom"
    feed_file.write_text(atom_with_html)

    entries = list(rss_adapter.parse(feed_file))

    assert len(entries) == 1
    # Content should contain the HTML (unescaped)
    assert "<p>" in entries[0].content


@freeze_time("2025-12-06 10:00:00")
def test_atom_multiple_authors(rss_adapter: RSSAdapter, tmp_path: Path) -> None:
    """Test parsing entry with multiple authors."""
    atom_multi_author = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Test Feed</title>
        <link href="https://example.com"/>
        <updated>2025-12-06T10:00:00Z</updated>

        <entry>
            <id>multi-author-entry</id>
            <title>Collaboration</title>
            <updated>2025-12-06T10:00:00Z</updated>
            <content>Joint work</content>
            <author>
                <name>Alice</name>
                <email>alice@example.com</email>
            </author>
            <author>
                <name>Bob</name>
            </author>
        </entry>
    </feed>"""

    feed_file = tmp_path / "multi-author.atom"
    feed_file.write_text(atom_multi_author)

    entries = list(rss_adapter.parse(feed_file))

    assert len(entries) == 1
    assert len(entries[0].authors) == 2
    assert entries[0].authors[0].name == "Alice"
    assert entries[0].authors[0].email == "alice@example.com"
    assert entries[0].authors[1].name == "Bob"


# ========== Test Link Handling ==========


@freeze_time("2025-12-06 10:00:00")
def test_atom_entry_links_parsed(rss_adapter: RSSAdapter, tmp_path: Path) -> None:
    """Test that entry links are parsed correctly."""
    atom_with_links = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>Test Feed</title>
        <link href="https://example.com"/>
        <updated>2025-12-06T10:00:00Z</updated>

        <entry>
            <id>linked-entry</id>
            <title>Entry with Links</title>
            <updated>2025-12-06T10:00:00Z</updated>
            <content>Content</content>
            <link rel="alternate" href="https://example.com/post"/>
            <link rel="enclosure" href="https://example.com/image.jpg" type="image/jpeg" length="12345"/>
        </entry>
    </feed>"""

    feed_file = tmp_path / "links.atom"
    feed_file.write_text(atom_with_links)

    entries = list(rss_adapter.parse(feed_file))

    assert len(entries) == 1
    assert len(entries[0].links) == 2

    # Check alternate link
    alternate = next((link for link in entries[0].links if link.rel == "alternate"), None)
    assert alternate is not None
    assert alternate.href == "https://example.com/post"

    # Check enclosure link
    enclosure = next((link for link in entries[0].links if link.rel == "enclosure"), None)
    assert enclosure is not None
    assert enclosure.href == "https://example.com/image.jpg"
    assert enclosure.type == "image/jpeg"
    assert enclosure.length == 12345


# ========== Test Iterator Protocol ==========


def test_parse_returns_iterator(rss_adapter: RSSAdapter, sample_atom_feed: str, tmp_path: Path) -> None:
    """Test that parse() returns an iterator, not a list."""
    feed_file = tmp_path / "feed.atom"
    feed_file.write_text(sample_atom_feed)

    result = rss_adapter.parse(feed_file)

    # Should be an iterator
    assert hasattr(result, "__iter__")
    assert hasattr(result, "__next__")

    # Can be consumed multiple times by converting to list
    entries1 = list(rss_adapter.parse(feed_file))
    entries2 = list(rss_adapter.parse(feed_file))

    assert len(entries1) == len(entries2) == 2
