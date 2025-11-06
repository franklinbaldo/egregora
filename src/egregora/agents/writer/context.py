"""Context building utilities for writer - RAG and profile loading."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from ibis.expr.types import Table
from returns.result import Failure, Result, Success

from egregora.agents.tools.profiler import get_active_authors, read_profile
from egregora.agents.tools.rag import (
    VectorStore,
    build_rag_context_for_writer,
    query_similar_posts,
)
from egregora.agents.tools.rag.embedder import embed_query
from egregora.utils.logfire_config import logfire_info, logfire_span

logger = logging.getLogger(__name__)


@dataclass
class RagContext:
    """RAG query result with formatted text and metadata."""

    text: str
    records: list[dict[str, Any]]


class RagErrorReason:
    """Error reason constants for RAG failures."""

    NO_HITS = "no_hits"
    SYSTEM_ERROR = "rag_error"


def build_rag_context_for_prompt(  # noqa: PLR0913
    table_markdown: str,
    rag_dir: Path,
    client: genai.Client,
    *,
    embedding_model: str,
    embedding_output_dimensionality: int = 3072,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    top_k: int = 5,
    use_pydantic_helpers: bool = False,
) -> str:
    """
    Build a lightweight RAG context string from the conversation markdown.

    This mirrors the pattern from the Pydantic-AI RAG example: embed the query,
    fetch similar chunks, and convert them into a short "Relevant context" block
    for the LLM prompt.

    Args:
        table_markdown: Conversation text to use as query
        rag_dir: Directory containing vector store
        client: Gemini client
        embedding_model: Embedding model name
        embedding_output_dimensionality: Embedding dimension
        retrieval_mode: "ann" or "exact"
        retrieval_nprobe: ANN nprobe
        retrieval_overfetch: ANN overfetch
        top_k: Number of results
        use_pydantic_helpers: If True, use async pydantic_helpers instead of sync code

    Returns:
        Formatted RAG context string
    """
    # Use new Pydantic AI helpers if requested
    if use_pydantic_helpers:
        import asyncio

        return asyncio.run(
            build_rag_context_for_writer(
                query=table_markdown,
                client=client,
                rag_dir=rag_dir,
                embedding_model=embedding_model,
                output_dimensionality=embedding_output_dimensionality,
                top_k=top_k,
                retrieval_mode=retrieval_mode,
                retrieval_nprobe=retrieval_nprobe,
                retrieval_overfetch=retrieval_overfetch,
            )
        )
    if not table_markdown.strip():
        return ""

    try:
        query_vector = embed_query(
            table_markdown,
            model=embedding_model,
            output_dimensionality=embedding_output_dimensionality,
        )
        store = VectorStore(rag_dir / "chunks.parquet")
        search_results = store.search(
            query_vec=query_vector,
            top_k=top_k,
            min_similarity=0.7,
            mode=retrieval_mode,
            nprobe=retrieval_nprobe,
            overfetch=retrieval_overfetch,
        )

        df = search_results.execute()
        if getattr(df, "empty", False):
            logger.info("Writer RAG: no similar posts found for query")
            return ""

        records = df.to_dict("records")
        if not records:
            return ""

        lines = [
            "## Related Previous Posts (for continuity and linking):",
            "You can reference these posts in your writing to maintain conversation continuity.\n",
        ]

        for row in records:
            title = row.get("post_title") or "Untitled"
            post_date = row.get("post_date") or ""
            snippet = (row.get("content") or "")[:400]
            tags = row.get("tags") or []
            similarity = row.get("similarity")

            lines.append(f"### [{title}] ({post_date})")
            lines.append(f"{snippet}...")
            lines.append(f"- Tags: {', '.join(tags) if tags else 'none'}")
            if similarity is not None:
                lines.append(f"- Similarity: {float(similarity):.2f}")
            lines.append("")

        return "\n".join(lines).strip()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Writer RAG context failed: %s", exc, exc_info=True)
        return ""


def _query_rag_for_context(  # noqa: PLR0913
    table: Table,
    client: genai.Client,
    rag_dir: Path,
    *,
    embedding_model: str,
    embedding_output_dimensionality: int = 3072,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    return_records: bool = False,
) -> Result[RagContext, str] | tuple[str, list[dict[str, Any]]]:
    """Query RAG system for similar previous posts.

    Returns a Result[RagContext, str] with observability data, or legacy tuple
    format when return_records is specified for backward compatibility.

    Args:
        table: Conversation table to query
        client: Gemini client for embeddings
        rag_dir: Directory containing RAG vector store
        embedding_model: Model name for embeddings
        embedding_output_dimensionality: Embedding dimension size
        retrieval_mode: "ann" or "exact" retrieval mode
        retrieval_nprobe: ANN nprobe parameter
        retrieval_overfetch: ANN overfetch multiplier
        return_records: If True, return legacy (str, list) tuple for backward compatibility

    Returns:
        Result[RagContext, str] where:
        - Success contains RagContext with text and records
        - Failure contains error reason ("no_hits" or "rag_error")
        OR tuple[str, list] if return_records=True (legacy mode)

    Examples:
        >>> result = _query_rag_for_context(table, client, rag_dir, embedding_model="...")
        >>> if isinstance(result, Success):
        ...     print(result.unwrap().text)
    """

    try:
        with logfire_span("rag_query", query_type="similar_posts"):
            store = VectorStore(rag_dir / "chunks.parquet")
            similar_posts = query_similar_posts(
                table,
                store,
                embedding_model=embedding_model,
                top_k=5,
                deduplicate=True,
                output_dimensionality=embedding_output_dimensionality,
                retrieval_mode=retrieval_mode,
                retrieval_nprobe=retrieval_nprobe,
                retrieval_overfetch=retrieval_overfetch,
            )

            if similar_posts.count().execute() == 0:
                logger.info("No similar previous posts found")
                logfire_info("RAG query completed", results_count=0)
                if return_records:
                    return ("", [])
                return Failure(RagErrorReason.NO_HITS)

            post_count = similar_posts.count().execute()
            logger.info(f"Found {post_count} similar previous posts")
            logfire_info("RAG query completed", results_count=post_count)
        rag_text = "\n\n## Related Previous Posts (for continuity and linking):\n"
        rag_text += "You can reference these posts in your writing to maintain conversation continuity.\n\n"

        records = similar_posts.execute().to_dict("records")
        for row in records:
            rag_text += f"### [{row['post_title']}] ({row['post_date']})\n"
            rag_text += f"{row['content'][:400]}...\n"
            rag_text += f"- Tags: {', '.join(row['tags']) if row['tags'] else 'none'}\n"
            rag_text += f"- Similarity: {row['similarity']:.2f}\n\n"

        if return_records:
            return rag_text, records
        return Success(RagContext(text=rag_text, records=records))
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True)
        if return_records:
            return ("", [])
        return Failure(RagErrorReason.SYSTEM_ERROR)


def _load_profiles_context(table: Table, profiles_dir: Path) -> str:
    """Load profiles for top active authors."""
    top_authors = get_active_authors(table, limit=20)
    if not top_authors:
        return ""

    logger.info(f"Loading profiles for {len(top_authors)} active authors")
    profiles_context = "\n\n## Active Participants (Profiles):\n"
    profiles_context += (
        "Understanding the participants helps you write posts that match "
        "their style, voice, and interests.\n\n"
    )

    for author_uuid in top_authors:
        profile_content = read_profile(author_uuid, profiles_dir)

        if profile_content:
            profiles_context += f"### Author: {author_uuid}\n"
            profiles_context += f"{profile_content}\n\n"
        else:
            # No profile yet (first time seeing this author)
            profiles_context += f"### Author: {author_uuid}\n"
            profiles_context += "(No profile yet - first appearance)\n\n"

    logger.info(f"Profiles context: {len(profiles_context)} characters")
    return profiles_context
