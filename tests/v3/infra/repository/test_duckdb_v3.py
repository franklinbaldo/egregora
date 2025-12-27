import pytest
from datetime import datetime, timezone, timedelta
import ibis
from uuid import uuid4

from egregora_v3.core.types import Document, DocumentType, Entry, Source
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def duckdb_repo() -> DuckDBDocumentRepository:
    """Provides an in-memory DuckDB repository for testing."""
    conn = ibis.duckdb.connect()
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()
    return repo


def test_save_and_get_document(duckdb_repo: DuckDBDocumentRepository):
    """Tests that a Document can be saved and retrieved."""
    # ARRANGE
    doc = Document(
        id=str(uuid4()),
        content="This is a test post.",
        doc_type=DocumentType.POST,
        title="Test Post",
        source=Source(id="test_source", type="test"),
        updated=datetime.now(timezone.utc),
    )

    # ACT
    duckdb_repo.save(doc)
    retrieved_doc = duckdb_repo.get(doc.id)

    # ASSERT
    assert retrieved_doc is not None
    assert retrieved_doc.id == doc.id
    assert retrieved_doc.title == "Test Post"
    assert retrieved_doc.doc_type == DocumentType.POST
    assert retrieved_doc.source.id == "test_source"


def test_save_and_get_entry(duckdb_repo: DuckDBDocumentRepository):
    """Tests that a basic Entry can be saved and retrieved."""
    # ARRANGE
    entry = Entry(
        id=str(uuid4()),
        title="Test Entry",
        content="This is a basic entry.",
        source=Source(id="test_source", type="test"),
        updated=datetime.now(timezone.utc),
    )

    # ACT
    duckdb_repo.save(entry)
    retrieved_entry = duckdb_repo.get_entry(entry.id)

    # ASSERT
    assert retrieved_entry is not None
    assert isinstance(retrieved_entry, Entry)
    assert not isinstance(retrieved_entry, Document)
    assert retrieved_entry.id == entry.id
    assert retrieved_entry.content == "This is a basic entry."


def test_get_nonexistent_document(duckdb_repo: DuckDBDocumentRepository):
    """Tests that getting a non-existent document returns None."""
    # ACT
    retrieved_doc = duckdb_repo.get(str(uuid4()))

    # ASSERT
    assert retrieved_doc is None


def test_upsert_document(duckdb_repo: DuckDBDocumentRepository):
    """Tests that saving a document with an existing ID updates it."""
    # ARRANGE
    doc_id = str(uuid4())
    original_doc = Document(
        id=doc_id,
        content="Original content.",
        doc_type=DocumentType.POST,
        title="Original Title",
        updated=datetime.now(timezone.utc),
    )
    duckdb_repo.save(original_doc)

    # ACT
    updated_doc = Document(
        id=doc_id,
        content="Updated content.",
        doc_type=DocumentType.POST,
        title="Updated Title",
        updated=datetime.now(timezone.utc),
    )
    duckdb_repo.save(updated_doc)
    retrieved_doc = duckdb_repo.get(doc_id)

    # ASSERT
    assert retrieved_doc is not None
    assert retrieved_doc.title == "Updated Title"
    assert retrieved_doc.content == "Updated content."


def test_get_does_not_return_entry(duckdb_repo: DuckDBDocumentRepository):
    """Tests that the `get` method (for Documents) ignores raw Entries."""
    # ARRANGE
    entry = Entry(
        id=str(uuid4()),
        title="Raw Entry",
        content="This is a raw entry, not a document.",
        source=Source(id="test_source", type="test"),
        updated=datetime.now(timezone.utc),
    )
    duckdb_repo.save(entry)

    # ACT
    result = duckdb_repo.get(entry.id)

    # ASSERT
    assert result is None


def test_list_all_documents(duckdb_repo: DuckDBDocumentRepository):
    """Tests listing all documents, excluding raw entries."""
    # ARRANGE
    duckdb_repo.save(Document(doc_type=DocumentType.POST, title="Post 1"))
    duckdb_repo.save(Document(doc_type=DocumentType.MEDIA, title="Media 1"))
    duckdb_repo.save(
        Entry(
            id=str(uuid4()),
            title="Raw Entry",
            content="A raw entry",
            updated=datetime.now(timezone.utc),
        )
    )

    # ACT
    results = duckdb_repo.list()

    # ASSERT
    assert len(results) == 2
    assert all(isinstance(d, Document) for d in results)


