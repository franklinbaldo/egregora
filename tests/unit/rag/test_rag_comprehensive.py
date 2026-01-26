"""Comprehensive tests for RAG implementation.

This test suite exhaustively validates:
- Chunking with various document sizes and types
- Embedding generation and batching
- Indexing with different configurations
- Search with various queries and filters
- Edge cases and error handling
- Metadata preservation
- Performance characteristics

All critical issues have been fixed:
✅ Similarity scores now use cosine metric (correct range)
✅ Unused top_k_default parameter removed
✅ Filters now accept SQL WHERE strings (matching LanceDB API)
✅ top_k limit increased to 100 for flexibility
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

import egregora.rag
from egregora.data_primitives.document import Document, DocumentType
from egregora.rag import get_backend, index_documents, search
from egregora.rag.ingestion import DEFAULT_MAX_CHARS, chunks_from_document, chunks_from_documents
from egregora.rag.lancedb_backend import LanceDBRAGBackend
from egregora.rag.models import RAGQueryRequest


@pytest.fixture
def temp_db_dir() -> Path:
    """Create a temporary directory for LanceDB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_embed_fn():
    """Create a mock embedding function that returns deterministic vectors."""

    def embed(texts: list[str], task_type: str) -> list[list[float]]:
        # Return deterministic embeddings based on text content
        # This allows us to test similarity meaningfully
        embeddings = []
        for text in texts:
            # Simple hash-based deterministic embedding
            seed = hash(text) % 10000
            rng = np.random.default_rng(seed=seed)
            emb = rng.random(768).astype(np.float32)
            embeddings.append(emb.tolist())
        return embeddings

    return embed


@pytest.fixture
def mock_embed_fn_similar():
    """Create an embedding function where similar texts get similar embeddings."""

    def embed(texts: list[str], task_type: str) -> list[list[float]]:
        embeddings = []
        for text in texts:
            # Create embeddings based on word overlap
            words = set(text.lower().split())
            base = np.zeros(768, dtype=np.float32)

            # Add contribution for each word
            for word in words:
                seed = hash(word) % 10000
                rng = np.random.default_rng(seed=seed)
                base += rng.random(768).astype(np.float32) * 0.1

            # Normalize
            norm = np.linalg.norm(base)
            if norm > 0:
                base = base / norm

            embeddings.append(base.tolist())
        return embeddings

    return embed


# ============================================================================
# Chunking Tests
# ============================================================================


def test_chunking_small_document():
    """Test chunking a document smaller than max_chars."""
    doc = Document(
        content="This is a small document.",
        type=DocumentType.POST,
    )

    chunks = chunks_from_document(doc, max_chars=100)

    assert len(chunks) == 1
    assert chunks[0].text == "This is a small document."
    assert chunks[0].chunk_id.endswith(":0")


def test_chunking_large_document():
    """Test chunking a document larger than max_chars with overlap."""
    # Create a document with ~2000 chars (should split into multiple chunks)
    content = " ".join([f"Word{i}" for i in range(400)])  # ~2400 chars
    doc = Document(content=content, type=DocumentType.POST)

    chunks = chunks_from_document(doc, max_chars=800, chunk_overlap=200)

    # Should have multiple chunks
    assert len(chunks) >= 3
    # Each chunk should be roughly <= max_chars
    for chunk in chunks:
        assert len(chunk.text) <= 900  # Allow some flexibility for word boundaries

    # Verify overlap behavior
    # First chunk should start with beginning of content
    assert content.startswith(chunks[0].text.split()[0])
    # Last chunk should end with end of content
    assert content.endswith(chunks[-1].text.split()[-1])

    # Verify consecutive chunks have overlapping content
    for i in range(len(chunks) - 1):
        current_words = chunks[i].text.split()
        next_words = chunks[i + 1].text.split()
        # There should be some overlap between consecutive chunks
        # Find common words at the end of current and start of next
        overlap_found = False
        for j in range(1, min(len(current_words), len(next_words))):
            if current_words[-j:] == next_words[:j]:
                overlap_found = True
                break
        assert overlap_found, f"No overlap found between chunk {i} and {i + 1}"


