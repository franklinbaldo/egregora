"""EnricherAgent for adding descriptions and metadata to entries.

Uses Pydantic-AI for generating enrichments for media content.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from egregora_v3.core.context import PipelineContext
from egregora_v3.core.types import Entry, Feed


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
        system_prompt: str | None = None,
    ) -> None:
        """Initialize EnricherAgent.

        Args:
            model: Model name (e.g., "google-gla:gemini-2.0-flash-vision", "test")
            skip_existing: Skip entries that already have content
            system_prompt: Optional custom system prompt

        """
        self.model_name = model
        self.skip_existing = skip_existing
        self.custom_system_prompt = system_prompt

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
            system_prompt=system_prompt or self._get_default_system_prompt(),
        )

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for the agent.

        TODO: Replace with Jinja2 template in Phase 3.4
        """
        return """You are a helpful assistant that generates descriptions for media content.

Given information about a media file (image, audio, or video), provide:
- A clear, descriptive caption
- Confidence score (0.0 to 1.0)
- Relevant metadata tags

Be concise but informative. Focus on what's visible or audible in the media.
"""

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

        # Create enriched entry with updated content
        return Entry(
            id=entry.id,
            title=entry.title,
            content=enrichment.description,
            summary=entry.summary,
            published=entry.published,
            updated=datetime.now(UTC),
            authors=entry.authors,
            links=entry.links,
            categories=entry.categories,
            internal_metadata=entry.internal_metadata
            | {
                "enrichment_confidence": str(enrichment.confidence),
                **{f"enrichment_{k}": v for k, v in enrichment.metadata.items()},
            },
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

        TODO: Replace with Jinja2 template in Phase 3.4

        Args:
            entry: Entry with media to describe

        Returns:
            Formatted prompt string

        """
        lines = ["Describe the following media:", ""]

        # Add title
        lines.append(f"Title: {entry.title}")

        # Add media information
        if entry.links:
            media_links = [
                link
                for link in entry.links
                if link.rel == "enclosure" and link.type
            ]
            if media_links:
                lines.append("\nMedia files:")
                lines.extend(f"- {link.href} ({link.type})" for link in media_links)

        # Add existing content if any
        if entry.content:
            lines.append(f"\nExisting description: {entry.content}")

        lines.append(
            "\nProvide a clear, descriptive caption for this media content."
        )

        return "\n".join(lines)
