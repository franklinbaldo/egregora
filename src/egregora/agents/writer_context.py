"""Writer agent context and dependency management.

This module contains data structures and functions for building the context
and dependencies required by the writer agent, separating data preparation
from agent execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from egregora.agents.formatting import (
    build_conversation_xml,
    load_journal_memory,
)
from egregora.agents.types import WriterDeps, WriterResources
from egregora.data_primitives.document import Document, DocumentType
from egregora.knowledge.profiles import get_active_authors
from egregora.rag import index_documents, reset_backend
from egregora.resources.prompts import PromptManager
from egregora.transformations.windowing import generate_window_signature
from egregora.utils.cache import CacheTier

if TYPE_CHECKING:
    from datetime import datetime

    from ibis.expr.types import Table

    from egregora.cache import PipelineCache
    from egregora.config.settings import EgregoraConfig
    from egregora.utils.metrics import UsageTracker

logger = logging.getLogger(__name__)

# Constants for RAG and journaling
MAX_RAG_QUERY_BYTES = 30000

# Result keys
RESULT_KEY_POSTS = "posts"
RESULT_KEY_PROFILES = "profiles"


# ============================================================================
# Context Data Structures
# ============================================================================


@dataclass
class RagContext:
    """RAG query result with formatted text and metadata."""

    text: str
    records: list[dict[str, Any]]


@dataclass
class WriterContext:
    """Encapsulates all contextual data required for the writer agent prompt."""

    conversation_xml: str
    rag_context: str
    profiles_context: str
    journal_memory: str
    active_authors: list[str]
    format_instructions: str
    custom_instructions: str
    source_context: str
    date_label: str
    pii_prevention: dict[str, Any] | None = None  # LLM-native PII prevention settings

    @property
    def template_context(self) -> dict[str, Any]:
        """Return context dictionary for Jinja template rendering."""
        return {
            "conversation_xml": self.conversation_xml,
            "rag_context": self.rag_context,
            "profiles_context": self.profiles_context,
            "journal_memory": self.journal_memory,
            "active_authors": ", ".join(self.active_authors),
            "format_instructions": self.format_instructions,
            "custom_instructions": self.custom_instructions,
            "source_context": self.source_context,
            "date": self.date_label,
            "enable_memes": False,
            "pii_prevention": self.pii_prevention,
        }


@dataclass
class WriterContextParams:
    """Parameters for building writer context."""

    table: Table
    resources: WriterResources
    cache: PipelineCache
    config: EgregoraConfig
    window_label: str
    adapter_content_summary: str
    adapter_generation_instructions: str


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


# ============================================================================
# Context Building Logic
# ============================================================================


def build_writer_context(params: WriterContextParams) -> WriterContext:
    """Collect contextual inputs used when rendering the writer prompt."""
    messages_table = params.table.to_pyarrow()
    conversation_xml = build_conversation_xml(messages_table, params.resources.annotations_store)

    # CACHE INVALIDATION STRATEGY:
    # RAG and Profiles context building moved to dynamic system prompts for lazy evaluation.
    # This creates a cache trade-off:
    #
    # Trade-off: Cache signature includes conversation XML but NOT RAG/Profile results
    # - Pro: Avoids expensive RAG/Profile computation for signature calculation
    # - Con: Cache hit may use stale data if RAG index changes but conversation doesn't
    #
    # Mitigation strategies (not currently implemented):
    # 1. Include RAG index version/timestamp in signature
    # 2. Add cache TTL for RAG-enabled runs
    # 3. Manual cache invalidation when RAG index is updated
    #
    # Current behavior: Cache is conversation-scoped only. If RAG data changes
    # but conversation is identical, cached results will be used.
    # This is acceptable for most use cases where conversation changes drive cache invalidation.

    rag_context = ""  # Dynamically injected via @agent.system_prompt
    profiles_context = ""  # Dynamically injected via @agent.system_prompt

    journal_memory = load_journal_memory(params.resources.output)
    active_authors = get_active_authors(params.table)

    format_instructions = params.resources.output.get_format_instructions()
    custom_instructions = params.config.writer.custom_instructions or ""
    if params.adapter_generation_instructions:
        custom_instructions = "\n\n".join(
            filter(None, [custom_instructions, params.adapter_generation_instructions])
        )

    pii_prevention = None
    if params.config.privacy.pii_detection_enabled:
        pii_prevention = params.config.privacy.model_dump()

    return WriterContext(
        conversation_xml=conversation_xml,
        rag_context=rag_context,
        profiles_context=profiles_context,
        journal_memory=journal_memory,
        active_authors=active_authors,
        format_instructions=format_instructions,
        custom_instructions=custom_instructions,
        source_context=params.adapter_content_summary,
        date_label=params.window_label,
        pii_prevention=pii_prevention,
    )


def prepare_writer_dependencies(params: WriterDepsParams) -> WriterDeps:
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


def cast_uuid_columns_to_str(table: Table) -> Table:
    """Ensure UUID-like columns are serialised to strings."""
    return table.mutate(
        event_id=table.event_id.cast(str),
        author_uuid=table.author_uuid.cast(str),
        thread_id=table.thread_id.cast(str),
        created_by_run=table.created_by_run.cast(str),
    )


def build_context_and_signature(
    params: WriterContextParams,
    prompts_dir: Path | None,
) -> tuple[WriterContext, str]:
    """Build writer context and calculate cache signature.

    Returns:
        Tuple of (writer_context, cache_signature)

    """
    table_with_str_uuids = cast_uuid_columns_to_str(params.table)

    # Generate context for both prompt and signature
    # This now just generates the base context (XML, Journal) which is cheap(er)
    # We update params with casted table
    params.table = table_with_str_uuids
    writer_context = build_writer_context(params)

    # Get template content for signature calculation
    template_content = PromptManager.get_template_content("writer.jinja", site_dir=prompts_dir)

    # Calculate signature using data (XML) + logic (template) + engine
    signature = generate_window_signature(
        table_with_str_uuids,
        params.config,
        template_content,
        xml_content=writer_context.conversation_xml,
    )

    return writer_context, signature


# ============================================================================
# Cache & Indexing Logic
# ============================================================================


def check_writer_cache(
    cache: PipelineCache, signature: str, window_label: str, usage_tracker: UsageTracker | None = None
) -> dict[str, list[str]] | None:
    """Check L3 cache for cached writer results.

    Args:
        cache: Pipeline cache instance
        signature: Window signature for cache lookup
        window_label: Human-readable window label for logging
        usage_tracker: Optional usage tracker to record cache hits

    Returns:
        Cached result if found, None otherwise

    """
    if cache.should_refresh(CacheTier.WRITER):
        return None

    cached_result = cache.writer.get(signature)
    if cached_result:
        logger.info("⚡ [L3 Cache Hit] Skipping Writer LLM for window %s", window_label)
        if usage_tracker:
            # Record a cache hit (0 tokens) to track efficiency
            pass
    return cached_result


def index_new_content_in_rag(
    resources: WriterResources,
    saved_posts: list[str],
    saved_profiles: list[str],
) -> None:
    """Index newly created content in RAG system.

    Args:
        resources: Writer resources including RAG configuration
        saved_posts: List of post identifiers that were created
        saved_profiles: List of profile identifiers that were updated

    """
    # Check if RAG is enabled and we have posts to index
    if not (resources.retrieval_config.enabled and saved_posts):
        return

    try:
        # Read the newly saved post documents
        docs: list[Document] = []
        for post_id in saved_posts:
            # Try to read the document from output format
            # The output format should have a way to read documents by identifier
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
        # NOTE: Not strictly needed in sync mode but prevents potential issues
        # if async operations are added in the future or called from async contexts
        reset_backend()
