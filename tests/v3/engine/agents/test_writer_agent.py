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
from egregora_v3.core.types import Entry
from egregora_v3.engine.agents.writer import GeneratedPost, WriterAgent
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
async def test_writer_agent_generates_generated_post(
    sample_entries: list[Entry],
    pipeline_context: PipelineContext,
) -> None:
    """Test that WriterAgent generates a GeneratedPost from entries."""
    agent = WriterAgent(model="test")

    result = await agent.generate(
        entries=sample_entries,
        context=pipeline_context,
    )

    assert isinstance(result, GeneratedPost)
    assert "Generated Blog Post" in result.title


@pytest.mark.asyncio
async def test_writer_agent_uses_test_model(content_library: ContentLibrary) -> None:
    """Test that WriterAgent works with TestModel (no live API calls)."""
    agent = WriterAgent(model="test")

    entries = [
        Entry(
            id="test-1",
            title="Test Entry",
            summary="Test summary",
            updated="2025-12-06T10:00:00Z",
        ),
    ]
    context = PipelineContext(library=content_library, run_id="test-run")

    result = await agent.generate(entries=entries, context=context)

    assert isinstance(result, GeneratedPost)
    assert "Generated Blog Post" in result.title


@pytest.mark.asyncio
async def test_writer_agent_structured_output(content_library: ContentLibrary) -> None:
    """Test that WriterAgent returns structured GeneratedPost output."""
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

    assert isinstance(result, GeneratedPost)
    assert result.title
    assert result.content


# ========== Context Integration Tests ==========


@pytest.mark.asyncio
async def test_writer_agent_receives_pipeline_context(
    sample_entries: list[Entry],
    pipeline_context: PipelineContext,
) -> None:
    """Test that WriterAgent receives PipelineContext."""
    agent = WriterAgent(model="test")

    result = await agent.generate(
        entries=sample_entries,
        context=pipeline_context,
    )

    assert isinstance(result, GeneratedPost)


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

    assert isinstance(result, GeneratedPost)
    assert result.title


# ========== Output Validation Tests ==========


@pytest.mark.asyncio
async def test_writer_agent_output_has_required_fields(
    content_library: ContentLibrary,
) -> None:
    """Test that generated GeneratedPost has all required fields."""
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

    assert result.title
    assert result.content


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


class TestWriterAgentInterface:
    """Test the public interface of the WriterAgent."""

    @pytest.mark.asyncio
    async def test_generate_returns_generated_post(
        self, sample_entries: list[Entry], pipeline_context: PipelineContext
    ) -> None:
        """Generate should return a GeneratedPost object, not a Document."""
        agent = WriterAgent(model="test")
        result = await agent.generate(sample_entries, pipeline_context)

        assert isinstance(result, GeneratedPost)
        assert result.title
        assert "Generated Blog Post" in result.title
        assert result.content
