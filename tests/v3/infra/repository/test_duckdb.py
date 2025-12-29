import pytest
from datetime import datetime, timedelta, timezone

import ibis

from egregora_v3.core.types import Document, DocumentType
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def duckdb_repo() -> DuckDBDocumentRepository:
    """Provides an in-memory DuckDB repository for testing."""
    conn = ibis.duckdb.connect()
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()
    return repo


def test_list_with_order_by_and_limit(duckdb_repo: DuckDBDocumentRepository):
    """Tests that the list method correctly applies sorting and limiting."""
    # ARRANGE
    now = datetime.now(timezone.utc)
    docs = []
    for i in range(5):
        doc = Document(
            content=f"Post {i}",
            doc_type=DocumentType.POST,
            title=f"Post {i}",
        )
        doc.updated = now - timedelta(days=i)
        docs.append(doc)

    for doc in docs:
        duckdb_repo.save(doc)

    # ACT
    # Fetch the 3 most recent posts
    result = duckdb_repo.list(
        doc_type=DocumentType.POST, order_by="-updated", limit=3
    )

    # ASSERT
    assert len(result) == 3
    assert result[0].title == "Post 0"  # Most recent
    assert result[1].title == "Post 1"
    assert result[2].title == "Post 2"

    # Check that they are sorted correctly (most recent first)
    assert result[0].updated > result[1].updated > result[2].updated


from egregora_v3.core.types import Entry, Source


def test_get_retrieves_document_but_not_entry(duckdb_repo: DuckDBDocumentRepository):
    """Locks behavior: get() should only retrieve Documents, not raw Entries."""
    # ARRANGE
    now = datetime.now(timezone.utc)
    doc = Document(content="A document", doc_type=DocumentType.POST, title="Doc")
    entry = Entry(id="entry-1", title="Raw Entry", updated=now, content="An entry")
    duckdb_repo.save(doc)
    duckdb_repo.save(entry)

    # ACT
    retrieved_doc = duckdb_repo.get(doc.id)
    retrieved_entry = duckdb_repo.get(entry.id)

    # ASSERT
    assert retrieved_doc is not None
    assert isinstance(retrieved_doc, Document)
    assert retrieved_doc.id == doc.id
    assert retrieved_entry is None


def test_list_retrieves_documents_but_not_entries(
    duckdb_repo: DuckDBDocumentRepository,
):
    """Locks behavior: list() should only retrieve Documents, not raw Entries."""
    # ARRANGE
    now = datetime.now(timezone.utc)
    doc = Document(content="A document", doc_type=DocumentType.POST, title="Doc")
    entry = Entry(id="entry-1", title="Raw Entry", updated=now, content="An entry")
    duckdb_repo.save(doc)
    duckdb_repo.save(entry)

    # ACT
    result = duckdb_repo.list()

    # ASSERT
    assert len(result) == 1
    assert isinstance(result[0], Document)
    assert result[0].id == doc.id


def test_get_entry_retrieves_both_document_and_entry(
    duckdb_repo: DuckDBDocumentRepository,
):
    """Locks behavior: get_entry() should retrieve any Entry or subclass."""
    # ARRANGE
    now = datetime.now(timezone.utc)
    doc = Document(content="A document", doc_type=DocumentType.POST, title="Doc")
    entry = Entry(id="entry-1", title="Raw Entry", updated=now, content="An entry")
    duckdb_repo.save(doc)
    duckdb_repo.save(entry)

    # ACT
    retrieved_doc = duckdb_repo.get_entry(doc.id)
    retrieved_entry = duckdb_repo.get_entry(entry.id)

    # ASSERT
    assert retrieved_doc is not None
    assert isinstance(retrieved_doc, Document)
    assert retrieved_doc.id == doc.id

    assert retrieved_entry is not None
    assert isinstance(retrieved_entry, Entry)
    assert not isinstance(
        retrieved_entry, Document
    )  # Make sure it's a raw Entry
    assert retrieved_entry.id == entry.id


def test_get_entries_by_source(duckdb_repo: DuckDBDocumentRepository):
    """Locks behavior: get_entries_by_source() retrieves all entries for a source."""
    # ARRANGE
    now = datetime.now(timezone.utc)
    source_id = "source-1"
    entry1 = Entry(
        id="entry-1",
        title="Entry 1",
        updated=now,
        content="Entry 1",
        source=Source(id=source_id, name="Test Source"),
    )
    entry2 = Document(
        content="Doc 1",
        doc_type=DocumentType.POST,
        title="Doc 1",
        source=Source(id=source_id, name="Test Source"),
    )
    other_entry = Entry(
        id="other-entry",
        title="Other",
        updated=now,
        content="Other",
        source=Source(id="source-2", name="Other Source"),
    )
    duckdb_repo.save(entry1)
    duckdb_repo.save(entry2)
    duckdb_repo.save(other_entry)

    # ACT
    results = duckdb_repo.get_entries_by_source(source_id)

    # ASSERT
    assert len(results) == 2
    result_ids = {e.id for e in results}
    assert entry1.id in result_ids
    assert entry2.id in result_ids
