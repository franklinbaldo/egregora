"""Context building utilities for writer - RAG and profile loading."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from ibis.expr.types import Table
from returns.result import Failure, Result, Success

from ...augmentation.profiler import get_active_authors, read_profile
from ...knowledge.rag import VectorStore, query_similar_posts
from ...utils import GeminiBatchClient

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


def _query_rag_for_context(  # noqa: PLR0913
    table: Annotated[Table, "The table of messages to query for"],
    batch_client: Annotated[GeminiBatchClient, "A Gemini client for batch processing"],
    rag_dir: Annotated[Path, "The directory of the RAG index"],
    *,
    embedding_model: Annotated[str, "The name of the embedding model to use"],
    embedding_output_dimensionality: Annotated[
        int, "The output dimensionality of the embedding model"
    ] = 3072,
    retrieval_mode: Annotated[
        str, "The retrieval mode for the RAG query ('ann' or 'exact')"
    ] = "ann",
    retrieval_nprobe: Annotated[int | None, "The number of probes for ANN retrieval"] = None,
    retrieval_overfetch: Annotated[int | None, "The overfetch factor for ANN retrieval"] = None,
    return_records: Annotated[
        bool, "Whether to return the raw records along with the formatted string"
    ] = False,
) -> Result[RagContext, str] | tuple[str, list[dict[str, Any]]]:
    """Query RAG system for similar previous posts.

    Returns a Result[RagContext, str] with observability data, or legacy tuple
    format when return_records is specified for backward compatibility.

    Args:
        table: Conversation table to query
        batch_client: Gemini batch client for embeddings
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
        store = VectorStore(rag_dir / "chunks.parquet")
        similar_posts = query_similar_posts(
            table,
            batch_client,
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
            if return_records:
                return ("", [])
            return Failure(RagErrorReason.NO_HITS)

        post_count = similar_posts.count().execute()
        logger.info(f"Found {post_count} similar previous posts")
        rag_text = "\n\n## Related Previous Posts (for continuity and linking):\n"
        rag_text += (
            "You can reference these posts in your writing to maintain conversation continuity.\n\n"
        )

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


def _load_profiles_context(
    table: Annotated[Table, "The table of messages to extract authors from"],
    profiles_dir: Annotated[Path, "The directory where profiles are stored"],
) -> Annotated[str, "The formatted context string of author profiles"]:
    """Load profiles for top active authors."""
    top_authors = get_active_authors(table, limit=20)
    if not top_authors:
        return ""

    logger.info(f"Loading profiles for {len(top_authors)} active authors")
    profiles_context = "\n\n## Active Participants (Profiles):\n"
    profiles_context += "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n"

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
