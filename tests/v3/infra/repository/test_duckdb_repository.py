import ibis
import pytest
from datetime import datetime, UTC

from egregora_v3.core.types import Document, DocumentType, Entry
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def repo() -> DuckDBDocumentRepository:
    """Provides an in-memory DuckDB repository for testing."""
    # Using a named in-memory database to ensure connection is shared
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()
    return repo


def test_hydrate_object_locking(repo: DuckDBDocumentRepository):
    """
    Locks the behavior of the _hydrate_object method.
    It should correctly deserialize a raw Entry and a Document.
    """
    # ARRANGE
    now = datetime.now(UTC)
    doc = Document(id="doc-1", title="A Document", doc_type=DocumentType.POST, updated=now)
    entry = Entry(id="entry-1", title="An Entry", updated=now)

    repo.save(doc)
    repo.save(entry)

    # ACT
    hydrated_doc = repo.get_entry(doc.id)
    hydrated_entry = repo.get_entry(entry.id)

    # ASSERT
    assert isinstance(hydrated_doc, Document)
    assert hydrated_doc.id == doc.id
    assert hydrated_doc.doc_type == DocumentType.POST

    assert isinstance(hydrated_entry, Entry)
    assert not isinstance(hydrated_entry, Document)  # Verify it's not the subclass
    assert hydrated_entry.id == entry.id


def test_get_method_returns_none_for_entry_locking(repo: DuckDBDocumentRepository):
    """
    Locks the behavior of the get() method.
    It should return None when the ID belongs to a raw Entry, not a Document.
    """
    # ARRANGE
    entry = Entry(id="entry-only-1", title="Raw Entry", updated=datetime.now(UTC))
    repo.save(entry)

    # ACT
    result = repo.get(entry.id)

    # ASSERT
    assert result is None


def test_get_entries_by_source_locking(repo: DuckDBDocumentRepository):
    """
    Locks the behavior of get_entries_by_source.
    It should return only entries with the matching source.id.
    """
    # ARRANGE
    now = datetime.now(UTC)
    source_id = "source-1"

    # Entries that should be found
    entry_with_source1 = Entry(
        id="entry-1",
        title="Entry with Source",
        updated=now,
        source={"id": source_id, "title": "Source Feed"},
    )
    doc_with_source = Document(
        id="doc-1",
        title="Document with Source",
        updated=now,
        doc_type=DocumentType.POST,
        source={"id": source_id, "title": "Source Feed"},
    )

    # Entries that should NOT be found
    entry_without_source = Entry(id="entry-2", title="No Source", updated=now)
    entry_with_diff_source = Entry(
        id="entry-3",
        title="Different Source",
        updated=now,
        source={"id": "source-2", "title": "Another Feed"},
    )

    repo.save(entry_with_source1)
    repo.save(doc_with_source)
    repo.save(entry_without_source)
    repo.save(entry_with_diff_source)

    # ACT
    results = repo.get_entries_by_source(source_id)

    # ASSERT
    assert len(results) == 2
    result_ids = {entry.id for entry in results}
    assert "entry-1" in result_ids
    assert "doc-1" in result_ids
