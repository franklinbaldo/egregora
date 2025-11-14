"""Unit tests for chunked RAG context building.

Tests the new chunked RAG augmentation implementation:
- consolidate_messages_to_markdown()
- deduplicate_by_document()
- query_rag_per_chunk()
"""

from __future__ import annotations

from datetime import datetime, timezone

import ibis
import pytest

from egregora.agents.writer.context_builder import consolidate_messages_to_markdown, deduplicate_by_document


class TestConsolidateMessagesToMarkdown:
    """Tests for consolidate_messages_to_markdown()."""

    def test_empty_table(self):
        """Empty table returns empty string."""
        table = ibis.memtable([], schema={"timestamp": "timestamp", "author": "string", "message": "string"})
        result = consolidate_messages_to_markdown(table)
        assert result == ""

    def test_single_message(self):
        """Single message formats correctly."""
        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        table = ibis.memtable(
            [{"timestamp": dt, "author": "uuid-123", "message": "Hello world"}],
            schema={"timestamp": "timestamp", "author": "string", "message": "string"},
        )
        result = consolidate_messages_to_markdown(table)

        assert "## Message 1" in result
        assert "**Author:** uuid-123" in result
        assert "**Timestamp:**" in result
        assert "Hello world" in result

    def test_multiple_messages(self):
        """Multiple messages format correctly with proper numbering."""
        dt1 = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 15, 10, 35, 0, tzinfo=timezone.utc)
        dt3 = datetime(2025, 1, 15, 10, 40, 0, tzinfo=timezone.utc)
        table = ibis.memtable(
            [
                {"timestamp": dt1, "author": "uuid-123", "message": "First message"},
                {"timestamp": dt2, "author": "uuid-456", "message": "Second message"},
                {"timestamp": dt3, "author": "uuid-789", "message": "Third message"},
            ],
            schema={"timestamp": "timestamp", "author": "string", "message": "string"},
        )
        result = consolidate_messages_to_markdown(table)

        assert "## Message 1" in result
        assert "## Message 2" in result
        assert "## Message 3" in result
        assert "uuid-123" in result
        assert "uuid-456" in result
        assert "uuid-789" in result
        assert "First message" in result
        assert "Second message" in result
        assert "Third message" in result

    def test_message_with_multiline_content(self):
        """Messages with multiple lines preserve formatting."""
        multiline_message = "Line 1\nLine 2\nLine 3"
        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        table = ibis.memtable(
            [{"timestamp": dt, "author": "uuid-123", "message": multiline_message}],
            schema={"timestamp": "timestamp", "author": "string", "message": "string"},
        )
        result = consolidate_messages_to_markdown(table)

        assert "Line 1\nLine 2\nLine 3" in result

    def test_paragraph_boundaries(self):
        """Output has paragraph boundaries (double newlines) for chunking."""
        dt1 = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 15, 10, 35, 0, tzinfo=timezone.utc)
        table = ibis.memtable(
            [
                {"timestamp": dt1, "author": "uuid-123", "message": "Message 1"},
                {"timestamp": dt2, "author": "uuid-456", "message": "Message 2"},
            ],
            schema={"timestamp": "timestamp", "author": "string", "message": "string"},
        )
        result = consolidate_messages_to_markdown(table)

        # Should have double newlines between messages for paragraph-based chunking
        assert "\n\n" in result


