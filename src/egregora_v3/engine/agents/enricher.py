"""EnricherAgent for adding descriptions and metadata to entries.

Uses Pydantic-AI for generating enrichments for media content.
"""

from typing import List

from jinja2 import Environment, PackageLoader
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.utils import slugify
from egregora_v3.engine import filters


class EnrichmentResult(BaseModel):
    """Structured output from enrichment agent."""

    description: str
    """Description or caption for the media."""

    confidence: float = 1.0
    """Confidence score for the enrichment (0.0 to 1.0)."""

    metadata: dict[str, str] = {}
    """Additional metadata extracted from the media."""


class EnricherAgent:
    """Agent that enriches feed entries with media descriptions.

    Uses Pydantic-AI with structured output (output_type=EnrichmentResult).
    Supports RunContext[PipelineContext] for dependency injection.
    """

    def __init__(self, model: str = "test") -> None:
        """Initialize EnricherAgent.

        Args:
            model: Model name (e.g., "google-gla:gemini-2.0-flash", "test")
        """
        self.model_name = model

        # Heuristic: Library over framework. Use Jinja2 directly.
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
            valid_enrichment_dict = {
                "description": "A beautiful sunset over the ocean.",
                "confidence": 0.95,
                "metadata": {"scene": "sunset"},
            }
            model_instance = TestModel(custom_output_args=valid_enrichment_dict)
        else:
            model_instance = model  # type: ignore[assignment]

        system_prompt = self.env.get_template("enricher/system.jinja2").render()
        self._agent: Agent[PipelineContext, EnrichmentResult] = Agent(
            model=model_instance,
            output_type=EnrichmentResult,
            system_prompt=system_prompt,
        )

    async def enrich(
        self,
        media_urls: List[str],
        context: PipelineContext,
    ) -> EnrichmentResult | None:
        """Generate enrichment for a list of media URLs.

        Args:
            media_urls: List of media URLs to enrich
            context: Pipeline context

        Returns:
            EnrichmentResult if successful, None if no media URLs are provided.
        """
        if not media_urls:
            return None

        user_prompt = self._build_prompt(media_urls)
        result = await self._agent.run(user_prompt, deps=context)
        return result.output

    def _build_prompt(self, media_urls: List[str]) -> str:
        """Build user prompt from a list of media URLs using a Jinja2 template.

        Args:
            media_urls: List of media URLs to describe

        Returns:
            Formatted prompt string
        """
        template = self.env.get_template("enricher/enrich_media.jinja2")
        return template.render(media_urls=media_urls)
