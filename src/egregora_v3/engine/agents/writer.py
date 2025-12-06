"""WriterAgent for generating blog posts from entries.

Uses Pydantic-AI for structured output with output_type=Document.
"""

import json
from datetime import UTC, datetime

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Document, DocumentStatus, DocumentType, Entry


class WriterAgent:
    """Agent that generates blog posts from feed entries.

    Uses Pydantic-AI with structured output (output_type=Document).
    Supports RunContext[PipelineContext] for dependency injection.
    """

    def __init__(self, model: str = "test") -> None:
        """Initialize WriterAgent.

        Args:
            model: Model name (e.g., "google-gla:gemini-2.0-flash", "test")
        """
        self.model_name = model

        # Create Pydantic-AI agent with structured output
        # For testing, use TestModel; for production, use actual model
        if model == "test":
            # Configure TestModel with valid Document dict for testing
            # Use custom_output_args for structured output (not custom_output_text)
            valid_doc_dict = {
                "id": "test-generated-post",
                "title": "Generated Blog Post",
                "content": "# Generated Blog Post\n\nThis is a test blog post generated from entries.",
                "doc_type": "post",
                "status": "draft",
                "updated": datetime.now(UTC).isoformat(),
            }
            model_instance = TestModel(custom_output_args=valid_doc_dict)
        else:
            model_instance = model  # type: ignore[assignment]

        self._agent: Agent[PipelineContext, Document] = Agent(
            model=model_instance,
            output_type=Document,  # Pydantic-AI uses output_type parameter
            system_prompt=self._get_system_prompt(),
        )

    def _get_system_prompt(self) -> str:
        """Get system prompt for the agent.

        TODO: Replace with Jinja2 template in Phase 3.4
        """
        return """You are a helpful assistant that generates blog posts from feed entries.

Given a list of entries, create an engaging blog post that:
- Summarizes the key points from the entries
- Uses markdown formatting
- Has a clear title and structure
- Is informative and well-written

Return a Document with:
- title: A catchy title for the post
- content: The full blog post content in markdown
- doc_type: POST
- status: DRAFT
"""

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

        TODO: Replace with Jinja2 template in Phase 3.4

        Args:
            entries: List of entries to include in prompt

        Returns:
            Formatted prompt string
        """
        lines = ["Generate a blog post from these entries:", ""]

        for i, entry in enumerate(entries, 1):
            lines.append(f"Entry {i}:")
            lines.append(f"Title: {entry.title}")
            if entry.summary:
                lines.append(f"Summary: {entry.summary}")
            lines.append("")

        lines.append("Create an engaging blog post that synthesizes these entries.")

        return "\n".join(lines)
