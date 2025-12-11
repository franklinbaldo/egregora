import builtins
import ibis
import pytest
from datetime import datetime, UTC
from egregora_v3.core.types import Document, DocumentType, Entry, Source
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository

@pytest.fixture
def duckdb_conn():
    return ibis.duckdb.connect(":memory:")

@pytest.fixture
def repo(duckdb_conn):
    repo = DuckDBDocumentRepository(duckdb_conn)
    repo.initialize()
    return repo

def test_save_and_get_document(repo):
    doc = Document.create(content="Test content", doc_type=DocumentType.POST, title="Test Post")
    repo.save(doc)

    retrieved = repo.get(doc.id)
    assert retrieved is not None
    assert retrieved.id == doc.id
    assert retrieved.title == "Test Post"
    assert retrieved.content == "Test content"
    assert retrieved.doc_type == DocumentType.POST
    # Check serialization of datetime
    assert retrieved.updated == doc.updated

def test_list_documents(repo):
    doc1 = Document.create(title="Post 1", content="Content 1", doc_type=DocumentType.POST)
    doc2 = Document.create(title="Post 2", content="Content 2", doc_type=DocumentType.POST)
    doc3 = Document.create(title="Profile 1", content="Profile Content", doc_type=DocumentType.PROFILE)

    repo.save(doc1)
    repo.save(doc2)
    repo.save(doc3)

    # List all
    all_docs = repo.list()
    assert len(all_docs) == 3

    # List by type
    posts = repo.list(doc_type=DocumentType.POST)
    assert len(posts) == 2
    assert {d.id for d in posts} == {doc1.id, doc2.id}

    profiles = repo.list(doc_type=DocumentType.PROFILE)
    assert len(profiles) == 1
    assert profiles[0].id == doc3.id

def test_delete_document(repo):
    doc = Document.create(title="To Delete", content="...", doc_type=DocumentType.NOTE)
    repo.save(doc)

    assert repo.get(doc.id) is not None

    repo.delete(doc.id)
    assert repo.get(doc.id) is None

def test_exists_document(repo):
    doc = Document.create(title="Exists?", content="...", doc_type=DocumentType.NOTE)
    assert not repo.exists(doc.id)

    repo.save(doc)
    assert repo.exists(doc.id)

def test_save_update_document(repo):
    doc = Document.create(title="Original", content="Original", doc_type=DocumentType.POST)
    repo.save(doc)

    doc.title = "Updated"
    repo.save(doc)

    retrieved = repo.get(doc.id)
    assert retrieved.title == "Updated"

# --- Entry Tests ---

def test_save_and_get_entry(repo):
    entry = Entry(
        id="entry-1",
        title="Test Entry",
        updated=datetime.now(UTC),
        content="Entry Content"
    )
    repo.save_entry(entry)

    retrieved = repo.get_entry(entry.id)
    assert retrieved is not None
    assert retrieved.id == entry.id
    assert retrieved.title == "Test Entry"
    # Ensure it's exactly an Entry, not a Document
    assert type(retrieved) is Entry

def test_get_entries_by_source(repo):
    source_id = "whatsapp-chat-123"
    other_source = "other-source"

    entry1 = Entry(
        id="e1",
        title="E1",
        updated=datetime.now(UTC),
        source=Source(id=source_id)
    )
    entry2 = Entry(
        id="e2",
        title="E2",
        updated=datetime.now(UTC),
        source=Source(id=source_id)
    )
    entry3 = Entry(
        id="e3",
        title="E3",
        updated=datetime.now(UTC),
        source=Source(id=other_source)
    )
    entry4 = Entry(
        id="e4",
        title="E4",
        updated=datetime.now(UTC),
        # No source
    )

    repo.save_entry(entry1)
    repo.save_entry(entry2)
    repo.save_entry(entry3)
    repo.save_entry(entry4)

    results = repo.get_entries_by_source(source_id)
    assert len(results) == 2
    ids = {e.id for e in results}
    assert ids == {"e1", "e2"}

    empty_results = repo.get_entries_by_source("non-existent")
    assert len(empty_results) == 0

def test_get_polymorphism(repo):
    # Retrieve Document as Entry
    doc = Document.create(title="Doc", content="C", doc_type=DocumentType.POST)
    repo.save(doc)

    # get_entry should be able to retrieve it, returning Document (subclass of Entry)
    entry = repo.get_entry(doc.id)
    assert entry is not None
    assert isinstance(entry, Document)
    assert entry.doc_type == DocumentType.POST

    # get() should NOT retrieve an Entry
    ent = Entry(id="pure-entry", title="E", updated=datetime.now(UTC))
    repo.save_entry(ent)

    val = repo.get(ent.id)
    assert val is None
