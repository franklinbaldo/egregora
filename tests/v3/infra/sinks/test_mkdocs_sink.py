"""Tests for the MkDocsOutputSink."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import yaml

from egregora_v3.core.types import Author, Document, DocumentStatus, DocumentType, Feed, Category
from egregora_v3.infra.sinks.mkdocs import MkDocsOutputSink


def test_generate_frontmatter_single_author():
    """Test YAML frontmatter generation for a document with a single author."""
    doc = Document(
        id="test-doc",
        title="My Title",
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
        updated=datetime(2023, 10, 26, 12, 0, 0, tzinfo=timezone.utc),
        published=datetime(2023, 10, 26, 12, 0, 0, tzinfo=timezone.utc),
        authors=[Author(name="John Doe")],
        categories=[Category(term="testing"), Category(term="python")],
    )
    sink = MkDocsOutputSink(Path("dummy"))
    frontmatter_str = sink._generate_frontmatter(doc)

    # --- Assertions ---
    data = yaml.safe_load(frontmatter_str)

    assert data["title"] == "My Title"
    assert data["date"] == "2023-10-26"
    assert data["author"] == "John Doe"
    assert "authors" not in data # Should use 'author' for single author
    assert data["tags"] == ["testing", "python"]
    assert data["type"] == "post"
    assert data["status"] == "published"


def test_generate_frontmatter_multiple_authors():
    """Test YAML frontmatter generation for a document with multiple authors."""
    doc = Document(
        id="test-doc-multi",
        title="Another Title",
        doc_type=DocumentType.NOTE,
        status=DocumentStatus.DRAFT,
        updated=datetime(2023, 11, 1, 8, 0, 0, tzinfo=timezone.utc),
        published=datetime(2023, 11, 1, 8, 0, 0, tzinfo=timezone.utc),
        authors=[Author(name="Jane Doe"), Author(name="Peter Pan")],
    )
    sink = MkDocsOutputSink(Path("dummy"))
    frontmatter_str = sink._generate_frontmatter(doc)

    # --- Assertions ---
    data = yaml.safe_load(frontmatter_str)

    assert data["title"] == "Another Title"
    assert data["authors"] == ["Jane Doe", "Peter Pan"]
    assert "author" not in data # Should use 'authors' for multiple
    assert data["type"] == "note"
    assert data["status"] == "draft"


def test_write_index_generates_correct_markdown():
    """Locking test to ensure _write_index output remains consistent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        sink = MkDocsOutputSink(output_dir)

        # --- Test Data ---
        feed_author = Author(name="Feed Author")
        doc_author1 = Author(name="Doc Author One")
        doc_author2 = Author(name="Doc Author Two")

        feed = Feed(
            id="test-feed",
            title="My Test Blog",
            updated=datetime(2023, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
            authors=[feed_author],
        )

        doc1 = Document(
            id="post-one",
            title="First Post",
            doc_type=DocumentType.POST,
            status=DocumentStatus.PUBLISHED,
            updated=datetime(2023, 10, 26, 12, 0, 0, tzinfo=timezone.utc),
            published=datetime(2023, 10, 26, 12, 0, 0, tzinfo=timezone.utc),
            authors=[doc_author1],
            internal_metadata={"slug": "first-post"},
        )

        doc2 = Document(
            id="post-two",
            title="Second Post",
            doc_type=DocumentType.POST,
            status=DocumentStatus.PUBLISHED,
            updated=datetime(2023, 10, 27, 9, 0, 0, tzinfo=timezone.utc),
            published=datetime(2023, 10, 27, 9, 0, 0, tzinfo=timezone.utc),
            authors=[doc_author1, doc_author2],
            internal_metadata={"slug": "second-post"},
        )

        doc3_no_slug = Document(
            id="post-three-no-slug",
            title="Third Post (No Slug)",
            doc_type=DocumentType.POST,
            status=DocumentStatus.PUBLISHED,
            updated=datetime(2023, 10, 28, 9, 0, 0, tzinfo=timezone.utc),
        )

        published_docs = [doc1, doc2, doc3_no_slug]

        # --- Call the private method ---
        sink._write_index(feed, published_docs)

        # --- Assertions ---
        index_file = output_dir / "index.md"
        assert index_file.exists()

        content = index_file.read_text(encoding="utf-8")

        expected_content = """# My Test Blog

**Authors:** Feed Author

**Last Updated:** 2023-10-27 10:00:00

## Posts

- [Third Post (No Slug)](third-post-no-slug.md) - 2023-10-28

- [Second Post](second-post.md) - 2023-10-27
  *by Doc Author One, Doc Author Two*

- [First Post](first-post.md) - 2023-10-26
  *by Doc Author One*

"""
        assert content.strip() == expected_content.strip()
