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
