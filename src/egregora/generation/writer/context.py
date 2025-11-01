"""Context building utilities for writer - RAG and profile loading."""

import logging
from pathlib import Path
from typing import Annotated, Any

from ibis.expr.types import Table

from ...augmentation.profiler import get_active_authors, read_profile
from ...knowledge.rag import VectorStore, query_similar_posts
from ...utils import GeminiBatchClient

logger = logging.getLogger(__name__)


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
) -> str | tuple[str, list[dict[str, Any]]]:
    """Query RAG system for similar previous posts.

    When ``return_records`` is ``True`` both the formatted markdown string and the raw
    records are returned. This is helpful for callers that need to persist the RAG output
    for later inspection while keeping backward compatibility with existing string-only
    callers.
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
            return ("", []) if return_records else ""

        post_count = similar_posts.count().execute()
        logger.info(f"Found {post_count} similar previous posts")
        rag_context = "\n\n## Related Previous Posts (for continuity and linking):\n"
        rag_context += (
            "You can reference these posts in your writing to maintain conversation continuity.\n\n"
        )

        records = similar_posts.execute().to_dict("records")
        for row in records:
            rag_context += f"### [{row['post_title']}] ({row['post_date']})\n"
            rag_context += f"{row['content'][:400]}...\n"
            rag_context += f"- Tags: {', '.join(row['tags']) if row['tags'] else 'none'}\n"
            rag_context += f"- Similarity: {row['similarity']:.2f}\n\n"

        if return_records:
            return rag_context, records
        return rag_context
    except Exception as e:
        logger.warning(f"RAG query failed: {e}")
        return ("", []) if return_records else ""


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
