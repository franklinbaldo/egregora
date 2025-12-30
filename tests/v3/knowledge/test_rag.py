"""Tests for V3 RAG chunking logic."""
from datetime import datetime, UTC
from egregora_v3.core.types import Document, DocumentType
from egregora_v3.knowledge.rag import RAGChunk, chunks_from_documents, simple_chunk_text


def test_simple_chunk_text_basic():
    """Test basic text chunking."""
    text = "This is a test sentence. This is another one."
    chunks = simple_chunk_text(text, max_chars=20, overlap=5)
    assert len(chunks) > 1
    assert chunks[0] == "This is a test"
    assert "test sentence." in chunks[1]


def test_simple_chunk_text_no_split():
    """Test text that doesn't need chunking."""
    text = "Short text."
    chunks = simple_chunk_text(text, max_chars=20, overlap=5)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_simple_chunk_text_empty():
    """Test empty text chunking."""
    text = ""
    chunks = simple_chunk_text(text)
    assert len(chunks) == 0


def test_chunks_from_documents_basic():
    """Test chunking from Document objects."""
    docs = [
        Document(id="doc1", title="Doc 1", updated=datetime.now(UTC), doc_type=DocumentType.POST, content="This is the first document."),
        Document(id="doc2", title="Doc 2", updated=datetime.now(UTC), doc_type=DocumentType.POST, content="This is the second document, which is a bit longer."),
    ]
    chunks = chunks_from_documents(docs, max_chars=20, chunk_overlap=5)
    assert len(chunks) > 1
    assert all(isinstance(c, RAGChunk) for c in chunks)
    # Check that the document IDs are correct for the chunks.
    assert chunks[0].document_id == "doc1"
    # The second document will also be chunked, so we expect to see chunks from it.
    assert any(c.document_id == "doc2" for c in chunks)


def test_chunks_from_documents_empty():
    """Test chunking from empty or content-less documents."""
    docs = [
        Document(id="doc1", title="Doc 1", updated=datetime.now(UTC), doc_type=DocumentType.POST, content=""),
        Document(id="doc2", title="Doc 2", updated=datetime.now(UTC), doc_type=DocumentType.POST, content=None),
    ]
    chunks = chunks_from_documents(docs)
    assert len(chunks) == 0
