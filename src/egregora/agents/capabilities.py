"""Capabilities for extending the writer agent.

Each capability registers its tools with the agent, enabling explicit and
auditable composition at the call site.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic_ai import Agent, RunContext

from egregora.agents.types import WriterDeps
from egregora.agents.writer_tools import (
    BannerContext,
    BannerResult,
    SearchMediaResult,
    generate_banner_impl,
    search_media_impl,
)

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
            return search_media_impl(query, top_k)


class BannerCapability:
    """Enables visual banner generation for posts (Synchronous)."""

    name = "Banner Image Generation"

    def register(self, agent: Agent[WriterDeps, Any]) -> None:
        @agent.tool
        def generate_banner(
            ctx: RunContext[WriterDeps], post_slug: str, title: str, summary: str
        ) -> BannerResult:
            """Generate a banner image for a post."""
            banner_ctx = BannerContext(output_sink=ctx.deps.output_sink)
            return generate_banner_impl(banner_ctx, post_slug, title, summary)


class ScheduledBannerCapability:
    """Enables visual banner generation for posts (Scheduled/Background)."""

    name = "Scheduled Banner Image Generation"

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

            # Schedule task (synchronous DB insert)
            task = task_store.create_task(
                task_type="generate_banner",
                payload=payload,
                run_id=self.run_id,
            )
            logger.info("Scheduled banner generation task: %s", task_id)
            return BannerResult(status="scheduled", path=None)
