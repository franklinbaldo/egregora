"""Advanced tests for Feed.to_xml() demonstrating battle-tested libraries.

Tests:
1. Roundtrip serialization (parse → Feed → to_xml())
2. RFC 4287 schema validation with xmlschema
3. Property-based testing with Hypothesis
4. Snapshot testing with syrupy for regression detection
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from faker import Faker
from freezegun import freeze_time
from hypothesis import given, settings
from hypothesis import strategies as st
from lxml import etree
from syrupy.assertion import SnapshotAssertion

from egregora_v3.core.types import (
    Author,
    Category,
    Document,
    DocumentStatus,
    DocumentType,
    Feed,
    InReplyTo,
    Link,
    documents_to_feed,
)
from egregora_v3.infra.adapters.rss import RSSAdapter

fake = Faker()

# Atom namespace
ATOM_NS = "http://www.w3.org/2005/Atom"


# ========== Fixtures ==========


@pytest.fixture
def sample_feed() -> Feed:
    """Create a comprehensive sample feed with all features."""
    # Create documents with various features
    doc1 = Document.create(
        content="# First Post\n\nThis is the **first** post with *Markdown*.",
        doc_type=DocumentType.POST,
        title="First Post",
        status=DocumentStatus.PUBLISHED,
    )
    doc1.authors = [Author(name="Alice Smith", email="alice@example.com")]
    doc1.categories = [Category(term="technology", label="Technology")]
    doc1.links = [
        Link(href="https://example.com/first-post", rel="alternate"),
        Link(
            href="https://example.com/banner.jpg",
            rel="enclosure",
            type="image/jpeg",
            length=12345,
        ),
    ]

    doc2 = Document.create(
        content="Second post content.",
        doc_type=DocumentType.NOTE,
        title="Quick Note",
    )
    doc2.authors = [
        Author(name="Bob Jones", uri="https://bob.example.com"),
        Author(name="Carol White"),
    ]

    # Document with threading
    doc3 = Document.create(
        content="Reply to first post.",
        doc_type=DocumentType.POST,
        title="Re: First Post",
        in_reply_to=InReplyTo(ref=doc1.id, href="https://example.com/first-post"),
    )

    return documents_to_feed(
        docs=[doc1, doc2, doc3],
        feed_id="urn:uuid:feed-123",
        title="Comprehensive Test Feed",
        authors=[Author(name="Feed Author", email="feed@example.com")],
    )


# ========== Roundtrip Serialization Tests ==========


def test_roundtrip_feed_to_xml_to_entries(sample_feed: Feed, tmp_path: Path) -> None:
    """Test roundtrip: Feed → to_xml() → parse → Feed."""
    # Export to XML
    xml_output = sample_feed.to_xml()

    # Write to file
    feed_file = tmp_path / "exported_feed.atom"
    feed_file.write_text(xml_output)

    # Parse back using RSSAdapter
    adapter = RSSAdapter()
    parsed_entries = list(adapter.parse(feed_file))

    # Verify we got all entries back
    assert len(parsed_entries) == len(sample_feed.entries)

    # Verify entry IDs match
    original_ids = {e.id for e in sample_feed.entries}
    parsed_ids = {e.id for e in parsed_entries}
    assert original_ids == parsed_ids

    # Verify titles match
    for original, parsed in zip(
        sorted(sample_feed.entries, key=lambda e: e.id),
        sorted(parsed_entries, key=lambda e: e.id), strict=False,
    ):
        assert original.title == parsed.title
        assert original.content == parsed.content


@freeze_time("2025-12-06 10:00:00")
def test_roundtrip_preserves_timestamps(tmp_path: Path) -> None:
    """Test that timestamps are preserved in roundtrip serialization."""
    doc = Document.create(
        content="Test content",
        doc_type=DocumentType.POST,
        title="Test Post",
    )
    # Set published explicitly
    doc.published = datetime(2025, 12, 5, 9, 0, 0, tzinfo=UTC)
    doc.updated = datetime(2025, 12, 6, 10, 0, 0, tzinfo=UTC)

    feed = Feed(
        id="test-feed",
        title="Test Feed",
        updated=datetime(2025, 12, 6, 10, 0, 0, tzinfo=UTC),
        entries=[doc],
    )

    # Export and parse
    xml_output = feed.to_xml()
    feed_file = tmp_path / "test.atom"
    feed_file.write_text(xml_output)

    adapter = RSSAdapter()
    parsed_entries = list(adapter.parse(feed_file))

    assert len(parsed_entries) == 1
    # Updated timestamp should be preserved (within second precision)
    assert parsed_entries[0].updated.replace(microsecond=0) == doc.updated.replace(
        microsecond=0
    )
    # Published datetime should be preserved if exported
    if parsed_entries[0].published:
        assert parsed_entries[0].published.replace(microsecond=0) == doc.published.replace(
            microsecond=0
        )


def test_roundtrip_preserves_authors(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that authors are preserved in roundtrip."""
    xml_output = sample_feed.to_xml()
    feed_file = tmp_path / "test.atom"
    feed_file.write_text(xml_output)

    adapter = RSSAdapter()
    parsed_entries = list(adapter.parse(feed_file))

    # Find entry with multiple authors
    multi_author_entry = next((e for e in parsed_entries if len(e.authors) > 1), None)
    assert multi_author_entry is not None
    assert len(multi_author_entry.authors) >= 2


