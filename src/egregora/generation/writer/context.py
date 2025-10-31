"""Context building utilities for writer - RAG and profile loading."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ibis.expr.types import Table

from ...augmentation.profiler import get_active_authors, read_profile
from ...knowledge.rag import VectorStore, query_similar_posts
from ...utils import GeminiBatchClient

logger = logging.getLogger(__name__)


@dataclass
class RagResult:
    """Structured outcome from RAG query with failure reason tracking."""

    ok: bool
    text: str = ""
    reason: str = ""  # "success" | "no_hits" | "rag_error" | "disabled"
    records: list[dict[str, Any]] | None = None


def _query_rag_for_context(  # noqa: PLR0913
    table: Table,
    batch_client: GeminiBatchClient,
    rag_dir: Path,
    *,
    embedding_model: str,
    embedding_output_dimensionality: int = 3072,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    return_records: bool = False,
) -> RagResult | str | tuple[str, list[dict[str, Any]]]:
    """Query RAG system for similar previous posts.

    Returns a structured RagResult with observability data, or legacy string/tuple
    format when return_records is specified for backward compatibility.

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
            if return_records:
                return ("", [])
            return RagResult(ok=False, reason="no_hits")

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
        return RagResult(ok=True, text=rag_context, reason="success", records=records)
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True)
        if return_records:
            return ("", [])
        return RagResult(ok=False, reason="rag_error")


def _load_profiles_context(table: Table, profiles_dir: Path) -> str:
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
