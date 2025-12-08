"""Property-based tests for RSSAdapter using Hypothesis.

These tests generate random inputs to verify invariants and edge cases.
"""

import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from lxml import etree

from egregora_v3.core.types import Entry
from egregora_v3.infra.adapters.rss import RSSAdapter

# Atom namespace
ATOM_NS = "http://www.w3.org/2005/Atom"


# ========== Hypothesis Strategies ==========


@st.composite
def atom_entry_xml(draw: st.DrawFn) -> str:
    """Generate valid Atom entry XML with random data."""
    entry_id = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])))
    title = draw(st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])))
    content = draw(st.text(max_size=500, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])))

    # Generate ISO 8601 datetime
    year = draw(st.integers(min_value=2000, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))  # Safe for all months
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))

    updated = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"

    nsmap = {None: ATOM_NS}
    feed = etree.Element(f"{{{ATOM_NS}}}feed", nsmap=nsmap)

    feed_title = etree.SubElement(feed, f"{{{ATOM_NS}}}title")
    feed_title.text = "Test Feed"

    feed_link = etree.SubElement(feed, f"{{{ATOM_NS}}}link")
    feed_link.set("href", "https://example.com")

    feed_updated = etree.SubElement(feed, f"{{{ATOM_NS}}}updated")
    feed_updated.text = updated

    entry = etree.SubElement(feed, f"{{{ATOM_NS}}}entry")

    entry_id_elem = etree.SubElement(entry, f"{{{ATOM_NS}}}id")
    entry_id_elem.text = entry_id

    entry_title_elem = etree.SubElement(entry, f"{{{ATOM_NS}}}title")
    entry_title_elem.text = title

    entry_updated_elem = etree.SubElement(entry, f"{{{ATOM_NS}}}updated")
    entry_updated_elem.text = updated

    entry_content_elem = etree.SubElement(entry, f"{{{ATOM_NS}}}content")
    entry_content_elem.text = content

    return etree.tostring(feed, encoding="unicode")


# ========== Property-Based Tests ==========


@given(atom_entry_xml())
def test_parsing_atom_always_produces_valid_entry(atom_xml: str) -> None:
    """Property: Parsing any valid Atom feed always produces valid Entry objects."""
    adapter = RSSAdapter()

    # Write to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        feed_file = Path(tmpdir) / "test_feed.atom"
        feed_file.write_text(atom_xml)

        # Parse
        entries = list(adapter.parse(feed_file))

        # Invariants
        assert all(isinstance(e, Entry) for e in entries)
        assert all(e.id is not None for e in entries)
        assert all(e.title is not None for e in entries)
        assert all(isinstance(e.updated, datetime) for e in entries)


@given(st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])))
def test_atom_id_preservation(entry_id: str) -> None:
    """Property: Atom entry ID is always preserved exactly (for XML-compatible strings)."""
    # Create minimal valid Atom feed
    nsmap = {None: ATOM_NS}
    feed = etree.Element(f"{{{ATOM_NS}}}feed", nsmap=nsmap)

    feed_title = etree.SubElement(feed, f"{{{ATOM_NS}}}title")
    feed_title.text = "Test"

    feed_link = etree.SubElement(feed, f"{{{ATOM_NS}}}link")
    feed_link.set("href", "https://example.com")

    feed_updated = etree.SubElement(feed, f"{{{ATOM_NS}}}updated")
    feed_updated.text = "2025-01-01T00:00:00Z"

    entry = etree.SubElement(feed, f"{{{ATOM_NS}}}entry")

    entry_id_elem = etree.SubElement(entry, f"{{{ATOM_NS}}}id")
    entry_id_elem.text = entry_id

    entry_title_elem = etree.SubElement(entry, f"{{{ATOM_NS}}}title")
    entry_title_elem.text = "Test Title"

    entry_updated_elem = etree.SubElement(entry, f"{{{ATOM_NS}}}updated")
    entry_updated_elem.text = "2025-01-01T00:00:00Z"

    atom_xml = etree.tostring(feed, encoding="unicode")

    # Parse
    adapter = RSSAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        feed_file = Path(tmpdir) / "test_feed.atom"
        feed_file.write_text(atom_xml)

        entries = list(adapter.parse(feed_file))

        # Invariant: ID is preserved exactly
        assert len(entries) == 1
        assert entries[0].id == entry_id


