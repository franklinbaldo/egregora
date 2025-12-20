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
from egregora.output_adapters.conventions import StandardUrlConvention
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
        self.url_convention = StandardUrlConvention()

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

            # Predict the path using StandardUrlConvention
            # We assume the banner will be a JPEG (default assumption for generative AI)
            # The document ID will be forced to be slug + ".jpg"
            slug = slugify(post_slug, max_len=60)
            document_id = f"{slug}.jpg"

            # Create a placeholder document to generate the correct URL
            # Note: We don't save this document, just use it for URL prediction
            placeholder_doc = Document(
                content="", type=DocumentType.MEDIA, metadata={"filename": document_id}, id=document_id
            )

            # The URL context can be obtained from deps.resources.output.url_context if available
            # otherwise we construct a default one. However, the LLM needs the RELATIVE path
            # to include in the frontmatter, or the absolute URL if it's hosted.
            # MkDocsAdapter.url_context usually has base_url="" and site_prefix="".

            output_sink = ctx.deps.resources.output
            if output_sink and output_sink.url_convention:
                predicted_url = output_sink.url_convention.canonical_url(
                    placeholder_doc, output_sink.url_context
                )
            else:
                # Fallback if no output sink available (should not happen in writer)
                predicted_url = self.url_convention.canonical_url(
                    placeholder_doc, ctx.deps.resources.output.url_context
                )

            return BannerResult(status="scheduled", path=predicted_path(predicted_url))


def predicted_path(url: str) -> str:
    """Clean up URL to be used as path in markdown."""
    return url.lstrip("/")
