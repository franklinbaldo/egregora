"""Tests for vectorized RAG operations."""

import numpy as np
import pytest

from egregora.config import EMBEDDING_DIM
from egregora.rag.lancedb_backend import LanceDBRAGBackend

# Initialize a random number generator for consistent, modern NumPy usage.
rng = np.random.default_rng()


class MockEmbeddingFn:
    def __call__(self, texts, task_type):
        return [rng.random(EMBEDDING_DIM).tolist() for _ in texts]


class Document:
    def __init__(self, document_id, content, document_type="POST"):
        self.document_id = document_id
        self.content = content
        self.type = document_type
        self.title = "Mock Title"
        self.author_slug = "mock-author"
        self.slug = f"mock-slug-{document_id}"


@pytest.fixture
def sample_lancedb_backend(tmp_path):
    """Creates a sample LanceDB RAG backend with test data."""
    db_dir = tmp_path / "lancedb"
    backend = LanceDBRAGBackend(db_dir, "test_table", MockEmbeddingFn())

    docs = [
        Document("doc1", content="This is the first chunk of doc1."),
        Document("doc1", content="This is the second chunk of doc1."),
        Document("doc2", content="This is the first chunk of doc2."),
    ]
    backend.add(docs)
    return backend


