"""TDD tests for SQLite and CSV Output Sinks - written BEFORE implementation.

Tests for:
1. SQLiteOutputSink - Exports Feed to SQLite database
2. CSVOutputSink - Exports Feed to CSV files

Following TDD Red-Green-Refactor cycle.
"""

import csv
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from faker import Faker
from hypothesis import given, settings
from hypothesis import strategies as st

from egregora_v3.core.types import (
    Author,
    Category,
    Document,
    DocumentStatus,
    DocumentType,
    Feed,
    documents_to_feed,
)
from egregora_v3.infra.sinks.csv import CSVOutputSink
from egregora_v3.infra.sinks.sqlite import SQLiteOutputSink

fake = Faker()


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
    doc1.categories = [Category(term="tech", label="Technology")]

    doc2 = Document.create(
        content="Second post content.",
        doc_type=DocumentType.POST,
        title="Second Post",
        status=DocumentStatus.PUBLISHED,
    )
    doc2.published = datetime(2025, 12, 6, tzinfo=UTC)
    doc2.authors = [Author(name="Bob")]

    draft = Document.create(
        content="Draft content",
        doc_type=DocumentType.POST,
        title="Draft Post",
        status=DocumentStatus.DRAFT,
    )

    return documents_to_feed(
        docs=[doc1, doc2, draft],
        feed_id="urn:uuid:test-feed",
        title="Test Feed",
        authors=[Author(name="Feed Author")],
    )


# ========== SQLiteOutputSink Tests ==========


def test_sqlite_sink_creates_database_file(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that SQLiteOutputSink creates a SQLite database file."""
    db_file = tmp_path / "feed.db"
    sink = SQLiteOutputSink(db_path=db_file)

    sink.publish(sample_feed)

    assert db_file.exists()


def test_sqlite_sink_creates_documents_table(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink creates a 'documents' table."""
    db_file = tmp_path / "feed.db"
    sink = SQLiteOutputSink(db_path=db_file)

    sink.publish(sample_feed)

    # Verify table exists
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
    )
    result = cursor.fetchone()
    conn.close()

    assert result is not None
    assert result[0] == "documents"


def test_sqlite_sink_stores_all_published_documents(
    sample_feed: Feed, tmp_path: Path
) -> None:
    """Test that only PUBLISHED documents are stored."""
    db_file = tmp_path / "feed.db"
    sink = SQLiteOutputSink(db_path=db_file)

    sink.publish(sample_feed)

    # Query documents
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents")
    count = cursor.fetchone()[0]
    conn.close()

    # Only 2 published documents (not the draft)
    assert count == 2