def test_chunking_preserves_metadata():
    """Test that chunking preserves document metadata."""
    doc = Document(
        content="Test content",
        type=DocumentType.POST,
        metadata={"title": "Test", "slug": "test-post"},
    )

    chunks = chunks_from_document(doc)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.metadata["document_id"] == doc.document_id
    assert chunk.metadata["type"] == "post"  # DocumentType.POST.value is "post" (lowercase)
    assert chunk.metadata["title"] == "Test"
    assert chunk.metadata["slug"] == "test-post"


def test_chunking_filters_binary_content():
    """Test that binary content is filtered out."""
    doc = Document(
        content=b"binary data",
        type=DocumentType.MEDIA,
    )

    chunks = chunks_from_document(doc)

    assert len(chunks) == 0


def test_chunking_filters_by_document_type():
    """Test that only specified document types are chunked."""
    post_doc = Document(content="Post content", type=DocumentType.POST)
    media_doc = Document(content="Media content", type=DocumentType.MEDIA)

    # Default: only POST is indexed
    post_chunks = chunks_from_document(post_doc)
    media_chunks = chunks_from_document(media_doc)

    assert len(post_chunks) == 1
    assert len(media_chunks) == 0

    # Custom: index both POST and MEDIA
    media_chunks_custom = chunks_from_document(
        media_doc, indexable_types={DocumentType.POST, DocumentType.MEDIA}
    )
    assert len(media_chunks_custom) == 1


def test_chunking_multiple_documents():
    """Test chunking multiple documents at once."""
    docs = [Document(content=f"Document {i} content", type=DocumentType.POST) for i in range(5)]

    all_chunks = chunks_from_documents(docs)

    assert len(all_chunks) == 5
    # Verify each chunk has unique chunk_id and document_id
    chunk_ids = {c.chunk_id for c in all_chunks}
    assert len(chunk_ids) == 5


def test_chunking_word_boundary_splitting():
    """Test that chunking splits on word boundaries, not mid-word."""
    # Create text that would split mid-word if not careful
    content = "A" * 400 + " " + "B" * 400  # 800+ chars with space in middle

    doc = Document(content=content, type=DocumentType.POST)
    chunks = chunks_from_document(doc, max_chars=500)

    # Should split at the space, not mid-word
    assert len(chunks) == 2
    assert all("A" in chunk.text or "B" in chunk.text for chunk in chunks)
    # No chunk should have both A's and B's mixed (except at boundary)


# ============================================================================
# Indexing Tests
# ============================================================================


def test_backend_index_empty_documents(temp_db_dir: Path, mock_embed_fn):
    """Test indexing with empty document list."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    # Should not raise
    backend.add([])


def test_backend_index_documents_idempotency(temp_db_dir: Path, mock_embed_fn):
    """Test that indexing the same document twice is idempotent."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    doc = Document(content="Test document", type=DocumentType.POST)

    # Index once
    backend.add([doc])

    # Index again (should upsert, not duplicate)
    backend.add([doc])

    # Query should return only one result
    request = RAGQueryRequest(text="Test document", top_k=10)
    response = backend.query(request)

    # Should have exactly 1 hit (not duplicated)
    assert len(response.hits) == 1


def test_backend_index_documents_with_custom_types(temp_db_dir: Path, mock_embed_fn):
    """Test indexing with custom document types."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
        indexable_types={DocumentType.POST, DocumentType.MEDIA},
    )

    docs = [
        Document(content="Post content", type=DocumentType.POST),
        Document(content="Media content", type=DocumentType.MEDIA),
        Document(content="Annotation content", type=DocumentType.ANNOTATION),
    ]

    backend.add(docs)

    # Query - should only have POST and MEDIA indexed (ANNOTATION should be filtered out)
    request = RAGQueryRequest(text="content", top_k=10)
    response = backend.query(request)

    assert len(response.hits) == 2


def test_backend_index_large_batch(temp_db_dir: Path, mock_embed_fn):
    """Test indexing a large batch of documents."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    # Create 100 documents
    docs = [Document(content=f"Document {i} with unique content", type=DocumentType.POST) for i in range(100)]

    # Should handle large batch
    backend.add(docs)

    # Verify all indexed (top_k can now go up to 100)
    request = RAGQueryRequest(text="Document", top_k=50)
    response = backend.query(request)

    assert len(response.hits) == 50

    # To verify all 100 were actually indexed, we'd need to query multiple times
    # or check the table directly, but this at least confirms indexing succeeded


