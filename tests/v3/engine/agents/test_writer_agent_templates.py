"""TDD tests for WriterAgent Jinja2 template integration.

Tests written BEFORE implementing template support in WriterAgent.
Following TDD Red-Green-Refactor cycle.
"""

from datetime import UTC, datetime

import ibis
import pytest

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Entry
from egregora_v3.engine.agents.writer import WriterAgent
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
        profiles=repo,
        journal=repo,
        enrichments=repo,
    )


@pytest.fixture
def pipeline_context(content_library: ContentLibrary) -> PipelineContext:
    """Create pipeline context for testing."""
    return PipelineContext(
        library=content_library,
        run_id="test-run-templates",
        metadata={"test": True},
    )


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


class TestWriterAgentTemplateInitialization:
    """Test WriterAgent initialization with templates."""

    def test_writer_agent_can_initialize_with_template_loader(self) -> None:
        """WriterAgent should be able to use TemplateLoader."""
        agent = WriterAgent(model="test", use_templates=True)
        assert agent is not None
        assert hasattr(agent, "template_loader")
        assert agent.template_loader is not None

    def test_writer_agent_initializes_without_templates_by_default(self) -> None:
        """WriterAgent should not use templates by default (backward compatibility)."""
        agent = WriterAgent(model="test")
        # Should either not have template_loader or it should be None
        assert not hasattr(agent, "template_loader") or agent.template_loader is None


class TestWriterAgentSystemPromptTemplate:
    """Test WriterAgent system prompt from Jinja2 template."""

    def test_writer_agent_loads_system_prompt_from_template(self) -> None:
        """WriterAgent should load system prompt from writer/system.jinja2."""
        agent = WriterAgent(model="test", use_templates=True)

        # Get system prompt (might be a method or property)
        system_prompt = agent._get_system_prompt_from_template()

        # Should contain key instructions from template
        assert "blog posts from feed entries" in system_prompt
        assert "markdown formatting" in system_prompt
        assert "POST" in system_prompt
        assert "DRAFT" in system_prompt

    def test_system_prompt_template_includes_base_template_content(self) -> None:
        """System prompt should include content from base.jinja2."""
        agent = WriterAgent(model="test", use_templates=True)

        system_prompt = agent._get_system_prompt_from_template()

        # Should contain base template elements
        assert "AI assistant" in system_prompt
        assert "Current date:" in system_prompt or "Egregora" in system_prompt


class TestWriterAgentUserPromptTemplate:
    """Test WriterAgent user prompt generation from Jinja2 template."""

    def test_writer_agent_renders_user_prompt_from_template(
        self,
        sample_entries: list[Entry],
    ) -> None:
        """WriterAgent should render user prompt from writer/generate_post.jinja2."""
        agent = WriterAgent(model="test", use_templates=True)

        # Build prompt using template
        user_prompt = agent._build_prompt_from_template(sample_entries)

        # Should contain entries data
        assert "Python Tutorial" in user_prompt
        assert "JavaScript Guide" in user_prompt
        assert "Entry 1:" in user_prompt or "Entry 1" in user_prompt

    def test_user_prompt_includes_entry_summaries(
        self,
        sample_entries: list[Entry],
    ) -> None:
        """User prompt should include entry summaries when available."""
        agent = WriterAgent(model="test", use_templates=True)

        user_prompt = agent._build_prompt_from_template(sample_entries)

        assert "Learn Python basics" in user_prompt
        assert "Modern JavaScript features" in user_prompt

    def test_user_prompt_includes_published_dates(
        self,
        sample_entries: list[Entry],
    ) -> None:
        """User prompt should include published dates formatted nicely."""
        agent = WriterAgent(model="test", use_templates=True)

        user_prompt = agent._build_prompt_from_template(sample_entries)

        # Should have formatted dates (from format_datetime filter)
        assert "2024" in user_prompt
        assert "12" in user_prompt  # Month

    def test_user_prompt_truncates_long_content(self) -> None:
        """User prompt should truncate very long entry content."""
        agent = WriterAgent(model="test", use_templates=True)

        # Create entry with very long content
        long_entry = Entry(
            id="long-entry",
            title="Long Article",
            content=" ".join(["word"] * 200),  # 200 words
            updated=datetime.now(UTC),
        )

        user_prompt = agent._build_prompt_from_template([long_entry])

        # Content should be truncated (template uses truncate_words(100))
        word_count = len(user_prompt.split())
        # Should not have all 200 words - template truncates to 100
        # (plus other template text, so check it's not 200+)
        assert word_count < 250


class TestWriterAgentEndToEndWithTemplates:
    """Test complete WriterAgent flow with templates."""

    @pytest.mark.asyncio
    async def test_writer_agent_generates_document_using_templates(
        self,
        sample_entries: list[Entry],
        pipeline_context: PipelineContext,
    ) -> None:
        """WriterAgent should generate document using Jinja2 templates."""
        agent = WriterAgent(model="test", use_templates=True)

        # Generate document
        result = await agent.generate(
            entries=sample_entries,
            context=pipeline_context,
        )

        # Should return a valid Document
        assert result is not None
        assert result.title
        assert result.content
        assert result.doc_type == "post"
        assert result.status == "draft"

    @pytest.mark.asyncio
    async def test_template_prompts_differ_from_hardcoded_prompts(
        self,
        sample_entries: list[Entry],
    ) -> None:
        """Template-based prompts should be different from hardcoded ones."""
        agent_with_templates = WriterAgent(model="test", use_templates=True)
        agent_without_templates = WriterAgent(model="test", use_templates=False)

        # Get prompts
        prompt_with_template = agent_with_templates._build_prompt_from_template(sample_entries)
        prompt_hardcoded = agent_without_templates._build_prompt(sample_entries)

        # Prompts should have different formatting due to template
        # Template includes more metadata (published dates, etc.)
        assert len(prompt_with_template) != len(prompt_hardcoded) or prompt_with_template != prompt_hardcoded
