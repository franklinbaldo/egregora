"""EnricherAgent for adding descriptions and metadata to entries.

Uses Pydantic-AI for generating enrichments for media content.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Entry, Feed
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
        model: str,
        *,
        skip_existing: bool = False,
    ) -> None:
        """Initialize EnricherAgent.

        Args:
            model: Model name (e.g., "google-gla:gemini-2.0-flash-vision")
            skip_existing: Skip entries that already have content

        """
        self.model_name = model
        self.skip_existing = skip_existing
        self.template_loader = TemplateLoader()

        self._agent: Agent[PipelineContext, EnrichmentResult] = Agent(
            model=model,  # type: ignore[arg-type]
            output_type=EnrichmentResult,
            system_prompt=self._get_system_prompt(),
        )

    @classmethod
    def for_test(cls, *, skip_existing: bool = False) -> "EnricherAgent":
        """Create an EnricherAgent with a TestModel for testing."""
        agent = cls(model="test", skip_existing=skip_existing)

        # Configure TestModel with valid EnrichmentResult dict for testing
        valid_enrichment_dict = {
            "description": "A beautiful sunset over the ocean with orange and pink clouds reflecting on the water.",
            "confidence": 0.95,
            "metadata": {"scene": "sunset", "location": "beach"},
        }
        model_instance = TestModel(custom_output_args=valid_enrichment_dict)

        # Replace the agent's model with the test model
        agent._agent.model = model_instance
        return agent

    def _get_system_prompt(self) -> str:
        """Get default system prompt for the agent."""
        return self.template_loader.render_template("enricher/system.jinja2")

    def _should_enrich(self, entry: Entry) -> bool:
        """Determine if entry should be enriched.

        Args:
            entry: Entry to check

        Returns:
            True if entry should be enriched

        """
        # Skip if no media
        if not entry.has_enclosure:
            return False

        # Skip if entry already has content and skip_existing=True
        return not (self.skip_existing and entry.content)

    async def enrich(
        self,
        entry: Entry,
        context: PipelineContext,
    ) -> Entry:
        """Enrich a single entry with media description.

        Args:
            entry: Entry to enrich
            context: Pipeline context

        Returns:
            Enriched entry (or original if no enrichment needed)

        """
        if not self._should_enrich(entry):
            return entry

        # Build prompt from entry
        user_prompt = self._build_prompt(entry)

        # Run agent with context
        result = await self._agent.run(user_prompt, deps=context)

        # Get enrichment from result
        enrichment = result.output

        # Merge new metadata with existing internal metadata
        new_metadata = entry.internal_metadata | {
            "enrichment_confidence": str(enrichment.confidence),
            **{f"enrichment_{k}": v for k, v in enrichment.metadata.items()},
        }

        # Create enriched entry using model_copy for a declarative update
        return entry.model_copy(
            update={
                "content": enrichment.description,
                "updated": datetime.now(UTC),
                "internal_metadata": new_metadata,
            }
        )

    async def enrich_feed(
        self,
        feed: Feed,
        context: PipelineContext,
    ) -> Feed:
        """Enrich all entries in a feed.

        Args:
            feed: Feed to enrich
            context: Pipeline context

        Returns:
            Feed with enriched entries

        """
        enriched_entries = []
        for entry in feed.entries:
            enriched_entry = await self.enrich(entry, context)
            enriched_entries.append(enriched_entry)

        # Return new feed with enriched entries
        return Feed(
            id=feed.id,
            title=feed.title,
            updated=datetime.now(UTC),
            authors=feed.authors,
            links=feed.links,
            entries=enriched_entries,
        )

    def _build_prompt(self, entry: Entry) -> str:
        """Build user prompt from entry.

        Args:
            entry: Entry with media to describe

        Returns:
            Formatted prompt string

        """
        return self.template_loader.render_template(
            "enricher/describe_media.jinja2", entry=entry
        )
