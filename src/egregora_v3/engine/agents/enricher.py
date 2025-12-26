"""EnricherAgent for adding descriptions and metadata to entries.

Uses Pydantic-AI for generating enrichments for media content.
"""

from typing import List
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

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

    def __init__(self, model: str = "test") -> None:
        """Initialize EnricherAgent.

        Args:
            model: Model name (e.g., "google-gla:gemini-2.0-flash-vision", "test")

        """
        self.model_name = model

        # Initialize template loader for prompts
        self.template_loader = TemplateLoader()

        # Create Pydantic-AI agent with structured output
        if model == "test":
            # Configure TestModel with valid EnrichmentResult dict for testing
            valid_enrichment_dict = {
                "description": "A beautiful sunset over the ocean with orange and pink clouds reflecting on the water.",
                "confidence": 0.95,
                "metadata": {"scene": "sunset", "location": "beach"},
            }
            model_instance = TestModel(custom_output_args=valid_enrichment_dict)
        else:
            model_instance = model  # type: ignore[assignment]

        self._agent: Agent[PipelineContext, EnrichmentResult] = Agent(
            model=model_instance,
            output_type=EnrichmentResult,
            system_prompt=self.template_loader.render_template(
                "enricher/system.jinja2"
            ),
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
