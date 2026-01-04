import uuid
from datetime import datetime, timezone, timedelta

import ibis
import pytest

from egregora_v3.core.types import Document, DocumentType, Entry, Source
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def repo() -> DuckDBDocumentRepository:
    """Provides an in-memory DuckDB repository for testing."""
    conn = ibis.duckdb.connect()
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()
    return repo


def test_list_documents(repo: DuckDBDocumentRepository):
    """Verify that the list method retrieves all documents correctly."""
    # ARRANGE
    repo.save(Document(doc_type=DocumentType.POST, title="Post 1"))
    repo.save(Document(doc_type=DocumentType.MEDIA, title="Media 1"))
    repo.save(
        Entry(
            id=str(uuid.uuid4()),
            title="Raw Entry",
            updated=datetime.now(timezone.utc),
        )
    )

    # ACT
    all_docs = repo.list()
    post_docs = repo.list(doc_type=DocumentType.POST)

    # ASSERT
    assert len(all_docs) == 2
    assert all(isinstance(d, Document) for d in all_docs)

    assert len(post_docs) == 1
    assert post_docs[0].title == "Post 1"


def test_list_with_order_by_and_limit(repo: DuckDBDocumentRepository):
    """Tests that ordering and limiting work correctly."""
    # ARRANGE
    now = datetime.now(timezone.utc)
    repo.save(
        Document(
            doc_type=DocumentType.POST, title="Post 1", updated=now - timedelta(days=2)
        )
    )
    repo.save(
        Document(
            doc_type=DocumentType.POST, title="Post 2", updated=now - timedelta(days=1)
        )
    )
    repo.save(Document(doc_type=DocumentType.POST, title="Post 3", updated=now))

    # ACT
    results = repo.list(order_by="-updated", limit=2)

    # ASSERT
    assert len(results) == 2
    assert results[0].title == "Post 3"
    assert results[1].title == "Post 2"


def test_get_retrieves_document_but_not_entry(repo: DuckDBDocumentRepository):
    """Tests that `get` retrieves a Document but returns None for a raw Entry."""
    # ARRANGE
    doc = Document(doc_type=DocumentType.POST, title="A Document")
    entry = Entry(id="entry-1", title="An Entry", updated=datetime.now(timezone.utc))
    repo.save(doc)
    repo.save(entry)

    # ACT
    retrieved_doc = repo.get(doc.id)
    retrieved_entry = repo.get(entry.id)

    # ASSERT
    assert retrieved_doc is not None
    assert retrieved_doc.id == doc.id
    assert retrieved_entry is None


def test_get_entry_retrieves_both_document_and_entry(
    repo: DuckDBDocumentRepository,
):
    """Tests that `get_entry` retrieves both a Document and a raw Entry."""
    # ARRANGE
    doc = Document(doc_type=DocumentType.POST, title="A Document")
    entry = Entry(id="entry-1", title="An Entry", updated=datetime.now(timezone.utc))
    repo.save(doc)
    repo.save(entry)

    # ACT
    retrieved_doc = repo.get_entry(doc.id)
    retrieved_entry = repo.get_entry(entry.id)

    # ASSERT
    assert retrieved_doc is not None
    assert isinstance(retrieved_doc, Document)
    assert retrieved_doc.id == doc.id

    assert retrieved_entry is not None
    assert isinstance(retrieved_entry, Entry)
    assert not isinstance(retrieved_entry, Document)
    assert retrieved_entry.id == entry.id


def test_get_entries_by_source(repo: DuckDBDocumentRepository):
    """Verify that entries can be retrieved by their source ID."""
    # ARRANGE
    source_id = "shared-source"
    entry1 = Entry(
        id=str(uuid.uuid4()),
        title="Entry 1",
        source=Source(id=source_id, collector="test"),
        updated=datetime.now(timezone.utc),
    )
    entry2 = Document(
        id=str(uuid.uuid4()),
        title="Doc 1",
        doc_type=DocumentType.POST,
        source=Source(id=source_id, collector="test"),
        updated=datetime.now(timezone.utc),
    )
    other_entry = Entry(
        id=str(uuid.uuid4()),
        title="Other Entry",
        source=Source(id="other-source", collector="test"),
        updated=datetime.now(timezone.utc),
    )
    repo.save(entry1)
    repo.save(entry2)
    repo.save(other_entry)

    # ACT
    retrieved_entries = repo.get_entries_by_source(source_id)

    # ASSERT
    assert len(retrieved_entries) == 2
    assert {e.id for e in retrieved_entries} == {entry1.id, entry2.id}
