"""WriterAgent for generating blog posts from entries.

Uses Pydantic-AI for structured output with output_type=Document.
"""

from datetime import UTC, datetime

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Document, DocumentStatus, DocumentType, Entry
from egregora_v3.engine.template_loader import TemplateLoader


class WriterAgent:
    """Agent that generates blog posts from feed entries.

    Uses Pydantic-AI with structured output (output_type=Document).
    Supports RunContext[PipelineContext] for dependency injection.
    """

    def __init__(self, model: str) -> None:
        """Initialize WriterAgent.

        Args:
            model: Model name (e.g., "google-gla:gemini-2.0-flash")

        """
        self.model_name = model

        # Initialize template loader
        self.template_loader: TemplateLoader = TemplateLoader()

        self._agent: Agent[PipelineContext, Document] = Agent(
            model=model,  # type: ignore[arg-type]
            output_type=Document,  # Pydantic-AI uses output_type parameter
            system_prompt=self._get_system_prompt(),
        )

    @classmethod
    def for_test(cls) -> "WriterAgent":
        """Create a WriterAgent with a TestModel for testing."""
        agent = cls(model="test")

        # Configure TestModel with valid Document dict for testing
        valid_doc_dict = {
            "id": "test-generated-post",
            "title": "Generated Blog Post",
            "content": "# Generated Blog Post\n\nThis is a test blog post generated from entries.",
            "doc_type": "post",
            "status": "draft",
            "updated": datetime.now(UTC).isoformat(),
        }
        model_instance = TestModel(custom_output_args=valid_doc_dict)

        # Replace the agent's model with the test model
        agent._agent.model = model_instance
        return agent

    def _get_system_prompt(self) -> str:
        """Get system prompt for the agent."""
        return self._get_system_prompt_from_template()

    def _get_system_prompt_from_template(self) -> str:
        """Get system prompt from Jinja2 template.

        Returns:
            Rendered system prompt from writer/system.jinja2

        """
        return self.template_loader.render_template(
            "writer/system.jinja2",
            current_date=datetime.now(UTC),
            run_id="writer-agent",
        )

    async def generate(
        self,
        entries: list[Entry],
        context: PipelineContext,
    ) -> Document:
        """Generate a blog post from entries.

        Args:
            entries: List of feed entries to process
            context: Pipeline context with run metadata

        Returns:
            Document containing the generated blog post

        Raises:
            ValueError: If entries list is empty

        """
        if not entries:
            msg = "WriterAgent requires at least one entry to generate a post"
            raise ValueError(msg)

        # Build user prompt from entries
        user_prompt = self._build_prompt(entries)

        # Run agent with context
        result = await self._agent.run(user_prompt, deps=context)

        # Get structured Document from result
        doc = result.output

        # Ensure proper defaults
        if not doc.doc_type:
            doc.doc_type = DocumentType.POST
        if not doc.status:
            doc.status = DocumentStatus.DRAFT
        if not doc.updated:
            doc.updated = datetime.now(UTC)

        # Generate ID if not set (TestModel might not set it)
        if not doc.id or doc.id == "string":  # TestModel default
            # Use Document.create to get proper ID generation
            doc = Document.create(
                content=doc.content or "Generated content",
                doc_type=doc.doc_type,
                title=doc.title or "Generated Post",
                status=doc.status,
            )

        return doc

    def _build_prompt(self, entries: list[Entry]) -> str:
        """Build user prompt from entries.

        Args:
            entries: List of entries to include in prompt

        Returns:
            Formatted prompt string

        """
        return self._build_prompt_from_template(entries)

    def _build_prompt_from_template(self, entries: list[Entry]) -> str:
        """Build user prompt from Jinja2 template.

        Args:
            entries: List of entries to include in prompt

        Returns:
            Rendered prompt from writer/generate_post.jinja2

        """
        return self.template_loader.render_template(
            "writer/generate_post.jinja2",
            entries=entries,
        )
