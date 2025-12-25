"""TDD tests for WriterAgent.

Tests for V3 WriterAgent:
- Generates Document from entries using Pydantic-AI
- Uses structured output with output_type=Document
- Mock-free testing with TestModel
- Uses Jinja2 templates for prompts

Following TDD Red-Green-Refactor cycle.
"""
from datetime import UTC, datetime

import ibis
import pytest
from pydantic_ai.models.test import TestModel

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Document, DocumentStatus, DocumentType, Entry
from egregora_v3.engine.agents.writer import WriterAgent
from egregora_v3.engine.template_loader import TemplateLoader
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
            content="Python is a great programming language for beginners.",
            published=datetime(2024, 12, 1, 10, 0, 0, tzinfo=UTC),
            updated=datetime(2024, 12, 1, 10, 0, 0, tzinfo=UTC),
        ),
        Entry(
            id="entry-2",
            title="JavaScript Guide",
            summary="Modern JavaScript features",
            content="ES6 introduced many powerful features to JavaScript.",
            published=datetime(2024, 12, 2, 11, 0, 0, tzinfo=UTC),
            updated=datetime(2024, 12, 2, 11, 0, 0, tzinfo=UTC),
        ),
    ]


@pytest.fixture
def content_library() -> ContentLibrary:
    """Create a content library for testing using in-memory DuckDB."""
    conn = ibis.duckdb.connect(":memory:")
    repo = DuckDBDocumentRepository(conn)
    repo.initialize()
    return ContentLibrary(
        posts=repo, media=repo, profiles=repo, journal=repo, enrichments=repo
    )


@pytest.fixture
def pipeline_context(content_library: ContentLibrary) -> PipelineContext:
    """Create pipeline context for testing."""
    return PipelineContext(
        library=content_library, run_id="test-run-123", metadata={"test": True}
    )


@pytest.fixture
def template_loader() -> TemplateLoader:
    """Create a TemplateLoader for testing."""
    return TemplateLoader()


@pytest.fixture
def test_model() -> TestModel:
    """Create a TestModel instance for testing."""
    valid_doc_dict = {
        "id": "test-generated-post",
        "title": "Generated Blog Post",
        "content": "# Generated Blog Post\n\nThis is a test blog post.",
        "doc_type": "post",
        "status": "draft",
        "updated": datetime.now(UTC).isoformat(),
    }
    return TestModel(custom_output_args=valid_doc_dict)


# ========== Initialization Tests ==========


class TestWriterAgentInitialization:
    """Test WriterAgent initialization."""

    def test_writer_agent_initialization_with_deps(
        self, template_loader: TemplateLoader, test_model: TestModel
    ) -> None:
        """Test that WriterAgent can be initialized with dependencies."""
        agent = WriterAgent(model=test_model, template_loader=template_loader)
        assert agent is not None
        assert agent.template_loader is template_loader

    # This is the new failing test
    def test_writer_agent_fails_without_dependencies(self) -> None:
        """Test that WriterAgent raises TypeError without dependencies."""
        with pytest.raises(TypeError):
            WriterAgent()  # type: ignore

        with pytest.raises(ValueError, match="Model must be a valid Pydantic-AI model instance"):
            WriterAgent(model="test", template_loader=TemplateLoader())


# ========== Basic Functionality Tests ==========


@pytest.mark.asyncio
async def test_writer_agent_generates_document(
    sample_entries: list[Entry],
    pipeline_context: PipelineContext,
    template_loader: TemplateLoader,
    test_model: TestModel,
) -> None:
    """Test that WriterAgent generates a Document from entries."""
    agent = WriterAgent(model=test_model, template_loader=template_loader)
    result = await agent.generate(entries=sample_entries, context=pipeline_context)
    assert isinstance(result, Document)


@pytest.mark.asyncio
async def test_writer_agent_structured_output(
    sample_entries: list[Entry],
    pipeline_context: PipelineContext,
    template_loader: TemplateLoader,
    test_model: TestModel,
) -> None:
    """Test that WriterAgent returns structured Document output."""
    agent = WriterAgent(model=test_model, template_loader=template_loader)
    result = await agent.generate(entries=sample_entries, context=pipeline_context)
    assert isinstance(result, Document)
    assert result.title
    assert result.content
    assert result.doc_type == DocumentType.POST


# ========== Edge Cases ==========


@pytest.mark.asyncio
async def test_writer_agent_handles_empty_entries(
    pipeline_context: PipelineContext,
    template_loader: TemplateLoader,
    test_model: TestModel,
) -> None:
    """Test that WriterAgent handles empty entry list."""
    agent = WriterAgent(model=test_model, template_loader=template_loader)
    with pytest.raises(ValueError, match="at least one entry"):
        await agent.generate(entries=[], context=pipeline_context)


# ========== Prompt Template Tests ==========


class TestWriterAgentPromptTemplates:
    """Test WriterAgent prompt generation from Jinja2 templates."""

    def test_writer_agent_loads_system_prompt_from_template(
        self, template_loader: TemplateLoader, test_model: TestModel
    ) -> None:
        """WriterAgent should load system prompt from writer/system.jinja2."""
        agent = WriterAgent(model=test_model, template_loader=template_loader)
        system_prompt = agent._get_system_prompt()
        assert "blog posts from feed entries" in system_prompt
        assert "markdown formatting" in system_prompt

    def test_user_prompt_includes_entry_summaries(
        self,
        sample_entries: list[Entry],
        template_loader: TemplateLoader,
        test_model: TestModel,
    ) -> None:
        """User prompt should include entry summaries when available."""
        agent = WriterAgent(model=test_model, template_loader=template_loader)
        user_prompt = agent._build_prompt(sample_entries)
        assert "Learn Python basics" in user_prompt
        assert "Modern JavaScript features" in user_prompt


# ========== End-to-End Test ==========


@pytest.mark.asyncio
async def test_writer_agent_generates_document_using_templates(
    sample_entries: list[Entry],
    pipeline_context: PipelineContext,
    template_loader: TemplateLoader,
    test_model: TestModel,
) -> None:
    """WriterAgent should generate a document using Jinja2 templates."""
    agent = WriterAgent(model=test_model, template_loader=template_loader)
    result = await agent.generate(entries=sample_entries, context=pipeline_context)
    assert result is not None
    assert result.title
    assert result.content
    assert result.doc_type == "post"
    assert result.status == "draft"
