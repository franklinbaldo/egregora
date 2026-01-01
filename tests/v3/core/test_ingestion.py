from datetime import UTC, datetime
from egregora_v3.core.ingestion import chunks_from_documents
from egregora_v3.core.types import Document, DocumentType, RAGChunk


def test_chunks_from_documents_basic():
    # Arrange
    doc = Document(
        id="test-doc-1",
        title="Test Document",
        updated=datetime.now(UTC),
        content="This is the first sentence. This is the second sentence.",
        doc_type=DocumentType.NOTE,
        internal_metadata={"source": "test"},
    )
    docs = [doc]

    # Act
    # The text is 56 chars. `simple_chunk_text` will create two chunks.
    # 1. "This is the first sentence. This"
    # 2. "is the second sentence."
    chunks = chunks_from_documents(docs, max_chars=35, chunk_overlap=10)

    # Assert
    assert len(chunks) == 2
    assert all(isinstance(chunk, RAGChunk) for chunk in chunks)

    # Check first chunk
    assert chunks[0].chunk_id == "test-doc-1:0"
    assert chunks[0].document_id == "test-doc-1"
    assert chunks[0].text == "This is the first sentence. This"
    assert chunks[0].metadata["title"] == "Test Document"
    assert "content" not in chunks[0].metadata
    assert chunks[0].metadata["internal_metadata"]["source"] == "test"
    assert chunks[0].metadata["chunk_index"] == 0

    # Check second chunk (and overlap)
    assert chunks[1].chunk_id == "test-doc-1:1"
    assert chunks[1].text == "This is the second sentence."
    assert chunks[1].metadata["chunk_index"] == 1


def test_chunks_from_documents_empty_and_invalid_content():
    # Arrange
    docs = [
        Document(id="doc-1", title="Doc 1", updated=datetime.now(UTC), content="", doc_type=DocumentType.NOTE),
        Document(id="doc-2", title="Doc 2", updated=datetime.now(UTC), content=None, doc_type=DocumentType.NOTE),
        Document(id="doc-4", title="Doc 4", updated=datetime.now(UTC), content="This is valid.", doc_type=DocumentType.NOTE),
    ]

    # Act
    chunks = chunks_from_documents(docs)

    # Assert
    assert len(chunks) == 1
    assert chunks[0].document_id == "doc-4"
