import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from egregora_v3.core.types import (
    Category,
    Document,
    DocumentStatus,
    DocumentType,
    Feed,
    Link,
    Author,
)
from egregora_v3.infra.sinks.sqlite import SQLiteOutputSink


@pytest.fixture
def sample_feed() -> Feed:
    """Provides a sample Feed with one published document."""
    doc = Document(
        id="test-doc-1",
        title="Test Document",
        content="This is the content.",
        summary="A summary.",
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
        published=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        updated=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        authors=[Author(name="Author 1", email="author1@example.com")],
        categories=[Category(term="testing")],
        links=[Link(href="http://example.com/link")],
    )
    return Feed(id="test-feed", title="Test Feed", updated=doc.updated, entries=[doc])


def test_publish_creates_database_and_writes_document(
    tmp_path: Path, sample_feed: Feed
):
    """Verify that publishing a feed creates a SQLite DB with the correct data."""
    db_path = tmp_path / "output.db"
    sink = SQLiteOutputSink(db_path)

    # Act
    sink.publish(sample_feed)

    # Assert
    assert db_path.exists()

    # Verify content
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents WHERE id = ?", ("test-doc-1",))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    (
        id_val,
        title,
        content,
        summary,
        doc_type,
        status,
        published,
        updated,
        authors,
        categories,
        links,
    ) = row
    assert id_val == "test-doc-1"
    assert title == "Test Document"
    assert doc_type == "post"
    assert status == "published"
    assert published == "2023-01-01T12:00:00+00:00"
    assert updated == "2023-01-02T12:00:00+00:00"
    assert '"name": "Author 1"' in authors
    assert '"term": "testing"' in categories
    assert '"href": "http://example.com/link"' in links


def test_document_to_record_serializes_correctly(sample_feed: Feed):
    """Verify the new serialization method works as expected."""
    sink = SQLiteOutputSink(Path("dummy.db"))
    doc = sample_feed.entries[0]
    assert isinstance(doc, Document)

    record = sink._document_to_record(doc)

    assert isinstance(record, dict)
    assert record["id"] == "test-doc-1"
    assert record["title"] == "Test Document"
    assert record["doc_type"] == "post"
    assert record["status"] == "published"
    assert record["published"] == "2023-01-01T12:00:00+00:00"
    assert record["updated"] == "2023-01-02T12:00:00+00:00"
    assert json.loads(record["authors"]) == [
        {"name": "Author 1", "email": "author1@example.com", "uri": None}
    ]
    assert json.loads(record["categories"]) == [
        {"term": "testing", "scheme": None, "label": None}
    ]
    assert json.loads(record["links"]) == [
        {
            "href": "http://example.com/link",
            "rel": None,
            "type": None,
            "hreflang": None,
            "title": None,
            "length": None,
        }
    ]
