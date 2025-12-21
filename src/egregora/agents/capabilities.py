"""Capabilities for extending the writer agent.

Each capability registers its tools with the agent, enabling explicit and
auditable composition at the call site.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic_ai import Agent, RunContext

from egregora.agents.types import BannerResult, SearchMediaResult, WriterDeps
from egregora.data_primitives.document import Document, DocumentType
from egregora.utils.paths import slugify

logger = logging.getLogger(__name__)


@runtime_checkable
class AgentCapability(Protocol):
    """A distinct capability that can be attached to the writer agent."""

    name: str

    def register(self, agent: Agent[WriterDeps, Any]) -> None:
        """Register tools associated with this capability."""


class RagCapability:
    """Enables RAG knowledge retrieval for media search."""

    name = "RAG Knowledge Retrieval"

    def register(self, agent: Agent[WriterDeps, Any]) -> None:
        @agent.tool
        def search_media(ctx: RunContext[WriterDeps], query: str, top_k: int = 5) -> SearchMediaResult:
            """Search for relevant media (images, videos, audio) in the knowledge base."""
            return ctx.deps.search_media(query, top_k)


class BannerCapability:
    """Enables visual banner generation for posts (Synchronous)."""

    name = "Banner Image Generation"

    def register(self, agent: Agent[WriterDeps, Any]) -> None:
        @agent.tool
        def generate_banner(
            ctx: RunContext[WriterDeps], post_slug: str, title: str, summary: str
        ) -> BannerResult:
            """Generate a banner image for a post."""
            return ctx.deps.generate_banner(post_slug, title, summary)


class BackgroundBannerCapability:
    """Enables visual banner generation for posts (Background)."""

    name = "Background Banner Image Generation"

    def __init__(self, run_id: uuid.UUID | str) -> None:
        self.run_id = uuid.UUID(str(run_id))

    def register(self, agent: Agent[WriterDeps, Any]) -> None:
        @agent.tool
        def generate_banner(
            ctx: RunContext[WriterDeps], post_slug: str, title: str, summary: str
        ) -> BannerResult:
            """Schedule a banner image generation task."""
            task_store = ctx.deps.resources.task_store
            if not task_store:
                logger.warning("Task store not available, skipping banner generation")
                return BannerResult(status="skipped", path=None)

            # Create task payload
            payload = {
                "post_slug": post_slug,
                "title": title,
                "summary": summary,
                "run_id": str(self.run_id),
            }

            # Schedule task (sync)
            task_id = task_store.enqueue(
                task_type="generate_banner",
                payload=payload,
                run_id=self.run_id,
            )
            logger.info("Scheduled banner generation task: %s", task_id)

            # Predict the banner path so the LLM can reference it before it's generated
            # This must match the logic in BannerBatchProcessor._create_document()
            slug = slugify(post_slug, max_len=60)
            # Gemini typically returns JPEG, default assumption
            extension = ".jpg"
            filename = f"{slug}{extension}"

            # Create placeholder document to generate the canonical URL
            placeholder_doc = Document(
                content="",
                type=DocumentType.MEDIA,
                metadata={"filename": filename},
                id=filename,
            )

            # Use the output sink's URL convention for accurate path prediction
            output_sink = ctx.deps.resources.output
            if output_sink and output_sink.url_convention:
                predicted_url = output_sink.url_convention.canonical_url(
                    placeholder_doc, output_sink.url_context
                )
                predicted_path = predicted_url.lstrip("/")
            else:
                # Fallback: construct path manually (shouldn't happen in normal operation)
                predicted_path = f"media/images/{filename}"

            return BannerResult(status="scheduled", path=predicted_path)
