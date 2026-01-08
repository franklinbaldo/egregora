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
    source_id_1 = str(uuid.uuid4())
    source_id_2 = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Entries for the first source
    entry1 = Entry(id="entry1", title="Entry 1", updated=now, source=Source(id=source_id_1, type="test"))
    entry2 = Entry(id="entry2", title="Entry 2", updated=now, source=Source(id=source_id_1, type="test"))

    # A document, which is also an entry
    doc1 = Document(id="doc1", title="Doc 1", updated=now, source=Source(id=source_id_1, type="test"), doc_type=DocumentType.POST, content="test")


    # Entry for the second source
    entry3 = Entry(id="entry3", title="Entry 3", updated=now, source=Source(id=source_id_2, type="test"))

    # Entry with no source
    entry4 = Entry(id="entry4", title="Entry 4", updated=now)


    repo.save(entry1)
    repo.save(entry2)
    repo.save(doc1)
    repo.save(entry3)
    repo.save(entry4)


    # Retrieve entries for the first source
    retrieved_entries = repo.get_entries_by_source(source_id_1)

    assert len(retrieved_entries) == 3
    retrieved_ids = {entry.id for entry in retrieved_entries}
    assert retrieved_ids == {"entry1", "entry2", "doc1"}

    # Verify that the retrieved objects are correct
    for entry in retrieved_entries:
        assert entry.source
        assert entry.source.id == source_id_1

    # Retrieve entries for the second source
    retrieved_entries_2 = repo.get_entries_by_source(source_id_2)
    assert len(retrieved_entries_2) == 1
    assert retrieved_entries_2[0].id == "entry3"

    # Retrieve entries for a non-existent source
    retrieved_entries_3 = repo.get_entries_by_source("non-existent-source")
    assert len(retrieved_entries_3) == 0
