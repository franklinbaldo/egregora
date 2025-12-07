"""TDD tests for WriterAgent - written BEFORE implementation.

Tests for V3 WriterAgent:
- Generates Document from entries using Pydantic-AI
- Uses async generator pattern for streaming
- Structured output with output_type=Document
- Mock-free testing with TestModel

Following TDD Red-Green-Refactor cycle.
"""

import ibis
import pytest

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Document, DocumentStatus, DocumentType, Entry
from egregora_v3.engine.agents.writer import WriterAgent
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository

# ========== Fixtures ==========


@pytest.fixture
def sample_entries() -> list[Entry]:
    """Create sample entries for testing."""
    return [
        Entry(
            id="entry-1",
            title="Python Tutorial",
            summary="Learn Python basics",
            updated="2025-12-06T10:00:00Z",
        ),
        Entry(
            id="entry-2",
            title="JavaScript Guide",
            summary="Modern JavaScript features",
            updated="2025-12-06T11:00:00Z",
        ),
    ]


@pytest.fixture
def content_library() -> ContentLibrary:
    """Create a content library for testing using in-memory DuckDB."""
    # Use in-memory DuckDB repositories for testing
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()

    return ContentLibrary(
        posts=repo,
        media=repo,
        profiles=repo,
        journal=repo,
        enrichments=repo,
    )


@pytest.fixture
def pipeline_context(content_library: ContentLibrary) -> PipelineContext:
    """Create pipeline context for testing."""
    return PipelineContext(
        library=content_library,
        run_id="test-run-123",
        metadata={"test": True},
    )


# ========== Basic Functionality Tests ==========


def test_writer_agent_initialization() -> None:
    """Test that WriterAgent can be initialized."""
    agent = WriterAgent(model="test")
    assert agent is not None


def test_writer_agent_has_generate_method() -> None:
    """Test that WriterAgent has generate method."""
    agent = WriterAgent(model="test")
    assert hasattr(agent, "generate")
    assert callable(agent.generate)


@pytest.mark.asyncio
async def test_writer_agent_generates_document(
    sample_entries: list[Entry],
    pipeline_context: PipelineContext,
) -> None:
    """Test that WriterAgent generates a Document from entries."""
    # Use TestModel for deterministic testing
    agent = WriterAgent(model="test")

    # Generate document (TestModel is already configured in __init__)
    result = await agent.generate(
        entries=sample_entries,
        context=pipeline_context,
    )

    # Verify result is a Document
    assert isinstance(result, Document)


@pytest.mark.asyncio
async def test_writer_agent_uses_test_model(content_library: ContentLibrary) -> None:
    """Test that WriterAgent works with TestModel (no live API calls)."""
    agent = WriterAgent(model="test")

    # Should not make any HTTP requests
    entries = [
        Entry(
            id="test-1",
            title="Test Entry",
            summary="Test summary",
            updated="2025-12-06T10:00:00Z",
        ),
    ]

    context = PipelineContext(library=content_library, run_id="test-run")

    # This should work without network access
    result = await agent.generate(entries=entries, context=context)

    # Verify basic properties
    assert isinstance(result, Document)
    assert result.doc_type == DocumentType.POST
    assert result.status == DocumentStatus.DRAFT


@pytest.mark.asyncio
async def test_writer_agent_structured_output(content_library: ContentLibrary) -> None:
    """Test that WriterAgent returns structured Document output."""
    agent = WriterAgent(model="test")

    entries = [
        Entry(
            id="test-1",
            title="Test",
            summary="Test summary",
            updated="2025-12-06T10:00:00Z",
        ),
    ]

    context = PipelineContext(library=content_library, run_id="test-run")

    result = await agent.generate(entries=entries, context=context)

    # Verify structured output fields
    assert isinstance(result, Document)
    assert result.title
    assert result.content
    assert result.doc_type == DocumentType.POST


# ========== Context Integration Tests ==========


@pytest.mark.asyncio
async def test_writer_agent_receives_pipeline_context(
    sample_entries: list[Entry],
    pipeline_context: PipelineContext,
) -> None:
    """Test that WriterAgent receives PipelineContext."""
    agent = WriterAgent(model="test")

    # Context should be passed through
    result = await agent.generate(
        entries=sample_entries,
        context=pipeline_context,
    )

    assert isinstance(result, Document)
    # Context is available during generation (tested via agent internals)


# ========== Edge Cases ==========


@pytest.mark.asyncio
async def test_writer_agent_handles_empty_entries(
    content_library: ContentLibrary,
) -> None:
    """Test that WriterAgent handles empty entry list."""
    agent = WriterAgent(model="test")
    context = PipelineContext(library=content_library, run_id="test-run")

    # Should handle gracefully
    with pytest.raises(ValueError, match="at least one entry"):
        await agent.generate(entries=[], context=context)


@pytest.mark.asyncio
async def test_writer_agent_handles_single_entry(
    content_library: ContentLibrary,
) -> None:
    """Test that WriterAgent handles single entry."""
    agent = WriterAgent(model="test")

    entries = [
        Entry(
            id="single",
            title="Single Entry",
            summary="Only one",
            updated="2025-12-06T10:00:00Z",
        ),
    ]

    context = PipelineContext(library=content_library, run_id="test-run")

    result = await agent.generate(entries=entries, context=context)

    assert isinstance(result, Document)
    assert result.title


# ========== Output Validation Tests ==========


@pytest.mark.asyncio
async def test_writer_agent_output_has_required_fields(
    content_library: ContentLibrary,
) -> None:
    """Test that generated Document has all required fields."""
    agent = WriterAgent(model="test")

    entries = [
        Entry(
            id="test-1",
            title="Test",
            summary="Test summary",
            updated="2025-12-06T10:00:00Z",
        ),
    ]

    context = PipelineContext(library=content_library, run_id="test-run")

    result = await agent.generate(entries=entries, context=context)

    # Check required fields
    assert result.id  # Generated ID
    assert result.title  # Non-empty title
    assert result.content  # Non-empty content
    assert result.doc_type == DocumentType.POST
    assert result.status == DocumentStatus.DRAFT
    assert result.updated  # Timestamp present


@pytest.mark.asyncio
async def test_writer_agent_generates_markdown_content(
    content_library: ContentLibrary,
) -> None:
    """Test that WriterAgent generates markdown content."""
    agent = WriterAgent(model="test")

    entries = [
        Entry(
            id="test-1",
            title="Test Post",
            summary="Test summary",
            updated="2025-12-06T10:00:00Z",
        ),
    ]

    context = PipelineContext(library=content_library, run_id="test-run")

    result = await agent.generate(entries=entries, context=context)

    # Content should be non-empty string
    assert isinstance(result.content, str)
    assert len(result.content) > 0
