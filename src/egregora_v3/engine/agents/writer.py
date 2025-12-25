"""WriterAgent for generating blog posts from entries.

Uses Pydantic-AI for structured output with output_type=Document.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic_ai import Agent

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Document, DocumentStatus, DocumentType, Entry
from egregora_v3.engine.template_loader import TemplateLoader


class WriterAgent:
    """Agent that generates blog posts from feed entries.

    Uses Pydantic-AI with structured output (output_type=Document).
    Relies on dependency injection for the AI model and template loader.
    """

    def __init__(self, *, model: Any, template_loader: TemplateLoader) -> None:
        """Initialize WriterAgent.

        Args:
            model: A Pydantic-AI compatible model instance (e.g., TestModel, GoogleModel).
            template_loader: An instance of TemplateLoader for loading prompts.

        Raises:
            ValueError: If the provided model is a string instead of an object instance.
        """
        if isinstance(model, str):
            raise ValueError(
                "Model must be a valid Pydantic-AI model instance, not a string."
            )

        self.model = model
        self.template_loader = template_loader

        self._agent: Agent[PipelineContext, Document] = Agent(
            model=self.model,
            output_type=Document,
            system_prompt=self._get_system_prompt(),
        )

    def _get_system_prompt(self) -> str:
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
            entries: List of feed entries to process.
            context: Pipeline context with run metadata.

        Returns:
            A Document containing the generated blog post.

        Raises:
            ValueError: If the entries list is empty.
        """
        if not entries:
            raise ValueError("WriterAgent requires at least one entry to generate a post")

        user_prompt = self._build_prompt(entries)
        result = await self._agent.run(user_prompt, deps=context)
        doc = result.output

        # Ensure proper defaults after generation
        if not doc.doc_type:
            doc.doc_type = DocumentType.POST
        if not doc.status:
            doc.status = DocumentStatus.DRAFT
        if not doc.updated:
            doc.updated = datetime.now(UTC)

        # Generate a stable ID if one is not provided by the model
        if not doc.id or doc.id == "string":  # Handle pydantic-ai default
            doc = Document.create(
                content=doc.content or "Generated content",
                doc_type=doc.doc_type,
                title=doc.title or "Generated Post",
                status=doc.status,
            )

        return doc

    def _build_prompt(self, entries: list[Entry]) -> str:
        """Build the user prompt from a list of entries using a Jinja2 template.

        Args:
            entries: List of entries to include in the prompt.

        Returns:
            The rendered prompt string from writer/generate_post.jinja2.
        """
        return self.template_loader.render_template(
            "writer/generate_post.jinja2",
            entries=entries,
        )
