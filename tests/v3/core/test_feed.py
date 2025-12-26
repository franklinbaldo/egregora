"""Tests for the Feed model and its factory methods."""
from datetime import datetime, timedelta

from egregora_v3.core.types import Author, Document, DocumentStatus, DocumentType, Feed


def test_from_documents_factory_creates_feed_with_correct_metadata():
    """Test that Feed.from_documents creates a feed with correct metadata."""
    docs = [
        Document(
            id="doc1",
            title="Post 1",
            updated=datetime.now(),
            doc_type=DocumentType.POST,
            status=DocumentStatus.PUBLISHED,
        )
    ]
    authors = [Author(name="Test Author")]
    feed = Feed.from_documents(docs, feed_id="test-feed", title="Test Feed", authors=authors)

    assert feed.id == "test-feed"
    assert feed.title == "Test Feed"
    assert feed.authors == authors
    assert len(feed.entries) == 1


def test_from_documents_factory_sorts_entries_newest_first():
    """Test that Feed.from_documents sorts entries by updated timestamp."""
    now = datetime.now()
    doc1 = Document(
        id="doc1",
        title="Old Post",
        updated=now - timedelta(days=1),
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
    )
    doc2 = Document(
        id="doc2",
        title="New Post",
        updated=now,
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
    )
    feed = Feed.from_documents([doc1, doc2], feed_id="test-feed", title="Test Feed")

    assert len(feed.entries) == 2
    assert feed.entries[0].id == "doc2"
    assert feed.entries[1].id == "doc1"


def test_from_documents_factory_sets_updated_from_most_recent_entry():
    """Test that Feed.from_documents sets the feed's updated time correctly."""
    now = datetime.now()
    doc1 = Document(
        id="doc1",
        title="Old Post",
        updated=now - timedelta(days=1),
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
    )
    doc2 = Document(
        id="doc2",
        title="New Post",
        updated=now,
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
    )
    feed = Feed.from_documents([doc1, doc2], feed_id="test-feed", title="Test Feed")

    assert feed.updated == doc2.updated