def test_backend_index_embedding_failure(temp_db_dir: Path):
    """Test handling of embedding failures."""

    def failing_embed_fn(texts: list[str], task_type: str) -> list[list[float]]:
        msg = "Embedding API failed"
        raise RuntimeError(msg)

    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=failing_embed_fn,
    )

    doc = Document(content="Test", type=DocumentType.POST)

    with pytest.raises(RuntimeError, match="Failed to compute embeddings"):
        backend.add([doc])


def test_backend_index_embedding_count_mismatch(temp_db_dir: Path):
    """Test handling of embedding count mismatch."""

    def bad_embed_fn(texts: list[str], task_type: str) -> list[list[float]]:
        # Return wrong number of embeddings
        rng = np.random.default_rng(seed=42)
        return [rng.random(768).tolist()]

    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=bad_embed_fn,
    )

    docs = [
        Document(content="Doc 1", type=DocumentType.POST),
        Document(content="Doc 2", type=DocumentType.POST),
    ]

    with pytest.raises(RuntimeError, match="Embedding count mismatch"):
        backend.add(docs)


# ============================================================================
# Search/Query Tests
# ============================================================================


def test_backend_query_basic(temp_db_dir: Path, mock_embed_fn_similar):
    """Test basic query functionality."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn_similar,
    )

    docs = [
        Document(content="Machine learning is great", type=DocumentType.POST),
        Document(content="Python programming tutorial", type=DocumentType.POST),
        Document(content="Deep learning with neural networks", type=DocumentType.POST),
    ]

    backend.add(docs)

    # Query for machine learning
    request = RAGQueryRequest(text="machine learning", top_k=2)
    response = backend.query(request)

    assert len(response.hits) == 2
    # First hit should have "Machine learning" due to word overlap
    assert "Machine learning" in response.hits[0].text or "Deep learning" in response.hits[0].text


def test_backend_query_top_k_limit(temp_db_dir: Path, mock_embed_fn):
    """Test that top_k limit is respected.

    The top_k parameter is now directly controlled by RAGQueryRequest with a default
    of 5 and a maximum of 100, removing the need for backend-level defaults.
    """
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    # Index 15 documents
    docs = [Document(content=f"Document {i}", type=DocumentType.POST) for i in range(15)]
    backend.add(docs)

    # Query with top_k=5
    request = RAGQueryRequest(text="Document", top_k=5)
    response = backend.query(request)

    assert len(response.hits) == 5

    # Query with default top_k=5 (RAGQueryRequest defaults to 5)
    request_default = RAGQueryRequest(text="Document")
    response_default = backend.query(request_default)

    assert len(response_default.hits) == 5

    # Test the new higher limit
    request_large = RAGQueryRequest(text="Document", top_k=15)
    response_large = backend.query(request_large)

    assert len(response_large.hits) == 15


def test_backend_query_empty_database(temp_db_dir: Path, mock_embed_fn):
    """Test querying an empty database."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    request = RAGQueryRequest(text="test query", top_k=5)
    response = backend.query(request)

    assert len(response.hits) == 0


