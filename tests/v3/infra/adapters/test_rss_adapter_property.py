"""Property-based tests for RSSAdapter using Hypothesis.

These tests generate random inputs to verify invariants and edge cases.
"""

import html
import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from egregora_v3.core.types import Entry
from egregora_v3.infra.adapters.rss import RSSAdapter

# Atom namespace
ATOM_NS = "http://www.w3.org/2005/Atom"


# ========== Hypothesis Strategies ==========


@st.composite
def atom_entry_xml(draw: st.DrawFn) -> str:
    """Generate valid Atom entry XML with random data using f-strings for performance."""
    entry_id = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])))
    title = draw(st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])))
    content = draw(st.text(max_size=500, alphabet=st.characters(blacklist_categories=["Cc", "Cs"])))
    updated = draw(st.datetimes()).isoformat() + "Z"

    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="{ATOM_NS}">
  <title>Test Feed</title>
  <link href="https://example.com"/>
  <updated>{updated}</updated>
  <entry>
    <id>{html.escape(entry_id)}</id>
    <title>{html.escape(title)}</title>
    <updated>{updated}</updated>
    <content>{html.escape(content)}</content>
  </entry>
</feed>
"""


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
    updated = "2025-01-01T00:00:00Z"
    atom_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="{ATOM_NS}">
  <title>Test Feed</title>
  <link href="https://example.com"/>
  <updated>{updated}</updated>
  <entry>
    <id>{html.escape(entry_id)}</id>
    <title>Test Title</title>
    <updated>{updated}</updated>
    <content>Test Content</content>
  </entry>
</feed>
"""

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
    updated = "2025-01-01T00:00:00Z"
    entries_xml = "".join(
        f"""
  <entry>
    <id>entry-{i}</id>
    <title>{html.escape(title)}</title>
    <updated>{updated}</updated>
    <content>Content {i}</content>
  </entry>
"""
        for i, title in enumerate(titles)
    )

    atom_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="{ATOM_NS}">
  <title>Test Feed</title>
  <link href="https://example.com"/>
  <updated>{updated}</updated>
{entries_xml}
</feed>
"""

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
    updated = f"{year}-06-15T12:00:00Z"
    atom_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="{ATOM_NS}">
  <title>Test Feed</title>
  <link href="https://example.com"/>
  <updated>{updated}</updated>
  <entry>
    <id>test-entry</id>
    <title>Test Title</title>
    <updated>{updated}</updated>
    <content>Test Content</content>
  </entry>
</feed>
"""

    # Parse
    adapter = RSSAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        feed_file = Path(tmpdir) / "test_feed.atom"
        feed_file.write_text(atom_xml)

        entries = list(adapter.parse(feed_file))

        # Invariant: all datetimes are UTC
        assert all(e.updated.tzinfo.tzname(None) == "UTC" for e in entries)