class TestDeduplicateByDocument:
    """Tests for deduplicate_by_document()."""

    def test_empty_list(self):
        """Empty list returns empty list."""
        result = deduplicate_by_document([])
        assert result == []

    def test_single_document(self):
        """Single document returns as-is."""
        results = [{"document_id": "post-123", "similarity": 0.90, "content": "chunk 0"}]
        deduped = deduplicate_by_document(results, n=1)

        assert len(deduped) == 1
        assert deduped[0]["document_id"] == "post-123"
        assert deduped[0]["similarity"] == 0.90

    def test_keeps_top_1_per_document(self):
        """Keeps only highest-scoring chunk per document (n=1)."""
        results = [
            {"document_id": "post-123", "similarity": 0.90, "content": "chunk 0"},
            {"document_id": "post-123", "similarity": 0.85, "content": "chunk 1"},
            {"document_id": "post-456", "similarity": 0.88, "content": "chunk 0"},
            {"document_id": "post-456", "similarity": 0.82, "content": "chunk 1"},
        ]
        deduped = deduplicate_by_document(results, n=1)

        assert len(deduped) == 2

        # Find post-123 and post-456 in results
        post_123 = [r for r in deduped if r["document_id"] == "post-123"][0]
        post_456 = [r for r in deduped if r["document_id"] == "post-456"][0]

        assert post_123["similarity"] == 0.90  # Highest for post-123
        assert post_456["similarity"] == 0.88  # Highest for post-456

    def test_keeps_top_2_per_document(self):
        """Keeps top-2 chunks per document when n=2."""
        results = [
            {"document_id": "post-123", "similarity": 0.90, "content": "chunk 0"},
            {"document_id": "post-123", "similarity": 0.85, "content": "chunk 1"},
            {"document_id": "post-123", "similarity": 0.80, "content": "chunk 2"},
        ]
        deduped = deduplicate_by_document(results, n=2)

        assert len(deduped) == 2
        assert deduped[0]["similarity"] in (0.90, 0.85)
        assert deduped[1]["similarity"] in (0.90, 0.85)
        # Chunk 2 (0.80) should be excluded

    def test_handles_missing_document_id(self):
        """Results without document_id are excluded."""
        results = [
            {"document_id": "post-123", "similarity": 0.90, "content": "chunk 0"},
            {"similarity": 0.95, "content": "chunk without doc_id"},  # Missing document_id
        ]
        deduped = deduplicate_by_document(results, n=1)

        # Only the one with document_id should be kept
        assert len(deduped) == 1
        assert deduped[0]["document_id"] == "post-123"

    def test_handles_missing_similarity(self):
        """Results without similarity default to 0.0 for sorting."""
        results = [
            {"document_id": "post-123", "similarity": 0.90, "content": "chunk 0"},
            {"document_id": "post-123", "content": "chunk without similarity"},  # Missing similarity
        ]
        deduped = deduplicate_by_document(results, n=1)

        # Should keep the one with explicit similarity (0.90)
        assert len(deduped) == 1
        assert deduped[0]["similarity"] == 0.90

    def test_different_documents(self):
        """Different documents are kept separately."""
        results = [
            {"document_id": "post-123", "similarity": 0.90, "content": "chunk 0"},
            {"document_id": "post-456", "similarity": 0.88, "content": "chunk 0"},
            {"document_id": "post-789", "similarity": 0.85, "content": "chunk 0"},
        ]
        deduped = deduplicate_by_document(results, n=1)

        assert len(deduped) == 3
        doc_ids = {r["document_id"] for r in deduped}
        assert doc_ids == {"post-123", "post-456", "post-789"}


class TestQueryRagPerChunk:
    """Tests for query_rag_per_chunk().

    Integration tests using VCR are in tests/integration/test_rag_chunked.py
    These are basic unit tests to verify function signature and error handling.
    """

    def test_empty_chunks_list(self):
        """Empty chunks list returns empty results."""
        # This is a mock test - real implementation would need VectorStore
        # Real tests are in integration tests with VCR
        pytest.skip("Requires VectorStore mock or VCR - see integration tests")

    def test_function_exists_and_callable(self):
        """Verify function exists and has correct signature."""
        from egregora.agents.writer.context_builder import query_rag_per_chunk

        assert callable(query_rag_per_chunk)
        # Verify signature (will fail if signature changes)
        import inspect

        sig = inspect.signature(query_rag_per_chunk)
        params = list(sig.parameters.keys())
        assert "chunks" in params
        assert "store" in params
        assert "embedding_model" in params
        assert "top_k" in params
