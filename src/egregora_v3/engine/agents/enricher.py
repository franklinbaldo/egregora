"""EnricherAgent for adding descriptions and metadata to entries.

Uses Pydantic-AI for generating enrichments for media content.
"""

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Entry
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

    def __init__(
        self,
        model: str = "test",
        *,
        skip_existing: bool = False,
    ) -> None:
        """Initialize EnricherAgent.

        Args:
            model: Model name (e.g., "google-gla:gemini-2.0-flash-vision", "test")
            skip_existing: Skip entries that already have content

        """
        self.model_name = model
        self.skip_existing = skip_existing

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

    def _has_media_enclosure(self, entry: Entry) -> bool:
        """Check if entry has media enclosures.

        Args:
            entry: Entry to check

        Returns:
            True if entry has media enclosures

        """
        if not entry.links:
            return False

        return any(
            link.rel == "enclosure"
            and link.type
            and (
                link.type.startswith("image/")
                or link.type.startswith("audio/")
                or link.type.startswith("video/")
            )
            for link in entry.links
        )

    def _should_enrich(self, entry: Entry) -> bool:
        """Determine if entry should be enriched.

        Args:
            entry: Entry to check

        Returns:
            True if entry should be enriched

        """
        # Skip if no media
        if not self._has_media_enclosure(entry):
            return False

        # Skip if entry already has content and skip_existing=True
        return not (self.skip_existing and entry.content)

    async def enrich(
        self,
        entry: Entry,
        context: PipelineContext,
    ) -> EnrichmentResult | None:
        """Generate enrichment for a single entry.

        Args:
            entry: Entry to enrich
            context: Pipeline context

        Returns:
            EnrichmentResult if successful, None if skipped

        """
        if not self._should_enrich(entry):
            return None

        # Build prompt from entry using template
        user_prompt = self._build_prompt(entry)

        # Run agent with context
        result = await self._agent.run(user_prompt, deps=context)

        # Return structured output
        return result.output

    def _build_prompt(self, entry: Entry) -> str:
        """Build user prompt from entry using a Jinja2 template.

        Args:
            entry: Entry with media to describe

        Returns:
            Formatted prompt string

        """
        return self.template_loader.render_template(
            "enricher/enrich_media.jinja2", entry=entry
        )
