"""Orchestration logic for the writer agent.

This module acts as the facade for the writer package, coordinating context building,
cache checks, agent execution, and result finalization.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from egregora.agents.types import (
    WriterDeps,
)
from egregora.agents.writer.agent import execute_writer_with_error_handling
from egregora.agents.writer.context import (
    WriterContext,
    WriterContextParams,
    _build_context_and_signature,
)
from egregora.agents.writer.economic import execute_economic_writer
from egregora.data_primitives.document import Document, DocumentType
from egregora.rag import index_documents, reset_backend
from egregora.resources.prompts import render_prompt
from egregora.utils.cache import CacheTier, PipelineCache

if TYPE_CHECKING:
    from egregora.utils.metrics import UsageTracker
    from pathlib import Path

    from ibis.expr.types import Table

    from egregora.agents.types import WriterResources
    from egregora.config.settings import EgregoraConfig

logger = logging.getLogger(__name__)

# Result keys
RESULT_KEY_POSTS = "posts"
RESULT_KEY_PROFILES = "profiles"


@dataclass
class WriterDepsParams:
    """Parameters for creating WriterDeps."""

    window_start: datetime
    window_end: datetime
    resources: WriterResources
    model_name: str
    table: Table | None = None
    config: EgregoraConfig | None = None
    conversation_xml: str = ""
    active_authors: list[str] | None = None
    adapter_content_summary: str = ""
    adapter_generation_instructions: str = ""


def _prepare_writer_dependencies(params: WriterDepsParams) -> WriterDeps:
    """Create WriterDeps from window parameters and resources."""
    window_label = f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}"

    return WriterDeps(
        resources=params.resources,
        window_start=params.window_start,
        window_end=params.window_end,
        window_label=window_label,
        model_name=params.model_name,
        table=params.table,
        config=params.config,
        conversation_xml=params.conversation_xml,
        active_authors=params.active_authors or [],
        adapter_content_summary=params.adapter_content_summary,
        adapter_generation_instructions=params.adapter_generation_instructions,
    )


def _check_writer_cache(
    cache: PipelineCache, signature: str, window_label: str, usage_tracker: UsageTracker | None = None
) -> dict[str, list[str]] | None:
    """Check L3 cache for cached writer results."""
    if cache.should_refresh(CacheTier.WRITER):
        return None

    cached_result = cache.writer.get(signature)
    if cached_result:
        logger.info("⚡ [L3 Cache Hit] Skipping Writer LLM for window %s", window_label)
        if usage_tracker:
            # Record a cache hit (0 tokens) to track efficiency
            pass
    return cached_result


def _index_new_content_in_rag(
    resources: WriterResources,
    saved_posts: list[str],
    saved_profiles: list[str],
) -> None:
    """Index newly created content in RAG system."""
    # Check if RAG is enabled and we have posts to index
    if not (resources.retrieval_config.enabled and saved_posts):
        return

    try:
        # Read the newly saved post documents
        docs: list[Document] = []
        for post_id in saved_posts:
            # Try to read the document from output format
            if hasattr(resources.output, "documents"):
                # Find the matching document in the output format's documents
                for doc in resources.output.documents():
                    if doc.type == DocumentType.POST and post_id in str(doc.metadata.get("slug", "")):
                        docs.append(doc)
                        break

        if docs:
            index_documents(docs)
            logger.info("Indexed %d new posts in RAG", len(docs))
        else:
            logger.debug("No new documents to index in RAG")

    except (ConnectionError, TimeoutError, RuntimeError) as exc:
        # Non-critical: Pipeline continues even if RAG indexing fails
        logger.warning("RAG backend unavailable for indexing, skipping: %s", exc)
    except (ValueError, TypeError) as exc:
        logger.warning("Invalid document data for RAG indexing, skipping: %s", exc)
    except (OSError, PermissionError) as exc:
        logger.warning("Cannot access RAG storage, skipping indexing: %s", exc)
    finally:
        # Reset backend to clear loop-bound clients (httpx) as defensive programming
        reset_backend()


@dataclass
class WriterFinalizationParams:
    """Parameters for finalizing writer results."""

    saved_posts: list[str]
    saved_profiles: list[str]
    resources: WriterResources
    deps: WriterDeps
    cache: PipelineCache
    signature: str


def _finalize_writer_results(params: WriterFinalizationParams) -> dict[str, list[str]]:
    """Finalize window results: output, RAG indexing, and caching."""
    # Finalize output adapter
    params.resources.output.finalize_window(
        window_label=params.deps.window_label,
        posts_created=params.saved_posts,
        profiles_updated=params.saved_profiles,
        metadata=None,
    )

    # Index newly created content in RAG
    _index_new_content_in_rag(params.resources, params.saved_posts, params.saved_profiles)

    # Update L3 cache
    result_payload = {RESULT_KEY_POSTS: params.saved_posts, RESULT_KEY_PROFILES: params.saved_profiles}
    params.cache.writer.set(params.signature, result_payload)

    return result_payload


def _render_writer_prompt(
    context: WriterContext,
    prompts_dir: Path | None,
) -> str:
    """Render the final writer prompt text."""
    return render_prompt(
        "writer.jinja",
        prompts_dir=prompts_dir,
        **context.template_context,
    )


@dataclass
class WindowProcessingParams:
    """Parameters for processing a window of messages."""

    table: Table
    window_start: datetime
    window_end: datetime
    resources: WriterResources
    config: EgregoraConfig
    cache: PipelineCache
    adapter_content_summary: str = ""
    adapter_generation_instructions: str = ""
    run_id: str | None = None


def write_posts_for_window(params: WindowProcessingParams) -> dict[str, list[str]]:
    """Let LLM analyze window's messages, write 0-N posts, and update author profiles.

    This acts as the public entry point, orchestrating the setup and execution
    of the writer agent.
    """
    if params.table.count().execute() == 0:
        return {RESULT_KEY_POSTS: [], RESULT_KEY_PROFILES: []}

    # 1. Prepare dependencies (partial, will update with context later)
    resources = params.resources
    if params.run_id and resources.run_id is None:
        # Create new resources with run_id
        resources = dataclasses.replace(resources, run_id=params.run_id)

    # 2. Build context and calculate signature
    writer_context, signature = _build_context_and_signature(
        WriterContextParams(
            table=params.table,
            resources=resources,
            cache=params.cache,
            config=params.config,
            window_label=f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
            adapter_content_summary=params.adapter_content_summary,
            adapter_generation_instructions=params.adapter_generation_instructions,
        ),
        resources.prompts_dir,
    )

    # 3. Check L3 cache
    cached_result = _check_writer_cache(
        params.cache,
        signature,
        f"{params.window_start:%Y-%m-%d %H:%M} to {params.window_end:%H:%M}",
        resources.usage,
    )
    if cached_result:
        return cached_result

    logger.info("Using Pydantic AI backend for writer")

    # 4. Create Deps with the generated context
    deps = _prepare_writer_dependencies(
        WriterDepsParams(
            window_start=params.window_start,
            window_end=params.window_end,
            resources=resources,
            model_name=params.config.models.writer,
            table=params.table,
            config=params.config,
            conversation_xml=writer_context.conversation_xml,
            active_authors=writer_context.active_authors,
            adapter_content_summary=params.adapter_content_summary,
            adapter_generation_instructions=params.adapter_generation_instructions,
        )
    )

    # 5. Render prompt and execute agent
    prompt = _render_writer_prompt(writer_context, deps.resources.prompts_dir)

    # Check for economic mode
    if getattr(params.config.pipeline, "economic_mode", False):
        logger.info("💰 Economic Mode enabled: Using simple generation (no tools)")
        saved_posts, saved_profiles = execute_economic_writer(prompt, params.config, deps)
    else:
        saved_posts, saved_profiles = execute_writer_with_error_handling(prompt, params.config, deps)

    # 6. Finalize results (output, RAG indexing, caching)
    return _finalize_writer_results(
        WriterFinalizationParams(
            saved_posts=saved_posts,
            saved_profiles=saved_profiles,
            resources=resources,
            deps=deps,
            cache=params.cache,
            signature=signature,
        )
    )
