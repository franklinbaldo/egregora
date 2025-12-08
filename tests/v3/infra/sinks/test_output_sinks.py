"""TDD tests for Output Sinks - written BEFORE implementation.

Tests for:
1. AtomXMLOutputSink - Publishes Feed as Atom XML file
2. MkDocsOutputSink - Publishes Feed as MkDocs markdown files

Following TDD Red-Green-Refactor cycle.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from faker import Faker
from freezegun import freeze_time
from hypothesis import given
from hypothesis import strategies as st
from lxml import etree

from egregora_v3.core.types import (
    Author,
    Document,
    DocumentStatus,
    DocumentType,
    Feed,
    documents_to_feed,
)
from egregora_v3.infra.adapters.rss import RSSAdapter
from egregora_v3.infra.sinks.atom_xml import AtomXMLOutputSink
from egregora_v3.infra.sinks.mkdocs import MkDocsOutputSink

fake = Faker()

ATOM_NS = "http://www.w3.org/2005/Atom"


# ========== Fixtures ==========


@pytest.fixture
def sample_feed() -> Feed:
    """Create a sample feed for testing."""
    doc1 = Document.create(
        content="# First Post\n\nThis is content.",
        doc_type=DocumentType.POST,
        title="First Post",
        status=DocumentStatus.PUBLISHED,
    )
    doc1.authors = [Author(name="Alice", email="alice@example.com")]
    doc1.published = datetime(2025, 12, 5, tzinfo=UTC)

    doc2 = Document.create(
        content="Second post content.",
        doc_type=DocumentType.POST,
        title="Second Post",
        status=DocumentStatus.PUBLISHED,
    )
    doc2.published = datetime(2025, 12, 6, tzinfo=UTC)

    return documents_to_feed(
        docs=[doc1, doc2],
        feed_id="urn:uuid:test-feed",
        title="Test Feed",
        authors=[Author(name="Feed Author")],
    )


# ========== AtomXMLOutputSink Tests ==========


def test_atom_xml_sink_creates_file(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that AtomXMLOutputSink creates an Atom XML file."""
    output_file = tmp_path / "feed.atom"
    sink = AtomXMLOutputSink(output_path=output_file)

    sink.publish(sample_feed)

    assert output_file.exists()
    assert output_file.read_text().startswith('<?xml version')


