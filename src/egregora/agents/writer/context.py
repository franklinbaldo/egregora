"""Pydantic-AI powered writer agent context management.

This module handles the construction of the context required by the writer agent,
including RAG results, profile data, and conversation history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from egregora.agents.formatting import (
    build_conversation_xml,
    load_journal_memory,
)
from egregora.agents.types import WriterContextParams
from egregora.agents.writer_helpers import build_rag_context_for_prompt, load_profiles_context
from egregora.knowledge.profiles import get_active_authors
from egregora.resources.prompts import PromptManager
from egregora.transformations.windowing import generate_window_signature

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table
    from pydantic_ai import RunContext


logger = logging.getLogger(__name__)

# Constants for RAG and journaling
MAX_RAG_QUERY_BYTES = 30000


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


def _truncate_for_embedding(text: str, byte_limit: int = MAX_RAG_QUERY_BYTES) -> str:
    """Clamp markdown payloads before embedding to respect API limits."""
    encoded = text.encode("utf-8")
    if len(encoded) <= byte_limit:
        return text
    truncated = encoded[:byte_limit]
    truncated_text = truncated.decode("utf-8", errors="ignore").rstrip()
    logger.info(
        "Truncated RAG query markdown from %s bytes to %s bytes to fit embedding limits",
        len(encoded),
        byte_limit,
    )
    return truncated_text + "\n\n<!-- truncated for RAG query -->"


def _build_writer_context(params: WriterContextParams) -> WriterContext:
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


def _cast_uuid_columns_to_str(table: Table) -> Table:
    """Ensure UUID-like columns are serialised to strings."""
    return table.mutate(
        event_id=table.event_id.cast(str),
        author_uuid=table.author_uuid.cast(str),
        thread_id=table.thread_id.cast(str),
        created_by_run=table.created_by_run.cast(str),
    )


def _build_context_and_signature(
    params: WriterContextParams,
    prompts_dir: Path | None,
) -> tuple[WriterContext, str]:
    """Build writer context and calculate cache signature.

    Returns:
        Tuple of (writer_context, cache_signature)

    """
    table_with_str_uuids = _cast_uuid_columns_to_str(params.table)

    # Generate context for both prompt and signature
    # This now just generates the base context (XML, Journal) which is cheap(er)
    # We update params with casted table
    params.table = table_with_str_uuids
    writer_context = _build_writer_context(params)

    # Get template content for signature calculation
    template_content = PromptManager.get_template_content("writer.jinja", custom_prompts_dir=prompts_dir)

    # Calculate signature using data (XML) + logic (template) + engine
    signature = generate_window_signature(
        table_with_str_uuids,
        params.config,
        template_content,
        xml_content=writer_context.conversation_xml,
    )

    return writer_context, signature


# Dynamic context injection functions
def inject_rag_context(ctx: RunContext) -> str:
    """Inject RAG context into the agent prompt."""
    # We rely on dynamic attribute access or type checking the context.deps
    if ctx.deps.resources.retrieval_config.enabled:
        table_markdown = ctx.deps.conversation_xml
        return build_rag_context_for_prompt(
            table_markdown,
            top_k=ctx.deps.resources.retrieval_config.top_k,
            cache=None,
        )
    return ""


def inject_profiles_context(ctx: RunContext) -> str:
    """Inject profiles context into the agent prompt."""
    return load_profiles_context(ctx.deps.active_authors, ctx.deps.resources.output)
