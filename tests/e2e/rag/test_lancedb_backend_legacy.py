from collections.abc import Sequence
from pathlib import Path

import pytest

from egregora.data_primitives.document import Document, DocumentType
from egregora.rag.lancedb_backend_legacy import LanceDBRAGBackend
from egregora.rag.models import RAGQueryRequest


# Mock embedding function for testing
def mock_embed_fn(texts: Sequence[str], task_type: str) -> list[list[float]]:
    """A mock embedding function that returns predictable vectors."""
    return [[hash(text) / 1e10] * 768 for text in texts]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Fixture to create a temporary directory for the LanceDB database."""
    return tmp_path / "lancedb"


@pytest.fixture
def backend(db_path: Path) -> LanceDBRAGBackend:
    """Fixture to create a LanceDBRAGBackend instance for testing."""

    # Setup: Create a new backend instance for each test
    b = LanceDBRAGBackend(
        db_dir=db_path,
        table_name="test_rag",
        embed_fn=mock_embed_fn,
    )

    yield b

    # Teardown: Clean up the database directory after each test
    import shutil

    if db_path.exists():
        shutil.rmtree(db_path)


def test_add_and_query_documents(backend: LanceDBRAGBackend):
    """Test adding documents and querying them."""
    docs = [
        Document(
            id="doc1",
            content="This is a test document.",
            type=DocumentType.POST,
            metadata={"author": "test", "timestamp_utc": "2024-01-01T00:00:00Z"},
        )
    ]
    backend.add(docs)

    assert backend.count() > 0

    query = RAGQueryRequest(text="test", top_k=1)
    response = backend.query(query)

    assert len(response.hits) == 1
    assert response.hits[0].document_id == "doc1"
    assert "test document" in response.hits[0].text


def test_delete_documents(backend: LanceDBRAGBackend):
    """Test deleting documents from the store."""
    docs = [
        Document(
            id="doc2",
            content="Document to be deleted.",
            type=DocumentType.POST,
            metadata={"author": "test", "timestamp_utc": "2024-01-01T00:00:00Z"},
        )
    ]
    backend.add(docs)
    initial_count = backend.count()

    backend.delete(["doc2"])
    assert backend.count() < initial_count


def test_get_all_post_vectors(backend: LanceDBRAGBackend):
    """Test retrieving all post vectors and their centroids."""
    docs = [
        Document(
            id="doc3",
            content="First part of a post.",
            type=DocumentType.POST,
            metadata={"author": "test", "timestamp_utc": "2024-01-01T00:00:00Z"},
        ),
        Document(
            id="doc3",
            content="Second part of a post.",
            type=DocumentType.POST,
            metadata={"author": "test", "timestamp_utc": "2024-01-01T00:00:00Z"},
        ),
    ]
    backend.add(docs)

    ids, vectors = backend.get_all_post_vectors()

    assert len(ids) == 1
    assert ids[0] == "doc3"
    assert vectors.shape == (1, 768)


def test_empty_query(backend: LanceDBRAGBackend):
    """Test that querying an empty database returns no results."""
    query = RAGQueryRequest(text="empty", top_k=5)
    response = backend.query(query)
    assert len(response.hits) == 0


def test_add_multiple_documents(backend: LanceDBRAGBackend):
    """Test adding multiple documents in a single call."""
    docs = [
        Document(
            id=f"doc-multi-{i}",
            content=f"This is multi-document test number {i}.",
            type=DocumentType.POST,
            metadata={"author": "tester", "timestamp_utc": "2024-01-02T00:00:00Z"},
        )
        for i in range(5)
    ]

    backend.add(docs)

    # Assuming each document results in at least one chunk.
    assert backend.count() >= 5

    # Verify one of the documents can be retrieved.
    query = RAGQueryRequest(text="multi-document test", top_k=5)
    response = backend.query(query)

    assert len(response.hits) > 0
    retrieved_ids = {hit.document_id for hit in response.hits}
    assert "doc-multi-3" in retrieved_ids