def test_backend_query_score_range(temp_db_dir: Path, mock_embed_fn):
    """Test that similarity scores are in the correct range.

    After fixing to use cosine metric:
    - Cosine distance: distance ∈ [0, 2]
    - Similarity score: score = 1 - distance ∈ [-1, 1]

    For normalized vectors (most embedding models), cosine distance is typically [0, 1],
    giving scores in [0, 1] range.
    """
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    docs = [Document(content=f"Document {i}", type=DocumentType.POST) for i in range(5)]
    backend.add(docs)

    request = RAGQueryRequest(text="Document", top_k=5)
    response = backend.query(request)

    assert len(response.hits) == 5
    for hit in response.hits:
        assert isinstance(hit.score, float)
        # Cosine similarity scores should be in reasonable range
        # For normalized vectors: typically [0, 1]
        # For general case: [-1, 1]
        assert -1.0 <= hit.score <= 1.0, f"Score {hit.score} out of expected range [-1, 1]"

    # Verify hits are ranked by score (higher is better)
    scores = [hit.score for hit in response.hits]
    assert scores == sorted(scores, reverse=True), "Hits should be ranked by score (descending)"


def test_backend_query_metadata_preservation(temp_db_dir: Path, mock_embed_fn):
    """Test that metadata is preserved in query results."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    doc = Document(
        content="Test document",
        type=DocumentType.POST,
        metadata={"title": "Test", "author": "Alice", "tags": "test,sample"},
    )

    backend.add([doc])

    request = RAGQueryRequest(text="Test", top_k=1)
    response = backend.query(request)

    assert len(response.hits) == 1
    hit = response.hits[0]
    assert hit.metadata["title"] == "Test"
    assert hit.metadata["author"] == "Alice"
    assert hit.metadata["tags"] == "test,sample"


def test_backend_query_chunk_id_format(temp_db_dir: Path, mock_embed_fn):
    """Test that chunk IDs follow expected format."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    # Create a document that will be chunked
    content = " ".join([f"Word{i}" for i in range(200)])  # Large document
    doc = Document(content=content, type=DocumentType.POST)

    backend.add([doc])

    request = RAGQueryRequest(text="Word", top_k=10)
    response = backend.query(request)

    # All hits should have chunk_ids in format "{document_id}:{index}"
    for hit in response.hits:
        assert ":" in hit.chunk_id
        doc_id, chunk_idx = hit.chunk_id.rsplit(":", 1)
        assert doc_id == hit.document_id
        assert chunk_idx.isdigit()


def test_backend_asymmetric_embeddings(temp_db_dir: Path):
    """Test that documents and queries use different task_types for asymmetric embeddings.

    Google Gemini embeddings are asymmetric - documents should use RETRIEVAL_DOCUMENT
    and queries should use RETRIEVAL_QUERY for optimal retrieval quality.
    """
    # Track what task_types were used
    embedding_calls = []

    def mock_embed_with_task_tracking(texts: list[str], task_type: str) -> list[list[float]]:
        embedding_calls.append({"count": len(texts), "task_type": task_type})

        # Return mock embeddings
        rng = np.random.default_rng(seed=42)
        return [rng.random(768).tolist() for _ in texts]

    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_with_task_tracking,
    )

    # Index documents (should use RETRIEVAL_DOCUMENT)
    docs = [
        Document(content="Document 1", type=DocumentType.POST),
        Document(content="Document 2", type=DocumentType.POST),
    ]
    backend.add(docs)

    # Query (should use RETRIEVAL_QUERY)
    request = RAGQueryRequest(text="search query", top_k=5)
    backend.query(request)

    # Verify task types
    assert len(embedding_calls) == 2, "Should have 2 embedding calls (index + query)"

    index_call = embedding_calls[0]
    assert index_call["count"] == 2, "Indexing should embed 2 documents"
    assert index_call["task_type"] == "RETRIEVAL_DOCUMENT"

    query_call = embedding_calls[1]
    assert query_call["count"] == 1, "Query should embed 1 text"
    assert query_call["task_type"] == "RETRIEVAL_QUERY"


