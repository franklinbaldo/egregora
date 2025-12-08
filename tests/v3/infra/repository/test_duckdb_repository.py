from datetime import UTC, datetime

import pytest

from egregora_v3.core.types import Document, DocumentStatus, DocumentType, Entry
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def repo(tmp_path):
    """Fixture for a temporary file-based DuckDB repository."""
    db_path = tmp_path / "test.duckdb"
    return DuckDBDocumentRepository(db_path)


def test_save_and_get_document(repo):
    doc = Document.create(
        content="Test content",
        doc_type=DocumentType.POST,
        title="Test Doc",
        status=DocumentStatus.PUBLISHED,
    )

    repo.save(doc)

    loaded = repo.get(doc.id)
    assert loaded is not None
    assert loaded.id == doc.id
    assert loaded.title == "Test Doc"
    assert loaded.content == "Test content"
    assert loaded.status == DocumentStatus.PUBLISHED
    assert loaded.doc_type == DocumentType.POST


def test_list_documents(repo):
    doc1 = Document.create(content="A", doc_type=DocumentType.POST, title="A")
    doc2 = Document.create(content="B", doc_type=DocumentType.NOTE, title="B")

    repo.save(doc1)
    repo.save(doc2)

    all_docs = repo.list()
    assert len(all_docs) == 2

    posts = repo.list(doc_type=DocumentType.POST)
    assert len(posts) == 1
    assert posts[0].title == "A"


def test_exists(repo):
    doc = Document.create(content="X", doc_type=DocumentType.POST, title="X")
    repo.save(doc)

    assert repo.exists(doc.id)
    assert not repo.exists("non-existent")


def test_save_and_get_entry(repo):
    entry = Entry(
        id="entry-1",
        title="Entry 1",
        updated=datetime.now(UTC),
        content="Entry Content",
    )

    repo.save_entry(entry)

    loaded = repo.get_entry("entry-1")
    assert loaded is not None
    assert loaded.id == "entry-1"
    assert loaded.title == "Entry 1"


def test_persistence_reopen(tmp_path):
    """Test data persists across connections."""
    db_path = tmp_path / "persist.duckdb"

    # Session 1
    repo1 = DuckDBDocumentRepository(db_path)
    doc = Document.create(content="P", doc_type=DocumentType.POST, title="Persistent")
    repo1.save(doc)
    del repo1

    # Session 2
    repo2 = DuckDBDocumentRepository(db_path)
    loaded = repo2.get(doc.id)
    assert loaded is not None
    assert loaded.title == "Persistent"


def test_update_document(repo):
    """Test overwriting/updating a document."""
    doc = Document.create(content="Original", doc_type=DocumentType.POST, title="Title")
    repo.save(doc)

    doc.content = "Updated"
    repo.save(doc)

    loaded = repo.get(doc.id)
    assert loaded.content == "Updated"


def test_delete_document(repo):
    """Test deleting a document."""
    doc = Document.create(content="D", doc_type=DocumentType.POST, title="Delete Me")
    repo.save(doc)

    assert repo.exists(doc.id)

    repo.delete(doc.id)

    assert not repo.exists(doc.id)
    assert repo.get(doc.id) is None
