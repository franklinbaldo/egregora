"""EnricherAgent for adding descriptions and metadata to entries.

Uses Pydantic-AI for generating enrichments for media content.
"""

from typing import List
from pydantic import BaseModel
from pydantic_ai import Agent

from egregora_v3.core.context import PipelineContext
from egregora_v3.engine.template_loader import TemplateLoader


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

    def __init__(self, agent: Agent[PipelineContext, EnrichmentResult]) -> None:
        """Initialize EnricherAgent.

        Args:
            agent: A pre-configured pydantic_ai.Agent instance.
        """
        # Initialize template loader for prompts
        self.template_loader = TemplateLoader()
        self._agent = agent

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

        # Build prompt from entry using template
        user_prompt = self._build_prompt(media_urls)

        # Run agent with context
        result = await self._agent.run(user_prompt, deps=context)

        # Return structured output
        return result.output

    def _build_prompt(self, media_urls: List[str]) -> str:
        """Build user prompt from a list of media URLs using a Jinja2 template.

        Args:
            media_urls: List of media URLs to describe

        Returns:
            Formatted prompt string

        """
        return self.template_loader.render_template(
            "enricher/enrich_media.jinja2", media_urls=media_urls
        )