def test_list_documents_filtered_by_type(duckdb_repo: DuckDBDocumentRepository):
    """Tests that listing can be filtered by DocumentType."""
    # ARRANGE
    duckdb_repo.save(Document(doc_type=DocumentType.POST, title="Post 1"))
    duckdb_repo.save(Document(doc_type=DocumentType.POST, title="Post 2"))
    duckdb_repo.save(Document(doc_type=DocumentType.MEDIA, title="Media 1"))

    # ACT
    results = duckdb_repo.list(doc_type=DocumentType.POST)

    # ASSERT
    assert len(results) == 2
    assert all(d.doc_type == DocumentType.POST for d in results)


def test_delete_document(duckdb_repo: DuckDBDocumentRepository):
    """Tests that a document can be deleted."""
    # ARRANGE
    doc = Document(doc_type=DocumentType.POST, title="To be deleted")
    duckdb_repo.save(doc)

    # ACT
    duckdb_repo.delete(doc.id)
    retrieved_doc = duckdb_repo.get(doc.id)

    # ASSERT
    assert retrieved_doc is None


def test_exists_document(duckdb_repo: DuckDBDocumentRepository):
    """Tests that the exists method works correctly."""
    # ARRANGE
    doc = Document(doc_type=DocumentType.POST, title="I exist")
    duckdb_repo.save(doc)

    # ACT & ASSERT
    assert duckdb_repo.exists(doc.id) is True
    assert duckdb_repo.exists(str(uuid4())) is False


def test_count_all_documents(duckdb_repo: DuckDBDocumentRepository):
    """Tests counting all documents, excluding raw entries."""
    # ARRANGE
    duckdb_repo.save(Document(doc_type=DocumentType.POST, title="Post 1"))
    duckdb_repo.save(Document(doc_type=DocumentType.MEDIA, title="Media 1"))
    duckdb_repo.save(
        Entry(
            id=str(uuid4()),
            title="Raw Entry",
            content="A raw entry",
            updated=datetime.now(timezone.utc),
        )
    )

    # ACT
    count = duckdb_repo.count()

    # ASSERT
    assert count == 2


def test_count_documents_filtered_by_type(duckdb_repo: DuckDBDocumentRepository):
    """Tests that counting can be filtered by DocumentType."""
    # ARRANGE
    duckdb_repo.save(Document(doc_type=DocumentType.POST, title="Post 1"))
    duckdb_repo.save(Document(doc_type=DocumentType.POST, title="Post 2"))
    duckdb_repo.save(Document(doc_type=DocumentType.MEDIA, title="Media 1"))

    # ACT
    count = duckdb_repo.count(doc_type=DocumentType.POST)

    # ASSERT
    assert count == 2


def test_get_entries_by_source(duckdb_repo: DuckDBDocumentRepository):
    """Tests retrieving all entries for a given source ID."""
    # ARRANGE
    source_id = "test_source"
    duckdb_repo.save(
        Document(
            doc_type=DocumentType.POST,
            title="Post 1",
            source=Source(id=source_id, type="test"),
        )
    )
    duckdb_repo.save(
        Entry(
            id=str(uuid4()),
            title="Raw Entry",
            content="A raw entry",
            source=Source(id=source_id, type="test"),
            updated=datetime.now(timezone.utc),
        )
    )
    duckdb_repo.save(
        Document(
            doc_type=DocumentType.POST,
            title="Post 2",
            source=Source(id="other_source", type="test"),
        )
    )

    # ACT
    results = duckdb_repo.get_entries_by_source(source_id)

    # ASSERT
    assert len(results) == 2
    assert all(e.source.id == source_id for e in results)


def test_complex_json_data(duckdb_repo: DuckDBDocumentRepository):
    """Tests that a document with complex JSON data can be saved and retrieved."""
    # ARRANGE
    complex_data = {
        "key1": "value1",
        "key2": [1, 2, 3],
        "key3": {"nested_key": "nested_value"},
    }
    doc = Document(
        doc_type=DocumentType.POST,
        title="Complex JSON",
        internal_metadata=complex_data,
    )

    # ACT
    duckdb_repo.save(doc)
    retrieved_doc = duckdb_repo.get(doc.id)

    # ASSERT
    assert retrieved_doc is not None
    assert retrieved_doc.internal_metadata == complex_data


def test_get_entry_can_retrieve_document(duckdb_repo: DuckDBDocumentRepository):
    """Tests that `get_entry` can retrieve a Document."""
    # ARRANGE
    doc = Document(doc_type=DocumentType.POST, title="A Document")
    duckdb_repo.save(doc)

    # ACT
    retrieved_entry = duckdb_repo.get_entry(doc.id)

    # ASSERT
    assert retrieved_entry is not None
    assert isinstance(retrieved_entry, Document)
    assert retrieved_entry.id == doc.id
    assert retrieved_entry.title == "A Document"
