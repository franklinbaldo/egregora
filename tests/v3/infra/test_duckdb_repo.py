from datetime import UTC, datetime

import ibis
import pytest

from egregora_v3.core.types import Document, DocumentType, Entry
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


class MockIbisConnection:
    """A mock Ibis connection that lacks the '.con' attribute."""

    pass


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB Ibis connection."""
    return ibis.duckdb.connect(":memory:")


@pytest.fixture
def repo(duckdb_conn):
    """Provides an initialized DuckDBDocumentRepository."""
    repo = DuckDBDocumentRepository(duckdb_conn)
    repo.initialize()
    return repo


def test_repo_requires_raw_connection():
    """Tests that DuckDBDocumentRepository raises ValueError if the connection has no raw '.con' attribute."""
    mock_conn = MockIbisConnection()
    with pytest.raises(ValueError, match="raw DuckDB connection"):
        DuckDBDocumentRepository(mock_conn)


def test_initialize_creates_table(repo):
    """Tests that the table is created on initialization."""
    assert "documents" in repo.conn.list_tables()


def test_save_and_get_document(repo):
    """Tests saving and retrieving a document."""
    doc = Document.create(content="Test content", doc_type=DocumentType.POST, title="Test Post")
    repo.save(doc)

    retrieved = repo.get(doc.id)
    assert retrieved is not None
    assert retrieved.id == doc.id
    assert retrieved.title == "Test Post"


def test_save_is_upsert(repo):
    """Tests that saving an existing document updates it (upsert)."""
    doc = Document.create(title="Original", content="Original", doc_type=DocumentType.POST)
    repo.save(doc)

    # Modify and save again
    doc.title = "Updated"
    doc.updated = datetime.now(UTC)
    repo.save(doc)

    retrieved = repo.get(doc.id)
    assert retrieved is not None
    assert retrieved.title == "Updated"
    assert retrieved.id == doc.id

    # Check count to ensure no new record was created
    assert repo.count(doc_type=DocumentType.POST) == 1


def test_delete_document(repo):
    """Tests deleting a document."""
    doc = Document.create(title="To Delete", content="...", doc_type=DocumentType.NOTE)
    repo.save(doc)

    assert repo.exists(doc.id)
    repo.delete(doc.id)
    assert not repo.exists(doc.id)


def test_save_and_get_entry(repo):
    """Tests saving and retrieving a plain Entry."""
    entry = Entry(id="entry-1", title="Test Entry", updated=datetime.now(UTC), content="Entry Content")
    repo.save(entry)

    retrieved = repo.get_entry(entry.id)
    assert retrieved is not None
    assert retrieved.id == entry.id
    assert type(retrieved) is Entry


def test_save_handles_documents_and_entries(repo):
    """Tests that save correctly handles both Document and Entry instances."""
    doc = Document.create(content="Test content", doc_type=DocumentType.POST, title="Test Post")
    entry = Entry(id="entry-1", title="Test Entry", updated=datetime.now(UTC), content="Entry Content")

    repo.save(doc)
    repo.save(entry)

    retrieved_doc = repo.get(doc.id)
    assert retrieved_doc is not None
    assert retrieved_doc.id == doc.id

    retrieved_entry = repo.get_entry(entry.id)
    assert retrieved_entry is not None
    assert type(retrieved_entry) is Entry
