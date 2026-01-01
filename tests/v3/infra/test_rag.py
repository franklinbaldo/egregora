from datetime import datetime, UTC

from egregora_v3.infra.rag import RAGChunk, chunks_from_documents
from egregora_v3.core.types import Document, DocumentType


def test_chunks_from_documents_happy_path():
    """Verify basic document to chunk conversion."""
    doc = Document(
        id="test-doc-1",
        title="Test Document",
        updated=datetime.now(UTC),
        doc_type=DocumentType.POST,
        content="This is the first sentence. This is the second sentence. This is the third sentence, which is a bit longer.",
        status="published",
        searchable=True,
    )

    chunks = chunks_from_documents([doc], max_chars=40, chunk_overlap=15)

    assert len(chunks) == 4
    assert all(isinstance(chunk, RAGChunk) for chunk in chunks)

    # Check chunk content and overlap
    assert chunks[0].text == "This is the first sentence. This is the"
    assert chunks[1].text == "This is the second sentence. This is"
    assert chunks[2].text == "This is the third sentence, which is a"
    assert chunks[3].text == "which is a bit longer."

    # Check metadata propagation
    first_chunk = chunks[0]
    assert first_chunk.document_id == "test-doc-1"
    assert first_chunk.chunk_id == "test-doc-1:0"
    assert first_chunk.metadata["title"] == "Test Document"
    assert first_chunk.metadata["doc_type"] == "post"
    assert first_chunk.metadata["status"] == "published"
    assert first_chunk.metadata["searchable"] is True
    assert first_chunk.metadata["chunk_index"] == 0

    assert chunks[1].chunk_id == "test-doc-1:1"
    assert chunks[2].chunk_id == "test-doc-1:2"
    assert chunks[3].chunk_id == "test-doc-1:3"


def test_chunks_from_documents_no_content():
    """Verify that documents with no content or empty content produce no chunks."""
    docs = [
        Document(
            id="doc-none",
            title="None Content",
            updated=datetime.now(UTC),
            doc_type=DocumentType.NOTE,
            content=None,
        ),
        Document(
            id="doc-empty",
            title="Empty Content",
            updated=datetime.now(UTC),
            doc_type=DocumentType.NOTE,
            content="",
        ),
    ]
    chunks = chunks_from_documents(docs)
    assert len(chunks) == 0


def test_chunks_from_documents_content_too_short():
    """Verify that content shorter than max_chars results in a single chunk."""
    content = "This content is shorter than the max characters."
    doc = Document(
        id="test-doc-short",
        title="Short Content",
        updated=datetime.now(UTC),
        doc_type=DocumentType.POST,
        content=content,
    )
    chunks = chunks_from_documents([doc], max_chars=100)
    assert len(chunks) == 1
    assert chunks[0].text == content
    assert chunks[0].document_id == "test-doc-short"


def test_chunks_from_multiple_documents():
    """Verify chunking of multiple documents in a single call."""
    doc1 = Document(
        id="d1", title="Doc 1", updated=datetime.now(UTC), doc_type=DocumentType.POST, content="A B C"
    )
    doc2 = Document(
        id="d2", title="Doc 2", updated=datetime.now(UTC), doc_type=DocumentType.NOTE, content="D E F"
    )

    chunks = chunks_from_documents([doc1, doc2], max_chars=2, chunk_overlap=0)
    assert len(chunks) == 6
    doc1_chunks = [c for c in chunks if c.document_id == "d1"]
    doc2_chunks = [c for c in chunks if c.document_id == "d2"]
    assert len(doc1_chunks) == 3
    assert len(doc2_chunks) == 3
    assert doc1_chunks[0].text == "A"
    assert doc2_chunks[0].text == "D"
