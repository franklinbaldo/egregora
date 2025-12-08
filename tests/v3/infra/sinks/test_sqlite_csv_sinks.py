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
    cursor.execute("SELECT authors FROM documents WHERE title = 'First Post'")
    authors_json = cursor.fetchone()[0]
    conn.close()

    authors = json.loads(authors_json)
    assert len(authors) == 1
    assert authors[0]["name"] == "Alice"
    assert authors[0]["email"] == "alice@example.com"


# ========== CSVOutputSink Tests ==========


def test_csv_sink_creates_file(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that CSVOutputSink creates a CSV file."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    assert csv_file.exists()


def test_csv_sink_has_header(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that CSV file has header row."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

    assert fieldnames is not None
    assert "id" in fieldnames
    assert "title" in fieldnames
    assert "content" in fieldnames
    assert "published" in fieldnames


def test_csv_sink_stores_published_documents(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that only PUBLISHED documents are stored."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Only 2 published documents (not the draft)
    assert len(rows) == 2


def test_csv_sink_stores_correct_content(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that content is stored correctly."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Find "First Post"
    first_post = next((r for r in rows if r["title"] == "First Post"), None)
    assert first_post is not None
    assert "# First Post" in first_post["content"]
    assert first_post["type"] == "post"


def test_csv_sink_exports_authors_as_json(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that authors are exported as JSON string."""
    import json

    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    first_post = next((r for r in rows if r["title"] == "First Post"), None)
    authors_json = first_post["authors"]

    authors = json.loads(authors_json)
    assert len(authors) == 1
    assert authors[0]["name"] == "Alice"


def test_csv_sink_handles_unicode(tmp_path: Path) -> None:
    """Test that CSV sink handles unicode characters correctly."""
    csv_file = tmp_path / "unicode.csv"
    doc = Document.create(
        content="你好世界 (Hello World)",
        doc_type=DocumentType.POST,
        title="Unicode Title 🚀",
        status=DocumentStatus.PUBLISHED,
    )
    feed = documents_to_feed([doc], "urn:uuid:test", "Test")

    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(feed)

    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

    assert "你好世界" in row["content"]
    assert "🚀" in row["title"]


def test_csv_sink_handles_empty_feed(tmp_path: Path) -> None:
    """Test that CSV sink handles empty feed gracefully."""
    csv_file = tmp_path / "empty.csv"
    empty_feed = documents_to_feed([], "urn:uuid:empty", "Empty")

    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(empty_feed)

    # CSV should exist with header row only
    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 0


def test_csv_sink_handles_newlines_in_content(tmp_path: Path) -> None:
    """Test that newlines in content don't break CSV structure."""
    csv_file = tmp_path / "newlines.csv"
    content = "Line 1\nLine 2\r\nLine 3"
    doc = Document.create(
        content=content,
        doc_type=DocumentType.POST,
        title="Multiline",
        status=DocumentStatus.PUBLISHED,
    )
    feed = documents_to_feed([doc], "urn:uuid:test", "Test")

    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(feed)

    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

    assert row["content"] == content


def test_csv_sink_handles_quotes_in_content(tmp_path: Path) -> None:
    """Test that quotes in content are escaped correctly."""
    csv_file = tmp_path / "quotes.csv"
    content = 'This has "quotes" inside.'
    doc = Document.create(
        content=content,
        doc_type=DocumentType.POST,
        title="Quotes",
        status=DocumentStatus.PUBLISHED,
    )
    feed = documents_to_feed([doc], "urn:uuid:test", "Test")

    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(feed)

    # Read back and verify
    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

    assert '"quotes"' in row["content"]


def test_csv_sink_includes_dates(sample_feed: Feed, tmp_path: Path) -> None:
    """Test that dates are included in CSV."""
    csv_file = tmp_path / "feed.csv"
    sink = CSVOutputSink(csv_path=csv_file)

    sink.publish(sample_feed)

    with csv_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)

    assert "published" in reader.fieldnames or "updated" in reader.fieldnames
    assert row["published"].startswith("2025-12-05")


# ========== Property-Based Tests (Hypothesis) ==========


@settings(max_examples=10)
@given(num_docs=st.integers(min_value=0, max_value=20))
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
    feed = documents_to_feed(docs, "urn:uuid:test", "Test Feed")

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "feed.db"
        sink = SQLiteOutputSink(db_path=db_file)

        sink.publish(feed)

        # Verify count
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == num_docs


@settings(max_examples=10)
@given(num_docs=st.integers(min_value=0, max_value=20))
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
    feed = documents_to_feed(docs, "urn:uuid:test", "Test Feed")

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_file = Path(tmp_dir) / "feed.csv"
        sink = CSVOutputSink(csv_path=csv_file)

        sink.publish(feed)

        # Verify all documents in CSV
        with csv_file.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == num_docs
