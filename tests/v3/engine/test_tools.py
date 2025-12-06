"""Tests for agent tools with dependency injection.

Tests tool functions that use PipelineContext to access:
- ContentLibrary repositories
- Vector store for RAG search
- Pipeline metadata

Following TDD Red-Green-Refactor cycle.
"""

import ibis
import pytest

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Document, DocumentType
from egregora_v3.engine.tools import (
    get_recent_posts,
    search_prior_work,
    get_document_by_id,
    count_documents_by_type,
    get_pipeline_metadata,
)
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository


@pytest.fixture
def content_library() -> ContentLibrary:
    """Create a content library for testing using in-memory DuckDB."""
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()

    return ContentLibrary(
        posts=repo,
        media=repo,
        journal=repo,
        profiles=repo,
        enrichments=repo,
    )


@pytest.fixture
def pipeline_context(content_library: ContentLibrary) -> PipelineContext:
    """Create pipeline context for testing."""
    return PipelineContext(
        library=content_library,
        run_id="test-run-123",
        metadata={"source": "test", "batch_size": 5},
    )


@pytest.fixture
def sample_documents(content_library: ContentLibrary) -> list[Document]:
    """Create sample documents in the library."""
    docs = [
        Document.create(
            title=f"Test Post {i}",
            content=f"Content for post {i}",
            doc_type=DocumentType.POST,
        )
        for i in range(5)
    ]

    # Save to repository
    for doc in docs:
        content_library.posts.save(doc)

    return docs


# ========== Tool Tests ==========


@pytest.mark.asyncio
async def test_get_recent_posts_basic(
    pipeline_context: PipelineContext,
    sample_documents: list[Document],
) -> None:
    """Test get_recent_posts returns recent posts from library."""
    # Get recent posts
    posts = await get_recent_posts(pipeline_context, limit=3)

    # Should return 3 most recent posts
    assert len(posts) == 3
    assert all(isinstance(p, Document) for p in posts)
    assert all(p.doc_type == DocumentType.POST for p in posts)


@pytest.mark.asyncio
async def test_get_recent_posts_respects_limit(
    pipeline_context: PipelineContext,
    sample_documents: list[Document],
) -> None:
    """Test get_recent_posts respects the limit parameter."""
    # Tools now accept PipelineContext directly

    # Get different limits
    posts_1 = await get_recent_posts(pipeline_context, limit=1)
    posts_5 = await get_recent_posts(pipeline_context, limit=5)

    assert len(posts_1) == 1
    assert len(posts_5) == 5


@pytest.mark.asyncio
async def test_get_recent_posts_empty_library(
    pipeline_context: PipelineContext,
) -> None:
    """Test get_recent_posts with empty library returns empty list."""
    # Tools now accept PipelineContext directly

    posts = await get_recent_posts(pipeline_context, limit=10)

    assert posts == []


@pytest.mark.asyncio
async def test_search_prior_work_basic(
    pipeline_context: PipelineContext,
    sample_documents: list[Document],
) -> None:
    """Test search_prior_work searches vector store."""
    # Tools now accept PipelineContext directly

    # Note: This is a basic test - actual vector search would require
    # embeddings and a configured vector store
    results = await search_prior_work(pipeline_context, query="test post", limit=3)

    # Should return list (may be empty without vector store configured)
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)


@pytest.mark.asyncio
async def test_get_document_by_id_success(
    pipeline_context: PipelineContext,
    sample_documents: list[Document],
) -> None:
    """Test get_document_by_id retrieves document by ID."""
    # Tools now accept PipelineContext directly
    doc_id = sample_documents[0].id

    # Get document by ID
    doc = await get_document_by_id(pipeline_context, doc_id=doc_id)

    assert doc is not None
    assert doc.id == doc_id
    assert doc.title == sample_documents[0].title


@pytest.mark.asyncio
async def test_get_document_by_id_not_found(
    pipeline_context: PipelineContext,
) -> None:
    """Test get_document_by_id returns None for non-existent ID."""
    # Tools now accept PipelineContext directly

    doc = await get_document_by_id(pipeline_context, doc_id="non-existent-id")

    assert doc is None


@pytest.mark.asyncio
async def test_count_documents_by_type(
    pipeline_context: PipelineContext,
    sample_documents: list[Document],
) -> None:
    """Test count_documents_by_type returns document counts."""
    # Tools now accept PipelineContext directly

    # Count posts
    post_count = await count_documents_by_type(pipeline_context, doc_type=DocumentType.POST)

    assert post_count == 5  # We created 5 posts in fixture


@pytest.mark.asyncio
async def test_count_documents_by_type_zero(
    pipeline_context: PipelineContext,
    sample_documents: list[Document],
) -> None:
    """Test count_documents_by_type returns 0 for types with no documents."""
    # Tools now accept PipelineContext directly

    # Count media (we didn't create any)
    media_count = await count_documents_by_type(pipeline_context, doc_type=DocumentType.MEDIA)

    assert media_count == 0


@pytest.mark.asyncio
async def test_get_pipeline_metadata(
    pipeline_context: PipelineContext,
) -> None:
    """Test get_pipeline_metadata returns current pipeline metadata."""
    # Tools now accept PipelineContext directly

    metadata = await get_pipeline_metadata(pipeline_context)

    assert metadata["run_id"] == "test-run-123"
    assert metadata["source"] == "test"
    assert metadata["batch_size"] == 5


# ========== Integration Tests ==========


@pytest.mark.asyncio
async def test_tools_access_same_library(
    pipeline_context: PipelineContext,
    sample_documents: list[Document],
) -> None:
    """Test that multiple tools access the same ContentLibrary instance."""
    # Tools now accept PipelineContext directly

    # Get count before and after
    count_before = await count_documents_by_type(pipeline_context, doc_type=DocumentType.POST)

    # Add a new document through the context library
    new_doc = Document.create(
        title="New Post",
        content="New content",
        doc_type=DocumentType.POST,
    )
    pipeline_context.library.posts.save(new_doc)

    # Count should increase
    count_after = await count_documents_by_type(pipeline_context, doc_type=DocumentType.POST)

    assert count_after == count_before + 1


@pytest.mark.asyncio
async def test_tools_share_pipeline_context(
    pipeline_context: PipelineContext,
) -> None:
    """Test that tools can access shared pipeline context."""
    # Tools now accept PipelineContext directly

    # Get metadata
    metadata = await get_pipeline_metadata(pipeline_context)

    # Verify it matches what we set
    assert metadata["run_id"] == pipeline_context.run_id
    assert metadata == {**pipeline_context.metadata, "run_id": pipeline_context.run_id}
