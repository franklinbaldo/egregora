import shutil
from pathlib import Path

import pytest
import numpy as np
from egregora_v3.infra.vector.lancedb import LanceDBVectorStore
from egregora_v3.core.search import RAGQueryRequest
from egregora_v3.core.types import Document, DocumentType

def mock_embed_fn(texts, task_type):
    # Return random vectors of dim 768
    return [np.random.rand(768).tolist() for _ in texts]

@pytest.fixture
def vector_store(tmp_path):
    db_dir = tmp_path / "lancedb"
    return LanceDBVectorStore(
        db_dir=db_dir,
        table_name="test_vectors",
        embed_fn=mock_embed_fn,
        indexable_types={"post"}
    )

def test_add_and_query_v3_store(vector_store):
    # Create V3 Document
    doc = Document.create(
        content="This is a test document content that is long enough to be chunked maybe.",
        doc_type=DocumentType.POST,
        title="Test Doc",
        id_override="doc-1"
    )

    # Add
    count = vector_store.add([doc])
    assert count == 1
    assert vector_store.count() > 0

    # Query
    req = RAGQueryRequest(text="test", top_k=1)
    res = vector_store.query(req)

    assert len(res.hits) == 1
    assert res.hits[0].document_id == "doc-1"
    assert "test document" in res.hits[0].text

def test_delete_v3_store(vector_store):
    doc = Document.create(
        content="Delete me",
        doc_type=DocumentType.POST,
        title="Delete Test",
        id_override="del-1"
    )
    vector_store.add([doc])
    assert vector_store.count() > 0

    vector_store.delete(["del-1"])
    assert vector_store.count() == 0

def test_get_all_post_vectors(vector_store):
    doc1 = Document.create(content="Doc 1", doc_type=DocumentType.POST, title="Doc1", id_override="d1")
    doc2 = Document.create(content="Doc 2", doc_type=DocumentType.POST, title="Doc2", id_override="d2")

    vector_store.add([doc1, doc2])

    ids, vecs = vector_store.get_all_post_vectors()

    assert len(ids) == 2
    assert "d1" in ids
    assert "d2" in ids
    assert vecs.shape == (2, 768)