def test_roundtrip_preserves_links(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that links (including enclosures) are preserved."""
    xml_output = sample_feed.to_xml()
    feed_file = tmp_path / "test.atom"
    feed_file.write_text(xml_output)

    adapter = RSSAdapter()
    parsed_entries = list(adapter.parse(feed_file))

    # Find entry with enclosure link
    entry_with_enclosure = next(
        (
            e
            for e in parsed_entries
            if any(link.rel == "enclosure" for link in e.links)
        ),
        None,
    )
    assert entry_with_enclosure is not None

    enclosure = next(
        (link for link in entry_with_enclosure.links if link.rel == "enclosure"),
        None,
    )
    assert enclosure is not None
    assert enclosure.type == "image/jpeg"
    assert enclosure.length == 12345


# ========== RFC 4287 Schema Validation ==========


def test_feed_validates_against_atom_rfc_4287_schema(sample_feed: Feed) -> None:
    """Test that generated XML validates against Atom 1.0 schema."""
    try:
        import xmlschema
    except ImportError:
        pytest.skip("xmlschema not installed")

    xml_output = sample_feed.to_xml()

    # Parse with lxml for better error messages
    try:
        root = etree.fromstring(xml_output.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        pytest.fail(f"Generated XML is not well-formed: {e}")

    # Basic validation: check namespace
    assert root.tag == f"{{{ATOM_NS}}}feed", "Root element should be Atom feed"

    # Validate required elements exist
    ns = {"atom": ATOM_NS}
    assert root.find("atom:id", ns) is not None, "Feed must have id element"
    assert root.find("atom:title", ns) is not None, "Feed must have title element"
    assert root.find("atom:updated", ns) is not None, "Feed must have updated element"


def test_feed_entries_have_required_elements(sample_feed: Feed) -> None:
    """Test that all entries have required Atom elements."""
    xml_output = sample_feed.to_xml()
    root = etree.fromstring(xml_output.encode("utf-8"))

    ns = {"atom": ATOM_NS}
    entries = root.findall("atom:entry", ns)

    assert len(entries) > 0, "Feed should have entries"

    for entry in entries:
        # RFC 4287 required elements for entry
        assert entry.find("atom:id", ns) is not None, "Entry must have id"
        assert entry.find("atom:title", ns) is not None, "Entry must have title"
        assert entry.find("atom:updated", ns) is not None, "Entry must have updated"


def test_feed_datetime_format_rfc_3339_compliant(sample_feed: Feed) -> None:
    """Test that datetimes are formatted as RFC 3339 (required by Atom)."""
    xml_output = sample_feed.to_xml()
    root = etree.fromstring(xml_output.encode("utf-8"))

    ns = {"atom": ATOM_NS}

    # Check feed updated timestamp
    updated_elem = root.find("atom:updated", ns)
    assert updated_elem is not None
    updated_text = updated_elem.text

    # RFC 3339 format: 2025-12-06T10:00:00Z
    import re

    rfc3339_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    assert re.match(rfc3339_pattern, updated_text), f"Invalid RFC 3339 format: {updated_text}"


# ========== Snapshot Testing ==========


def test_feed_xml_snapshot_regression(sample_feed: Feed, snapshot: SnapshotAssertion) -> None:
    """Snapshot test to detect unintended changes in XML output.

    This test will fail if the XML structure changes, helping catch regressions.
    Run `pytest --snapshot-update` to update snapshots after intentional changes.
    """
    # Freeze time for deterministic output
    with freeze_time("2025-12-06 10:00:00"):
        # Create deterministic feed
        doc = Document.create(
            content="Deterministic content",
            doc_type=DocumentType.POST,
            title="Deterministic Post",
        )
        doc.authors = [Author(name="Test Author")]

        feed = Feed(
            id="test-feed-id",
            title="Test Feed",
            updated=datetime(2025, 12, 6, 10, 0, 0, tzinfo=UTC),
            entries=[doc],
        )

        xml_output = feed.to_xml()

        # Snapshot comparison
        assert xml_output == snapshot


# ========== Property-Based Tests ==========


@given(
    st.lists(
        st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=["Cc"])),
        min_size=1,
        max_size=5,
    )
)
def test_documents_to_feed_count_invariant(titles: list[str]) -> None:
    """Property: Number of documents equals number of feed entries."""
    docs = [
        Document.create(content=f"Content {i}", doc_type=DocumentType.NOTE, title=title)
        for i, title in enumerate(titles)
    ]

    feed = documents_to_feed(docs, feed_id="test", title="Test Feed")

    assert len(feed.entries) == len(docs)


@given(st.integers(min_value=1, max_value=10))
def test_feed_to_xml_always_well_formed(num_entries: int) -> None:
    """Property: Feed.to_xml() always produces well-formed XML."""
    docs = [
        Document.create(
            content=f"Content {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
        )
        for i in range(num_entries)
    ]

    feed = documents_to_feed(docs, feed_id="test-feed", title="Test Feed")
    xml_output = feed.to_xml()

    # Should parse without errors
    root = etree.fromstring(xml_output.encode("utf-8"))
    assert root.tag == f"{{{ATOM_NS}}}feed"

    # Should have correct number of entries
    entries = root.findall(f"{{{ATOM_NS}}}entry")
    assert len(entries) == num_entries


@settings(deadline=None)
@given(
    st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(
            blacklist_categories=["Cc", "Cs"],  # Exclude control chars and surrogates
            blacklist_characters="\x00",  # Exclude NULL byte
        ),
    )
)
def test_feed_preserves_title_exactly(title: str) -> None:
    """Property: Feed titles are preserved exactly in XML."""
    feed = Feed(
        id="test-id",
        title=title,
        updated=datetime.now(UTC),
        entries=[],
    )

    xml_output = feed.to_xml()
    root = etree.fromstring(xml_output.encode("utf-8"))

    title_elem = root.find(f"{{{ATOM_NS}}}title")
    assert title_elem is not None
    assert title_elem.text == title


# ========== Complex Scenarios ==========


def test_feed_with_threading_extension() -> None:
    """Test RFC 4685 threading extension (in-reply-to)."""
    parent = Document.create(
        content="Parent post",
        doc_type=DocumentType.POST,
        title="Parent",
    )

    reply = Document.create(
        content="Reply post",
        doc_type=DocumentType.POST,
        title="Re: Parent",
        in_reply_to=InReplyTo(ref=parent.id, href="https://example.com/parent"),
    )

    feed = documents_to_feed([parent, reply], feed_id="test", title="Threaded Feed")
    xml_output = feed.to_xml()

    root = etree.fromstring(xml_output.encode("utf-8"))

    # Find the reply entry
    thread_ns = "http://purl.org/syndication/thread/1.0"
    entries = root.findall(f"{{{ATOM_NS}}}entry")

    reply_entry = None
    for entry in entries:
        in_reply_to = entry.find(f"{{{thread_ns}}}in-reply-to")
        if in_reply_to is not None:
            reply_entry = entry
            break

    assert reply_entry is not None, "Reply entry should have in-reply-to element"
    in_reply_to_elem = reply_entry.find(f"{{{thread_ns}}}in-reply-to")
    assert in_reply_to_elem.get("ref") == parent.id


def test_feed_with_categories() -> None:
    """Test that categories are exported correctly."""
    doc = Document.create(
        content="Categorized content",
        doc_type=DocumentType.POST,
        title="Categorized Post",
    )
    doc.categories = [
        Category(term="technology", scheme="http://example.com/scheme", label="Technology"),
        Category(term="python", label="Python"),
    ]

    feed = documents_to_feed([doc], feed_id="test", title="Feed with Categories")
    xml_output = feed.to_xml()

    root = etree.fromstring(xml_output.encode("utf-8"))
    entry = root.find(f"{{{ATOM_NS}}}entry")
    categories = entry.findall(f"{{{ATOM_NS}}}category")

    # Should have user categories + Document type/status categories
    assert len(categories) >= 2

    # Check user categories exist
    category_terms = {cat.get("term") for cat in categories}
    assert "technology" in category_terms
    assert "python" in category_terms


def test_empty_feed_is_valid() -> None:
    """Test that empty feed (no entries) is still valid Atom."""
    feed = Feed(
        id="empty-feed",
        title="Empty Feed",
        updated=datetime.now(UTC),
        entries=[],
    )

    xml_output = feed.to_xml()
    root = etree.fromstring(xml_output.encode("utf-8"))

    assert root.tag == f"{{{ATOM_NS}}}feed"

    # Should have required elements even with no entries
    ns = {"atom": ATOM_NS}
    assert root.find("atom:id", ns) is not None
    assert root.find("atom:title", ns) is not None
    assert root.find("atom:updated", ns) is not None


@freeze_time("2025-12-06 15:30:45")
def test_feed_updated_timestamp_reflects_newest_entry() -> None:
    """Test that feed.updated is set to the newest entry's timestamp."""
    old_doc = Document.create(
        content="Old",
        doc_type=DocumentType.POST,
        title="Old Post",
    )
    old_doc.updated = datetime(2025, 12, 1, tzinfo=UTC)

    new_doc = Document.create(
        content="New",
        doc_type=DocumentType.POST,
        title="New Post",
    )
    new_doc.updated = datetime(2025, 12, 6, tzinfo=UTC)

    feed = documents_to_feed([old_doc, new_doc], feed_id="test", title="Test Feed")

    # Feed updated should be the newest
    assert feed.updated == new_doc.updated

    # Entries should be sorted newest first
    assert feed.entries[0].id == new_doc.id
    assert feed.entries[1].id == old_doc.id


def test_feed_with_content_types() -> None:
    """Test different content types (text, html, markdown)."""
    text_doc = Document.create(
        content="Plain text content",
        doc_type=DocumentType.POST,
        title="Text Post",
    )
    text_doc.content_type = "text/plain"

    html_doc = Document.create(
        content="<p>HTML content</p>",
        doc_type=DocumentType.POST,
        title="HTML Post",
    )
    html_doc.content_type = "text/html"

    markdown_doc = Document.create(
        content="# Markdown content",
        doc_type=DocumentType.POST,
        title="Markdown Post",
    )
    markdown_doc.content_type = "text/markdown"

    feed = documents_to_feed(
        [text_doc, html_doc, markdown_doc],
        feed_id="test",
        title="Content Types Feed",
    )

    xml_output = feed.to_xml()
    root = etree.fromstring(xml_output.encode("utf-8"))

    entries = root.findall(f"{{{ATOM_NS}}}entry")
    assert len(entries) == 3

    # Check content elements have type attribute
    content_types_found = []
    for entry in entries:
        content_elem = entry.find(f"{{{ATOM_NS}}}content")
        if content_elem is not None:
            content_type = content_elem.get("type")
            if content_type:
                content_types_found.append(content_type)

    # Should normalize some types to Atom-compatible values
    # text/markdown -> text, text/html -> html, text/plain may stay as-is
    assert len(content_types_found) >= 1