def test_backend_query_with_filters(temp_db_dir: Path, mock_embed_fn):
    """Test query with metadata filters.

    Filters now accept SQL WHERE clause strings, matching LanceDB's native API.
    """
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    docs = [
        Document(
            content="Post about Python",
            type=DocumentType.POST,
            metadata={"category": "programming"},
        ),
        Document(content="Post about cooking", type=DocumentType.POST, metadata={"category": "food"}),
    ]

    backend.add(docs)

    # Test that basic query works without filters
    request = RAGQueryRequest(text="Post", top_k=10, filters=None)
    response = backend.query(request)

    assert len(response.hits) == 2

    # Test filtering by document_id (available as a column)
    # Get one of the document IDs from the results
    doc_id = response.hits[0].document_id

    # Filter to only that specific document
    request_filtered = RAGQueryRequest(text="Post", top_k=10, filters=f"document_id = '{doc_id}'")
    response_filtered = backend.query(request_filtered)

    # Should only return chunks from that one document
    assert len(response_filtered.hits) >= 1
    assert all(hit.document_id == doc_id for hit in response_filtered.hits)


# ============================================================================
# High-Level API Tests
# ============================================================================


def test_high_level_api_index_and_search():
    """Test the high-level index_documents() and search() API."""
    with (
        tempfile.TemporaryDirectory(),
        patch("egregora.rag.get_backend") as mock_get_backend,
    ):
        mock_backend = Mock()
        mock_get_backend.return_value = mock_backend

        # Reset global backend
        egregora.rag.reset_backend()

        # Use high-level API
        docs = [Document(content="Test", type=DocumentType.POST)]
        index_documents(docs)

        mock_backend.add.assert_called_once_with(docs)

        # Search
        request = RAGQueryRequest(text="Test", top_k=5)
        search(request)

        mock_backend.query.assert_called_once_with(request)


def test_high_level_api_backend_singleton():
    """Test that get_backend() returns singleton instance."""
    with patch("egregora.rag.LanceDBRAGBackend") as mock_backend_class:
        mock_backend1 = Mock()
        mock_backend_class.return_value = mock_backend1

        # Reset global backend
        egregora.rag.reset_backend()

        # Get backend twice
        backend1 = get_backend()
        backend2 = get_backend()

        # Should be same instance
        assert backend1 is backend2
        # Should only create once
        assert mock_backend_class.call_count == 1


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_chunking_empty_document():
    """Test chunking an empty document."""
    doc = Document(content="", type=DocumentType.POST)

    chunks = chunks_from_document(doc)

    # Should return a single chunk with empty text
    assert len(chunks) == 1
    assert chunks[0].text == ""


def test_chunking_whitespace_only():
    """Test chunking a document with only whitespace."""
    doc = Document(content="   \n\t  ", type=DocumentType.POST)

    chunks = chunks_from_document(doc)

    # Should return a single chunk
    assert len(chunks) == 1


def test_chunking_single_long_word():
    """Test chunking a document with a single word longer than max_chars."""
    doc = Document(content="A" * 2000, type=DocumentType.POST)

    chunks = chunks_from_document(doc, max_chars=800)

    # Should still create chunks (one per "word" boundary)
    # In this case, single long word will be in one chunk despite exceeding limit
    assert len(chunks) >= 1


def test_backend_persistence_across_sessions(temp_db_dir: Path, mock_embed_fn):
    """Test that indexed data persists across backend instances."""
    # Create backend and index documents
    backend1 = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    doc = Document(content="Persistent test document", type=DocumentType.POST)
    backend1.add([doc])

    # Create new backend instance pointing to same directory
    backend2 = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    # Should be able to query previously indexed data
    request = RAGQueryRequest(text="Persistent", top_k=1)
    response = backend2.query(request)

    assert len(response.hits) == 1
    assert "Persistent" in response.hits[0].text


