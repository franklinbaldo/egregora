import ibis
import pytest

from egregora_v3.core.types import Document, DocumentType
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def duckdb_conn():
    # Use in-memory DuckDB for testing
    return ibis.duckdb.connect(":memory:")


@pytest.fixture
def repo(duckdb_conn):
    # Pass the connection to the repository
    # We might need to initialize the schema here or inside the repo
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
