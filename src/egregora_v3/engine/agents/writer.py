"""WriterAgent for generating blog posts from entries.

Uses Pydantic-AI for structured output with output_type=Document.
"""

from jinja2 import Environment, PackageLoader
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Entry
from egregora_v3.core.utils import slugify
from egregora_v3.engine import filters


class GeneratedPost(BaseModel):
    """Data-only representation of a generated post."""

    title: str
    content: str


class WriterAgent:
    """Agent that generates blog posts from feed entries.

    Uses Pydantic-AI with structured output (output_type=GeneratedPost).
    Supports RunContext[PipelineContext] for dependency injection.
    """

    def __init__(self, model: str = "test") -> None:
        """Initialize WriterAgent.

        Args:
            model: Model name (e.g., "google-gla:gemini-2.0-flash", "test")

        """
        self.model_name = model

        # Heuristic: Library over framework. Use Jinja2 directly.
        # This removes the unnecessary TemplateLoader abstraction.
        self.env = Environment(
            loader=PackageLoader("egregora_v3.engine", "prompts"),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters.update(
            {
                "format_datetime": filters.format_datetime,
                "isoformat": filters.isoformat,
                "truncate_words": filters.truncate_words,
                "slugify": slugify,
            }
        )

        # Create Pydantic-AI agent with structured output
        if model == "test":
            valid_post_dict = {
                "title": "Generated Blog Post",
                "content": "# Generated Blog Post\n\nThis is a test blog post generated from entries.",
            }
            model_instance = TestModel(custom_output_args=valid_post_dict)
        else:
            model_instance = model  # type: ignore[assignment]

        system_prompt = self.env.get_template("writer/system.jinja2").render()
        self._agent: Agent[PipelineContext, GeneratedPost] = Agent(
            model=model_instance,
            output_type=GeneratedPost,
            system_prompt=system_prompt,
        )

    async def generate(
        self,
        entries: list[Entry],
        context: PipelineContext,
    ) -> GeneratedPost:
        """Generate a blog post from entries.

        Args:
            entries: List of feed entries to process
            context: Pipeline context with run metadata

        Returns:
            GeneratedPost containing the title and content.

        Raises:
            ValueError: If entries list is empty

        """
        if not entries:
            msg = "WriterAgent requires at least one entry to generate a post"
            raise ValueError(msg)

        # Build user prompt from entries using the template
        user_prompt = self._build_prompt(entries)

        # Run agent with context
        result = await self._agent.run(user_prompt, deps=context)

        # Return the structured data object
        return result.output

    def _build_prompt(self, entries: list[Entry]) -> str:
        """Build user prompt from entries using a Jinja2 template.

        Args:
            entries: List of entries to include in prompt

        Returns:
            Formatted prompt string

        """
        template = self.env.get_template("writer/generate_post.jinja2")
        return template.render(entries=entries)