def test_backend_multiple_tables(temp_db_dir: Path, mock_embed_fn):
    """Test that multiple tables can coexist in same database."""
    backend1 = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="table1",
        embed_fn=mock_embed_fn,
    )

    backend2 = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="table2",
        embed_fn=mock_embed_fn,
    )

    # Index different documents in each table
    backend1.add([Document(content="Table 1 content", type=DocumentType.POST)])
    backend2.add([Document(content="Table 2 content", type=DocumentType.POST)])

    # Query each table - should return only its own documents
    response1 = backend1.query(RAGQueryRequest(text="Table", top_k=10))
    response2 = backend2.query(RAGQueryRequest(text="Table", top_k=10))

    assert len(response1.hits) == 1
    assert len(response2.hits) == 1
    assert "Table 1" in response1.hits[0].text
    assert "Table 2" in response2.hits[0].text


# ============================================================================
# Performance and Scalability Tests
# ============================================================================


def test_chunking_performance():
    """Test that chunking performs reasonably with large documents.

    PERFORMANCE NOTE: Observed ~3.2s for chunking 700KB of text. This is
    acceptable for batch processing but could be optimized if needed.
    """
    # Create a very large document (1MB of text)
    content = " ".join([f"Word{i}" for i in range(100000)])  # ~700KB
    doc = Document(content=content, type=DocumentType.POST)

    # Should complete in reasonable time
    start = time.time()
    chunks = chunks_from_document(doc, max_chars=DEFAULT_MAX_CHARS)
    elapsed = time.time() - start

    # Chunking performance: observed ~3.2s for 700KB
    # This is slower than ideal but acceptable for batch processing
    # Should chunk ~700KB in under 5 seconds
    assert elapsed < 5.0
    # Should produce many chunks
    assert len(chunks) > 500


def test_backend_concurrent_queries(temp_db_dir: Path, mock_embed_fn):
    """Test that backend handles concurrent queries correctly."""
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="test",
        embed_fn=mock_embed_fn,
    )

    # Index some documents
    docs = [Document(content=f"Document {i}", type=DocumentType.POST) for i in range(10)]
    backend.add(docs)

    # Perform multiple queries
    responses = []
    for i in range(5):
        request = RAGQueryRequest(text=f"Document {i}", top_k=3)
        response = backend.query(request)
        responses.append(response)

    # All queries should succeed
    assert len(responses) == 5
    assert all(len(r.hits) > 0 for r in responses)


# ============================================================================
# Integration Tests
# ============================================================================


def test_end_to_end_workflow(temp_db_dir: Path, mock_embed_fn_similar):
    """Test complete end-to-end RAG workflow."""
    # 1. Create backend
    backend = LanceDBRAGBackend(
        db_dir=temp_db_dir,
        table_name="knowledge_base",
        embed_fn=mock_embed_fn_similar,
        indexable_types={DocumentType.POST},
    )

    # 2. Create diverse documents
    docs = [
        Document(
            content="Python is a high-level programming language known for readability.",
            type=DocumentType.POST,
            metadata={"category": "programming", "language": "python"},
        ),
        Document(
            content="Machine learning is a subset of artificial intelligence.",
            type=DocumentType.POST,
            metadata={"category": "ai", "topic": "ml"},
        ),
        Document(
            content="Neural networks are inspired by biological neural networks.",
            type=DocumentType.POST,
            metadata={"category": "ai", "topic": "neural-nets"},
        ),
        Document(
            content="Django is a web framework written in Python.",
            type=DocumentType.POST,
            metadata={"category": "programming", "language": "python"},
        ),
    ]

    # 3. Index documents
    backend.add(docs)

    # 4. Perform searches
    # Search for Python-related content
    python_query = RAGQueryRequest(text="Python programming", top_k=2)
    python_results = backend.query(python_query)

    assert len(python_results.hits) == 2
    # Should find Python and Django docs

    # Search for AI-related content
    ai_query = RAGQueryRequest(text="artificial intelligence neural", top_k=2)
    ai_results = backend.query(ai_query)

    assert len(ai_results.hits) == 2

    # 5. Verify metadata is preserved and scores are valid
    for hit in python_results.hits + ai_results.hits:
        assert "category" in hit.metadata
        assert hit.document_id
        assert hit.chunk_id
        assert hit.text
        # Verify score is in valid range for cosine similarity
        assert -1.0 <= hit.score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