def test_atom_xml_sink_produces_valid_xml(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that output is valid, parseable XML."""
    output_file = tmp_path / "feed.atom"
    sink = AtomXMLOutputSink(output_path=output_file)

    sink.publish(sample_feed)

    # Should parse without errors
    xml_content = output_file.read_text()
    root = etree.fromstring(xml_content.encode("utf-8"))
    assert root.tag == f"{{{ATOM_NS}}}feed"


def test_atom_xml_sink_preserves_entries(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that all entries are preserved in output."""
    output_file = tmp_path / "feed.atom"
    sink = AtomXMLOutputSink(output_path=output_file)

    sink.publish(sample_feed)

    xml_content = output_file.read_text()
    root = etree.fromstring(xml_content.encode("utf-8"))

    entries = root.findall(f"{{{ATOM_NS}}}entry")
    assert len(entries) == len(sample_feed.entries)


def test_atom_xml_sink_roundtrip_with_rss_adapter(
    sample_feed: Feed, tmp_path: Path
) -> None:
    """Test full roundtrip: Feed → AtomXMLOutputSink → RSSAdapter → Feed."""
    output_file = tmp_path / "feed.atom"
    sink = AtomXMLOutputSink(output_path=output_file)

    # Publish feed
    sink.publish(sample_feed)

    # Parse back using RSSAdapter
    adapter = RSSAdapter()
    parsed_entries = list(adapter.parse(output_file))

    # Verify all entries preserved
    assert len(parsed_entries) == len(sample_feed.entries)

    # Verify IDs match
    original_ids = {e.id for e in sample_feed.entries}
    parsed_ids = {e.id for e in parsed_entries}
    assert original_ids == parsed_ids


def test_atom_xml_sink_overwrites_existing_file(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink overwrites existing file."""
    output_file = tmp_path / "feed.atom"

    # Create initial file
    output_file.write_text("old content")

    sink = AtomXMLOutputSink(output_path=output_file)
    sink.publish(sample_feed)

    # Should be replaced with valid XML
    xml_content = output_file.read_text()
    assert xml_content.startswith('<?xml version')
    assert "old content" not in xml_content


def test_atom_xml_sink_creates_parent_directories(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink creates parent directories if they don't exist."""
    output_file = tmp_path / "deeply" / "nested" / "directory" / "feed.atom"

    sink = AtomXMLOutputSink(output_path=output_file)
    sink.publish(sample_feed)

    assert output_file.exists()
    assert output_file.parent.exists()


@freeze_time("2025-12-06 15:30:00")
def test_atom_xml_sink_uses_feed_to_xml(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink uses Feed.to_xml() internally."""
    output_file = tmp_path / "feed.atom"
    sink = AtomXMLOutputSink(output_path=output_file)

    sink.publish(sample_feed)

    # Output should match Feed.to_xml()
    expected_xml = sample_feed.to_xml()
    actual_xml = output_file.read_text()

    assert actual_xml == expected_xml


def test_atom_xml_sink_with_empty_feed(tmp_path: Path) -> None:
    """Test that sink handles empty feed (no entries)."""
    empty_feed = Feed(
        id="empty-feed",
        title="Empty Feed",
        updated=datetime.now(UTC),
        entries=[],
    )

    output_file = tmp_path / "empty.atom"
    sink = AtomXMLOutputSink(output_path=output_file)

    sink.publish(empty_feed)

    assert output_file.exists()

    # Should still be valid Atom XML
    xml_content = output_file.read_text()
    root = etree.fromstring(xml_content.encode("utf-8"))
    assert root.tag == f"{{{ATOM_NS}}}feed"


# ========== MkDocsOutputSink Tests ==========


def test_mkdocs_sink_creates_markdown_files(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that MkDocsOutputSink creates markdown files for each document."""
    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(sample_feed)

    # Should create files for published documents + index.md
    markdown_files = list(output_dir.glob("**/*.md"))
    # 2 posts + 1 index = 3 total
    assert len(markdown_files) == 3


def test_mkdocs_sink_uses_slug_for_filename(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that markdown files are named using document slugs."""
    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(sample_feed)

    # Check that files exist with slugified names
    assert (output_dir / "first-post.md").exists()
    assert (output_dir / "second-post.md").exists()


def test_mkdocs_sink_includes_frontmatter(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that markdown files include YAML frontmatter."""
    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(sample_feed)

    content = (output_dir / "first-post.md").read_text()

    # Should start with YAML frontmatter
    assert content.startswith("---\n")
    assert "title:" in content
    assert "date:" in content


def test_mkdocs_sink_preserves_markdown_content(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that markdown content is preserved in output files."""
    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(sample_feed)

    content = (output_dir / "first-post.md").read_text()

    # Should contain the original markdown content
    assert "# First Post" in content
    assert "This is content." in content


def test_mkdocs_sink_creates_index_page(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink creates an index.md page listing all posts."""
    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(sample_feed)

    index_file = output_dir / "index.md"
    assert index_file.exists()

    index_content = index_file.read_text()
    assert "First Post" in index_content
    assert "Second Post" in index_content


def test_mkdocs_sink_respects_document_status(tmp_path: Path) -> None:
    """Test that only PUBLISHED documents are exported."""
    draft = Document.create(
        content="Draft content",
        doc_type=DocumentType.POST,
        title="Draft Post",
        status=DocumentStatus.DRAFT,
    )

    published = Document.create(
        content="Published content",
        doc_type=DocumentType.POST,
        title="Published Post",
        status=DocumentStatus.PUBLISHED,
    )

    feed = documents_to_feed(
        [draft, published],
        feed_id="test",
        title="Mixed Status Feed",
    )

    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(feed)

    # Only published post should be exported
    assert (output_dir / "published-post.md").exists()
    assert not (output_dir / "draft-post.md").exists()


def test_mkdocs_sink_creates_parent_directories(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink creates output directory if it doesn't exist."""
    output_dir = tmp_path / "deeply" / "nested" / "docs"

    sink = MkDocsOutputSink(output_dir=output_dir)
    sink.publish(sample_feed)

    assert output_dir.exists()
    assert list(output_dir.glob("*.md"))  # Has markdown files


def test_mkdocs_sink_includes_author_in_frontmatter(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that author information is included in frontmatter."""
    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(sample_feed)

    content = (output_dir / "first-post.md").read_text()

    # Should include author metadata
    assert "authors:" in content or "author:" in content
    assert "Alice" in content


def test_mkdocs_sink_cleans_existing_files(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink removes old markdown files before publishing."""
    output_dir = tmp_path / "docs"
    output_dir.mkdir()

    # Create old file that shouldn't exist anymore
    old_file = output_dir / "old-post.md"
    old_file.write_text("old content")

    sink = MkDocsOutputSink(output_dir=output_dir)
    sink.publish(sample_feed)

    # Old file should be removed
    assert not old_file.exists()

    # New files should exist
    assert (output_dir / "first-post.md").exists()


# ========== Property-Based Tests ==========


@given(st.integers(min_value=1, max_value=20))
def test_atom_xml_sink_handles_any_number_of_entries(num_entries: int) -> None:
    """Property: AtomXMLOutputSink handles any number of entries."""
    import tempfile

    docs = [
        Document.create(
            content=f"Content {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
            status=DocumentStatus.PUBLISHED,
        )
        for i in range(num_entries)
    ]

    feed = documents_to_feed(docs, feed_id="test", title="Test Feed")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / f"feed_{num_entries}.atom"
        sink = AtomXMLOutputSink(output_path=output_file)

        sink.publish(feed)

        assert output_file.exists()

        # Verify all entries in output
        xml_content = output_file.read_text()
        root = etree.fromstring(xml_content.encode("utf-8"))
        entries = root.findall(f"{{{ATOM_NS}}}entry")
        assert len(entries) == num_entries


@given(st.integers(min_value=1, max_value=20))
def test_mkdocs_sink_creates_correct_number_of_files(num_entries: int) -> None:
    """Property: MkDocsOutputSink creates one file per published document."""
    import tempfile

    docs = [
        Document.create(
            content=f"Content {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
            status=DocumentStatus.PUBLISHED,
        )
        for i in range(num_entries)
    ]

    feed = documents_to_feed(docs, feed_id="test", title="Test Feed")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / f"docs_{num_entries}"
        sink = MkDocsOutputSink(output_dir=output_dir)

        sink.publish(feed)

        # Should have num_entries markdown files + 1 index.md
        markdown_files = list(output_dir.glob("*.md"))
        assert len(markdown_files) == num_entries + 1  # posts + index


# ========== Edge Cases ==========


def test_atom_xml_sink_handles_special_characters_in_content(tmp_path: Path) -> None:
    """Test that sink properly escapes XML special characters."""
    doc = Document.create(
        content="Content with <tags> & \"quotes\" and 'apostrophes'",
        doc_type=DocumentType.POST,
        title="Special Characters",
    )

    feed = documents_to_feed([doc], feed_id="test", title="Test")

    output_file = tmp_path / "feed.atom"
    sink = AtomXMLOutputSink(output_path=output_file)

    sink.publish(feed)

    # Should parse as valid XML
    xml_content = output_file.read_text()
    root = etree.fromstring(xml_content.encode("utf-8"))
    assert root is not None


def test_mkdocs_sink_handles_unicode_content(tmp_path: Path) -> None:
    """Test that sink handles Unicode characters correctly."""
    doc = Document.create(
        content="Unicode content: 你好世界 🎉 Olá",
        doc_type=DocumentType.POST,
        title="Unicode Test",
        status=DocumentStatus.PUBLISHED,
    )

    feed = documents_to_feed([doc], feed_id="test", title="Test")

    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(feed)

    content = (output_dir / "unicode-test.md").read_text()
    assert "你好世界" in content
    assert "🎉" in content
    assert "Olá" in content


def test_mkdocs_sink_handles_documents_without_slug(tmp_path: Path) -> None:
    """Test that sink handles documents that don't have semantic slugs."""
    # NOTE type doesn't use semantic slugs, uses UUID
    doc = Document.create(
        content="Note content",
        doc_type=DocumentType.NOTE,
        title="A Note",
        status=DocumentStatus.PUBLISHED,
    )

    feed = documents_to_feed([doc], feed_id="test", title="Test")

    output_dir = tmp_path / "docs"
    sink = MkDocsOutputSink(output_dir=output_dir)

    sink.publish(feed)

    # Should create file with slugified title or ID
    markdown_files = list(output_dir.glob("*.md"))
    # At least index.md + one file for the note
    assert len(markdown_files) >= 2
