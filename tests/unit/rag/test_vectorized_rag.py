"""Tests for vectorized RAG operations."""

import numpy as np
import pytest

from egregora.config import EMBEDDING_DIM
from egregora.rag.lancedb_backend import LanceDBRAGBackend


class MockEmbeddingFn:
    def __call__(self, texts, task_type):
        return [np.random.rand(EMBEDDING_DIM).tolist() for _ in texts]


class Document:
    def __init__(self, document_id, text, document_type="POST"):
        self.document_id = document_id
        self.text = text
        self.document_type = document_type
        self.title = "Mock Title"
        self.author_slug = "mock-author"
        self.slug = f"mock-slug-{document_id}"


@pytest.fixture
def sample_lancedb_backend(tmp_path):
    """Creates a sample LanceDB RAG backend with test data."""
    db_dir = tmp_path / "lancedb"
    backend = LanceDBRAGBackend(db_dir, "test_table", MockEmbeddingFn())

    docs = [
        Document("doc1", "This is the first chunk of doc1."),
        Document("doc1", "This is the second chunk of doc1."),
        Document("doc2", "This is the first chunk of doc2."),
    ]
    backend.add(docs)
    return backend


def test_vectorized_centroid_calculation(sample_lancedb_backend):
    """
    Tests that the vectorized centroid calculation is correct.
    """
    from egregora.rag.lancedb_backend_legacy import LanceDBRAGBackend as LegacyLanceDBRAGBackend

    # Get centroids from the new, vectorized implementation
    new_backend = sample_lancedb_backend
    new_ids, new_vectors = new_backend.get_all_post_vectors()

    # Get centroids from the old, in-memory implementation
    legacy_backend = LegacyLanceDBRAGBackend(
        new_backend._db_dir, new_backend._table_name, new_backend._embed_fn
    )
    legacy_ids, legacy_vectors = legacy_backend.get_all_post_vectors()

    # Sort results to ensure consistent comparison
    new_sorted_indices = np.argsort(new_ids)
    legacy_sorted_indices = np.argsort(legacy_ids)

    new_sorted_ids = np.array(new_ids)[new_sorted_indices]
    legacy_sorted_ids = np.array(legacy_ids)[legacy_sorted_indices]

    new_sorted_vectors = new_vectors[new_sorted_indices]
    legacy_sorted_vectors = legacy_vectors[legacy_sorted_indices]

    # Assert that the document IDs and centroid vectors are the same
    np.testing.assert_array_equal(new_sorted_ids, legacy_sorted_ids)
    np.testing.assert_allclose(new_sorted_vectors, legacy_sorted_vectors, rtol=1e-5)