def test_sqlite_sink_stores_document_fields(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that document fields are stored correctly."""
    db_file = tmp_path / "feed.db"
    sink = SQLiteOutputSink(db_path=db_file)

    sink.publish(sample_feed)

    # Query first document
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, content, doc_type, status FROM documents ORDER BY title LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    _doc_id, title, content, doc_type, status = row

    assert title == "First Post"
    assert "# First Post" in content
    assert doc_type == "post"
    assert status == "published"


def test_sqlite_sink_stores_authors_as_json(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that authors are stored as JSON."""
    import json

    db_file = tmp_path / "feed.db"
    sink = SQLiteOutputSink(db_path=db_file)

    sink.publish(sample_feed)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT authors FROM documents WHERE title='First Post'")
    authors_json = cursor.fetchone()[0]
    conn.close()

    authors = json.loads(authors_json)
    assert len(authors) == 1
    assert authors[0]["name"] == "Alice"
    assert authors[0]["email"] == "alice@example.com"


def test_sqlite_sink_overwrites_existing_database(
    sample_feed: Feed, tmp_path: Path
) -> None:
    """Test that sink clears existing data before publishing."""
    db_file = tmp_path / "feed.db"

    # Create initial database with data
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE documents (id TEXT, title TEXT)")
    cursor.execute("INSERT INTO documents VALUES ('old-id', 'Old Title')")
    conn.commit()
    conn.close()

    sink = SQLiteOutputSink(db_path=db_file)
    sink.publish(sample_feed)

    # Old data should be gone
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents WHERE title='Old Title'")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 0


def test_sqlite_sink_creates_parent_directories(
    sample_feed: Feed, tmp_path: Path
) -> None:
    """Test that sink creates parent directories if they don't exist."""
    db_file = tmp_path / "deeply" / "nested" / "directory" / "feed.db"

    sink = SQLiteOutputSink(db_path=db_file)
    sink.publish(sample_feed)

    assert db_file.exists()
    assert db_file.parent.exists()


def test_sqlite_sink_with_empty_feed(tmp_path: Path) -> None:
    """Test that sink handles empty feed (no entries)."""
    empty_feed = Feed(
        id="empty-feed",
        title="Empty Feed",
        updated=datetime.now(UTC),
        entries=[],
    )

    db_file = tmp_path / "empty.db"
    sink = SQLiteOutputSink(db_path=db_file)

    sink.publish(empty_feed)

    # Database should exist with empty table
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 0


def test_sqlite_sink_handles_unicode_content(tmp_path: Path) -> None:
    """Test that sink handles Unicode characters correctly."""
    doc = Document.create(
        content="Unicode content: 你好世界 🎉 Olá",
        doc_type=DocumentType.POST,
        title="Unicode Test",
        status=DocumentStatus.PUBLISHED,
    )

    feed = documents_to_feed([doc], feed_id="test", title="Test")

    db_file = tmp_path / "unicode.db"
    sink = SQLiteOutputSink(db_path=db_file)

    sink.publish(feed)

    # Verify Unicode preserved
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM documents")
    content = cursor.fetchone()[0]
    conn.close()

    assert "你好世界" in content
    assert "🎉" in content
    assert "Olá" in content


def test_sqlite_sink_includes_timestamps(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that published and updated timestamps are stored."""
    db_file = tmp_path / "feed.db"
    sink = SQLiteOutputSink(db_path=db_file)

    sink.publish(sample_feed)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT published, updated FROM documents WHERE title='First Post'"
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    published, updated = row
    assert published is not None
    assert updated is not None


# ========== CSVOutputSink Tests ==========


def test_csv_sink_creates_csv_file(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that CSVOutputSink creates a CSV file."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    assert csv_file.exists()


def test_csv_sink_has_header_row(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that CSV file has header row."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

    assert fieldnames is not None
    assert "id" in fieldnames
    assert "title" in fieldnames
    assert "content" in fieldnames
    assert "doc_type" in fieldnames
    assert "status" in fieldnames


def test_csv_sink_exports_only_published_documents(
    sample_feed: Feed, tmp_path: Path
) -> None:
    """Test that only PUBLISHED documents are exported."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Only 2 published documents (not the draft)
    assert len(rows) == 2


def test_csv_sink_preserves_document_data(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that document data is preserved in CSV."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Find "First Post"
    first_post = next((r for r in rows if r["title"] == "First Post"), None)
    assert first_post is not None
    assert first_post["doc_type"] == "post"
    assert first_post["status"] == "published"
    assert "# First Post" in first_post["content"]


def test_csv_sink_exports_authors_as_json(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that authors are exported as JSON string."""
    import json

    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    first_post = next((r for r in rows if r["title"] == "First Post"), None)
    authors = json.loads(first_post["authors"])

    assert len(authors) == 1
    assert authors[0]["name"] == "Alice"


def test_csv_sink_overwrites_existing_file(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink overwrites existing CSV file."""
    csv_file = tmp_path / "feed.csv"

    # Create initial file
    csv_file.write_text("old,content\n1,2\n")

    sink = CSVOutputSink(csv_path=csv_file)
    sink.publish(sample_feed)

    # Should be replaced with new CSV
    content = csv_file.read_text()
    assert "old,content" not in content
    assert "First Post" in content


def test_csv_sink_creates_parent_directories(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that sink creates parent directories if they don't exist."""
    csv_file = tmp_path / "deeply" / "nested" / "directory" / "feed.csv"

    sink = CSVOutputSink(csv_path=csv_file)
    sink.publish(sample_feed)

    assert csv_file.exists()
    assert csv_file.parent.exists()


def test_csv_sink_with_empty_feed(tmp_path: Path) -> None:
    """Test that sink handles empty feed (no entries)."""
    empty_feed = Feed(
        id="empty-feed",
        title="Empty Feed",
        updated=datetime.now(UTC),
        entries=[],
    )

    csv_file = tmp_path / "empty.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(empty_feed)

    # CSV should exist with header row only
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 0


def test_csv_sink_handles_unicode_content(tmp_path: Path) -> None:
    """Test that sink handles Unicode characters correctly."""
    doc = Document.create(
        content="Unicode content: 你好世界 🎉 Olá",
        doc_type=DocumentType.POST,
        title="Unicode Test",
        status=DocumentStatus.PUBLISHED,
    )

    feed = documents_to_feed([doc], feed_id="test", title="Test")

    csv_file = tmp_path / "unicode.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(feed)

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

    assert "你好世界" in row["content"]
    assert "🎉" in row["content"]
    assert "Olá" in row["content"]


def test_csv_sink_handles_commas_and_quotes_in_content(tmp_path: Path) -> None:
    """Test that CSV properly escapes commas and quotes."""
    doc = Document.create(
        content='Content with "quotes" and, commas, and newlines\nhere',
        doc_type=DocumentType.POST,
        title="Special Characters",
        status=DocumentStatus.PUBLISHED,
    )

    feed = documents_to_feed([doc], feed_id="test", title="Test")

    csv_file = tmp_path / "special.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(feed)

    # Read back and verify
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

    assert '"quotes"' in row["content"]
    assert ", commas," in row["content"]


def test_csv_sink_includes_timestamps(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that published and updated timestamps are included."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

    assert "published" in reader.fieldnames or "updated" in reader.fieldnames
    # At least one timestamp should be present
    assert row.get("published") or row.get("updated")


# ========== Property-Based Tests ==========


@settings(deadline=None)
@given(st.integers(min_value=1, max_value=20))
def test_sqlite_sink_handles_any_number_of_documents(num_docs: int) -> None:
    """Property: SQLiteOutputSink handles any number of documents."""
    import tempfile

    docs = [
        Document.create(
            content=f"Content {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
            status=DocumentStatus.PUBLISHED,
        )
        for i in range(num_docs)
    ]

    feed = documents_to_feed(docs, feed_id="test", title="Test Feed")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / f"feed_{num_docs}.db"
        sink = SQLiteOutputSink(db_path=db_file)

        sink.publish(feed)

        # Verify all documents in database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == num_docs


@settings(deadline=None)
@given(st.integers(min_value=1, max_value=20))
def test_csv_sink_handles_any_number_of_documents(num_docs: int) -> None:
    """Property: CSVOutputSink handles any number of documents."""
    import tempfile

    docs = [
        Document.create(
            content=f"Content {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
            status=DocumentStatus.PUBLISHED,
        )
        for i in range(num_docs)
    ]

    feed = documents_to_feed(docs, feed_id="test", title="Test Feed")

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / f"feed_{num_docs}.csv"
        sink = CSVOutputSink(csv_path=csv_file)

        sink.publish(feed)

        # Verify all documents in CSV
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == num_docs