@given(
    st.lists(
        st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])),
        min_size=0,
        max_size=10,
    )
)
def test_atom_feed_entry_count_matches(titles: list[str]) -> None:
    """Property: Number of parsed entries equals number of entries in feed."""
    nsmap = {None: ATOM_NS}
    feed = etree.Element(f"{{{ATOM_NS}}}feed", nsmap=nsmap)

    feed_title = etree.SubElement(feed, f"{{{ATOM_NS}}}title")
    feed_title.text = "Test Feed"

    feed_link = etree.SubElement(feed, f"{{{ATOM_NS}}}link")
    feed_link.set("href", "https://example.com")

    feed_updated = etree.SubElement(feed, f"{{{ATOM_NS}}}updated")
    feed_updated.text = "2025-01-01T00:00:00Z"

    # Create entries
    for i, title in enumerate(titles):
        entry = etree.SubElement(feed, f"{{{ATOM_NS}}}entry")

        entry_id = etree.SubElement(entry, f"{{{ATOM_NS}}}id")
        entry_id.text = f"entry-{i}"

        entry_title = etree.SubElement(entry, f"{{{ATOM_NS}}}title")
        entry_title.text = title

        entry_updated = etree.SubElement(entry, f"{{{ATOM_NS}}}updated")
        entry_updated.text = "2025-01-01T00:00:00Z"

        entry_content = etree.SubElement(entry, f"{{{ATOM_NS}}}content")
        entry_content.text = f"Content {i}"

    atom_xml = etree.tostring(feed, encoding="unicode")

    # Parse
    adapter = RSSAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        feed_file = Path(tmpdir) / "test_feed.atom"
        feed_file.write_text(atom_xml)

        entries = list(adapter.parse(feed_file))

        # Invariant: entry count matches
        assert len(entries) == len(titles)


@given(st.integers(min_value=2000, max_value=2030))
def test_atom_datetime_always_utc(year: int) -> None:
    """Property: All parsed datetimes are in UTC timezone."""
    nsmap = {None: ATOM_NS}
    feed = etree.Element(f"{{{ATOM_NS}}}feed", nsmap=nsmap)

    feed_title = etree.SubElement(feed, f"{{{ATOM_NS}}}title")
    feed_title.text = "Test"

    feed_link = etree.SubElement(feed, f"{{{ATOM_NS}}}link")
    feed_link.set("href", "https://example.com")

    feed_updated = etree.SubElement(feed, f"{{{ATOM_NS}}}updated")
    feed_updated.text = f"{year}-06-15T12:00:00Z"

    entry = etree.SubElement(feed, f"{{{ATOM_NS}}}entry")

    entry_id = etree.SubElement(entry, f"{{{ATOM_NS}}}id")
    entry_id.text = "test-entry"

    entry_title = etree.SubElement(entry, f"{{{ATOM_NS}}}title")
    entry_title.text = "Test"

    entry_updated = etree.SubElement(entry, f"{{{ATOM_NS}}}updated")
    entry_updated.text = f"{year}-06-15T12:00:00Z"

    atom_xml = etree.tostring(feed, encoding="unicode")

    # Parse
    adapter = RSSAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        feed_file = Path(tmpdir) / "test_feed.atom"
        feed_file.write_text(atom_xml)

        entries = list(adapter.parse(feed_file))

        # Invariant: all datetimes are UTC
        assert all(e.updated.tzinfo.tzname(None) == "UTC" for e in entries)
