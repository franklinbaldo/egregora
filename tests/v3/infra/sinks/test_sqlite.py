import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from egregora_v3.core.types import (
    Author,
    Category,
    Document,
    DocumentStatus,
    DocumentType,
    Feed,
    Link,
)
from egregora_v3.infra.sinks.sqlite import SQLiteOutputSink, _document_to_record


@pytest.fixture
def published_doc() -> Document:
    """Provides a single published document."""
    return Document(
        id="published-doc-1",
        title="Published Document",
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


@pytest.fixture
def draft_doc() -> Document:
    """Provides a single draft document."""
    return Document(
        id="draft-doc-1",
        title="Draft Document",
        content="This is a draft.",
        doc_type=DocumentType.POST,
        status=DocumentStatus.DRAFT,
        updated=datetime(2023, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_feed(published_doc: Document) -> Feed:
    """Provides a sample Feed with one published document."""
    return Feed(
        id="test-feed",
        title="Test Feed",
        updated=published_doc.updated,
        entries=[published_doc],
    )


@pytest.fixture
def mixed_feed(published_doc: Document, draft_doc: Document) -> Feed:
    """Provides a sample Feed with both published and draft documents."""
    return Feed(
        id="mixed-feed",
        title="Mixed Feed",
        updated=draft_doc.updated,
        entries=[published_doc, draft_doc],
    )


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
    cursor.execute("SELECT * FROM documents WHERE id = ?", ("published-doc-1",))
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
    assert id_val == "published-doc-1"
    assert title == "Published Document"
    assert doc_type == "post"
    assert status == "published"
    assert published == "2023-01-01T12:00:00Z"
    assert updated == "2023-01-02T12:00:00Z"
    assert '"name": "Author 1"' in authors
    assert '"term": "testing"' in categories
    assert '"href": "http://example.com/link"' in links


def test_publish_writes_only_published_documents(tmp_path: Path, mixed_feed: Feed):
    """
    Locking Test: Verify that the sink correctly filters for published documents.
    """
    db_path = tmp_path / "output.db"
    sink = SQLiteOutputSink(db_path)

    # Act
    sink.publish(mixed_feed)

    # Assert
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check that the published document is there
    cursor.execute("SELECT id FROM documents WHERE id = ?", ("published-doc-1",))
    assert cursor.fetchone() is not None

    # Check that the draft document is NOT there
    cursor.execute("SELECT id FROM documents WHERE id = ?", ("draft-doc-1",))
    assert cursor.fetchone() is None

    # Check that there is only one row in total
    cursor.execute("SELECT COUNT(*) FROM documents")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 1


def test_document_to_record_serializes_correctly(sample_feed: Feed):
    """Verify the new serialization method works as expected."""
    doc = sample_feed.entries[0]
    assert isinstance(doc, Document)

    record = _document_to_record(doc)

    assert isinstance(record, dict)
    assert record["id"] == "published-doc-1"
    assert record["title"] == "Published Document"
    assert record["doc_type"] == "post"
    assert record["status"] == "published"
    assert record["published"] == "2023-01-01T12:00:00Z"
    assert record["updated"] == "2023-01-02T12:00:00Z"
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
