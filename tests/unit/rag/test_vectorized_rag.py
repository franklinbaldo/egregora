"""Tests for vectorized RAG operations."""

from datetime import datetime

import numpy as np
import pytest

from egregora.config import EMBEDDING_DIM
from egregora.data_primitives.document import DocumentType
from egregora.rag.lancedb_backend import LanceDBRAGBackend

# A shared seed for deterministic testing
TEST_SEED = 42


class MockEmbeddingFn:
    def __init__(self, rng_instance):
        self._rng = rng_instance

    def __call__(self, texts, task_type):
        return [self._rng.random(EMBEDDING_DIM).tolist() for _ in texts]


class Document:
    def __init__(self, document_id, content, document_type=DocumentType.POST):
        self.document_id = document_id
        self.content = content
        self.type = document_type
        self.title = "Mock Title"
        self.author_slug = "mock-author"
        self.slug = f"mock-slug-{document_id}"
        self.suggested_path = f"posts/{self.slug}.md"
        self.created_at = datetime.now()
        self.source_window = "test_window"
        self.metadata = {}


@pytest.fixture
def sample_lancedb_backend(tmp_path):
    """Creates a sample LanceDB RAG backend with test data."""
    # Use a seeded RNG for deterministic embeddings in the test
    rng_for_backend = np.random.default_rng(seed=TEST_SEED)

    db_dir = tmp_path / "lancedb"
    backend = LanceDBRAGBackend(db_dir, "test_table", MockEmbeddingFn(rng_for_backend))

    docs = [
        Document("doc1", content="This is the first chunk of doc1."),
        Document("doc1", content="This is the second chunk of doc1."),
        Document("doc2", content="This is the first chunk of doc2."),
    ]
    backend.add(docs)
    return backend


def test_vectorized_centroid_calculation(sample_lancedb_backend):
    """
    Tests that the vectorized centroid calculation is correct.
    """
    # Get centroids from the implementation
    backend = sample_lancedb_backend
    doc_ids, vectors = backend.get_all_post_vectors()

    # Re-create the same sequence of embeddings to calculate expected centroids
    rng_for_expected = np.random.default_rng(seed=TEST_SEED)

    # 3 documents are chunked, resulting in 3 chunks, so 3 embeddings are generated.
    v1 = rng_for_expected.random(EMBEDDING_DIM)
    v2 = rng_for_expected.random(EMBEDDING_DIM)
    v3 = rng_for_expected.random(EMBEDDING_DIM)

    expected_centroid_doc1 = np.mean([v1, v2], axis=0)
    expected_centroid_doc2 = v3

    # The order of returned doc_ids is not guaranteed, so we sort them for consistent comparison.
    sorted_indices = np.argsort(doc_ids)
    sorted_ids = np.array(doc_ids)[sorted_indices]
    sorted_vectors = vectors[sorted_indices]

    assert sorted_ids.tolist() == ["doc1", "doc2"]
    np.testing.assert_allclose(sorted_vectors[0], expected_centroid_doc1, rtol=1e-5)
    np.testing.assert_allclose(sorted_vectors[1], expected_centroid_doc2, rtol=1e-5)
