"""Context building for the Writer agent.

This module handles RAG context assembly, profile loading, and general prompt context construction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ibis.expr.types import Table

from egregora.agents.formatting import build_conversation_xml, load_journal_memory
from egregora.agents.types import WriterResources
from egregora.agents.writer_extraction import JOURNAL_TYPE_TEXT, JournalEntry
from egregora.config.settings import EgregoraConfig
from egregora.knowledge.profiles import get_active_authors, read_profile
from egregora.rag import RAGQueryRequest, reset_backend, search
from egregora.utils.cache import PipelineCache

logger = logging.getLogger(__name__)

# Constants
MAX_RAG_QUERY_BYTES = 30000


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
    pii_prevention: dict[str, Any] | None = None

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


def build_rag_context_for_prompt(
    table_markdown: str,
    *,
    top_k: int = 5,
    cache: PipelineCache | None = None,
) -> str:
    """Build RAG context by searching for similar posts.

    Args:
        table_markdown: Conversation content in markdown format to search against
        top_k: Number of similar posts to retrieve (default: 5)
        cache: Optional cache for RAG queries

    Returns:
        Formatted string with similar posts context, or empty string if no results

    """
    if not table_markdown or not table_markdown.strip():
        return ""

    try:
        # Use conversation content as search query (truncate if too long)
        query_text = table_markdown[:500]  # Use first 500 chars as query

        # Check cache if available
        cache_key = f"rag_context_{hash(query_text)}"
        if cache is not None:
            cached = cache.rag.get(cache_key)
            if cached is not None:
                logger.debug("RAG context cache hit")
                return cached

        # Execute RAG search
        reset_backend()

        request = RAGQueryRequest(text=query_text, top_k=top_k)
        response = search(request)

        if not response.hits:
            return ""

        # Build context from results
        parts = [
            "\n\n## Similar Posts (for context and inspiration):\n",
            "These are similar posts from previous conversations that might provide useful context:\n\n",
        ]

        for idx, hit in enumerate(response.hits, 1):
            similarity_pct = int(hit.score * 100)
            parts.append(f"### Similar Post {idx} (similarity: {similarity_pct}%)\n")
            parts.append(f"{hit.text[:500]}...\n\n")  # Truncate to 500 chars

        context = "".join(parts)

        # Cache the result
        if cache is not None:
            cache.rag.set(cache_key, context)

        logger.info("Built RAG context with %d similar posts", len(response.hits))
        return context

    except (ConnectionError, TimeoutError) as exc:
        logger.warning("RAG backend unavailable, continuing without context: %s", exc)
        return ""  # Non-critical: pipeline continues without RAG context
    except ValueError as exc:
        logger.warning("Invalid RAG query, continuing without context: %s", exc)
        return ""
    except (AttributeError, KeyError, TypeError) as exc:
        logger.exception("Malformed RAG response, continuing without context: %s", exc)
        return ""


def load_profiles_context(table: Table, profiles_dir: Any) -> str:
    """Load profiles for top active authors."""
    top_authors = get_active_authors(table, limit=20)
    if not top_authors:
        return ""
    logger.info("Loading profiles for %s active authors", len(top_authors))

    parts = [
        "\n\n## Active Participants (Profiles):\n",
        "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n",
    ]

    for author_uuid in top_authors:
        profile_content = read_profile(author_uuid, profiles_dir)
        parts.append(f"### Author: {author_uuid}\n")
        if profile_content:
            parts.append(f"{profile_content}\n\n")
        else:
            parts.append("(No profile yet - first appearance)\n\n")

    profiles_context = "".join(parts)
    logger.info("Profiles context: %s characters", len(profiles_context))
    return profiles_context


def build_writer_context(  # noqa: PLR0913
    table_with_str_uuids: Table,
    resources: WriterResources,
    cache: PipelineCache,
    config: EgregoraConfig,
    window_label: str,
    adapter_content_summary: str,
    adapter_generation_instructions: str,
) -> WriterContext:
    """Collect contextual inputs used when rendering the writer prompt."""
    messages_table = table_with_str_uuids.to_pyarrow()
    conversation_xml = build_conversation_xml(messages_table, resources.annotations_store)

    # Build RAG context if enabled
    if resources.retrieval_config.enabled:
        table_markdown = conversation_xml  # Use XML content for RAG query
        rag_context = build_rag_context_for_prompt(
            table_markdown,
            top_k=resources.retrieval_config.top_k,
            cache=cache,
        )
    else:
        rag_context = ""

    profiles_context = load_profiles_context(table_with_str_uuids, resources.profiles_dir)
    journal_memory = load_journal_memory(resources.output)
    active_authors = get_active_authors(table_with_str_uuids)

    format_instructions = resources.output.get_format_instructions()
    custom_instructions = config.writer.custom_instructions or ""
    if adapter_generation_instructions:
        custom_instructions = "\n\n".join(
            filter(None, [custom_instructions, adapter_generation_instructions])
        )

    # Build PII prevention context for LLM-native privacy protection
    pii_settings = config.privacy.pii_prevention.writer
    pii_prevention = None
    if pii_settings.enabled:
        pii_prevention = {
            "enabled": True,
            "scope": pii_settings.scope.value,
            "custom_definition": pii_settings.custom_definition
            if pii_settings.scope.value == "custom"
            else None,
            "apply_to_journals": pii_settings.apply_to_journals,
        }

    return WriterContext(
        conversation_xml=conversation_xml,
        rag_context=rag_context,
        profiles_context=profiles_context,
        journal_memory=journal_memory,
        active_authors=active_authors,
        format_instructions=format_instructions,
        custom_instructions=custom_instructions,
        source_context=adapter_content_summary,
        date_label=window_label,
        pii_prevention=pii_prevention,
    )
