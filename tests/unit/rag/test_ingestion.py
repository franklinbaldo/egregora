from datetime import datetime, timezone
import pytest
from egregora.data_primitives.document import Document, DocumentType
from egregora.rag.ingestion import chunks_from_document, chunks_from_documents

class TestIngestion:

    def test_chunk_post_document(self):
        doc = Document(
            type=DocumentType.POST,
            content="Hello World",
            metadata={"slug": "hello-world"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            suggested_path="post.md",
        )

        chunks = chunks_from_document(doc)
        assert len(chunks) == 1
        assert chunks[0].text == "Hello World"
        assert chunks[0].document_id == doc.document_id
        assert chunks[0].metadata["type"] == "post"

    def test_skip_non_indexable_types(self):
         doc = Document(
            type=DocumentType.MEDIA,
            content="some metadata",
            created_at=datetime.now(timezone.utc),
         )
         chunks = chunks_from_document(doc)
         assert len(chunks) == 0

    def test_skip_binary_content(self):
        doc = Document(
            type=DocumentType.POST,
            content=b"binary data",
            created_at=datetime.now(timezone.utc),
        )
        chunks = chunks_from_document(doc)
        assert len(chunks) == 0

    def test_custom_indexable_types(self):
         doc = Document(
            type=DocumentType.MEDIA,
            content="metadata",
            created_at=datetime.now(timezone.utc),
         )
         chunks = chunks_from_document(doc, indexable_types={DocumentType.MEDIA})
         assert len(chunks) == 1

    def test_metadata_inclusion(self):
         doc = Document(
            type=DocumentType.POST,
            content="text",
            created_at=datetime.now(timezone.utc),
            metadata={"extra": "value"}
         )
         chunks = chunks_from_document(doc)
         assert chunks[0].metadata["extra"] == "value"
         assert chunks[0].metadata["document_id"] == doc.document_id

    def test_multiple_chunks(self):
        text = "word " * 100
        doc = Document(
            type=DocumentType.POST,
            content=text,
            created_at=datetime.now(timezone.utc),
        )
        # Force small chunks
        chunks = chunks_from_document(doc, max_chars=50, chunk_overlap=10)
        assert len(chunks) > 1
        assert chunks[0].chunk_id.endswith(":0")
        assert chunks[1].chunk_id.endswith(":1")
        assert chunks[1].metadata["chunk_index"] == 1

    def test_chunks_from_documents(self):
        docs = [
            Document(type=DocumentType.POST, content="Doc 1", created_at=datetime.now(timezone.utc)),
            Document(type=DocumentType.POST, content="Doc 2", created_at=datetime.now(timezone.utc)),
        ]
        chunks = chunks_from_documents(docs)
        assert len(chunks) == 2
        assert chunks[0].text == "Doc 1"
        assert chunks[1].text == "Doc 2"
