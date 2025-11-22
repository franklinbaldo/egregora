"""Retrieval operations for RAG knowledge system.

Provides similarity search and result formatting for querying the vector store.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis
from ibis.expr.types import Table

from egregora.agents.shared.rag.embedder import embed_query_text
from egregora.agents.shared.rag.store import DEDUP_MAX_RANK, VectorStore
from egregora.database.duckdb_manager import DuckDBStorageManager

if TYPE_CHECKING:
    import google.generativeai as genai

logger = logging.getLogger(__name__)


def query_similar_posts(  # noqa: PLR0913
    table: Table,
    store: VectorStore,
    *,
    embedding_model: str,
    top_k: int = 5,
    deduplicate: bool = True,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> Table:
    """Find similar previous blog posts for a period's table."""
    msg_count = table.count().execute()
    logger.info("Querying similar posts for period with %s messages", msg_count)
    query_text = table.execute().to_csv(sep="|", index=False)
    logger.debug("Query text length: %s chars", len(query_text))
    query_vec = embed_query_text(query_text, model=embedding_model)
    results = store.search(
        query_vec=query_vec,
        top_k=top_k * 3 if deduplicate else top_k,
        min_similarity_threshold=0.7,
        mode=retrieval_mode,
        nprobe=retrieval_nprobe,
        overfetch=retrieval_overfetch,
    )
    if results.count().execute() == 0:
        logger.info("No similar posts found")
        return results
    result_count = results.count().execute()
    logger.info("Found %s similar chunks", result_count)
    if deduplicate:
        window = ibis.window(group_by="post_slug", order_by=ibis.desc("similarity"))
        results = (
            results.order_by(ibis.desc("similarity"))
            .mutate(_rank=ibis.row_number().over(window))
            .filter(lambda t: t._rank < DEDUP_MAX_RANK)
            .drop("_rank")
            .order_by(ibis.desc("similarity"))
            .limit(top_k)
        )
        dedup_count = results.count().execute()
        logger.info("After deduplication: %s unique posts", dedup_count)
    return results


def query_media(  # noqa: PLR0913
    query: str,
    store: VectorStore,
    media_types: list[str] | None = None,
    top_k: int = 5,
    min_similarity_threshold: float = 0.7,
    *,
    deduplicate: bool = True,
    embedding_model: str,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> Table:
    """Search for relevant media by description or topic."""
    logger.info("Searching media for: %s", query)
    query_vec = embed_query_text(query, model=embedding_model)
    results = store.search(
        query_vec=query_vec,
        top_k=top_k * 3 if deduplicate else top_k,
        min_similarity_threshold=min_similarity_threshold,
        document_type="media",
        media_types=media_types,
        mode=retrieval_mode,
        nprobe=retrieval_nprobe,
        overfetch=retrieval_overfetch,
    )
    result_count = results.count().execute()
    if result_count == 0:
        logger.info("No matching media found")
        return results
    logger.info("Found %s matching media chunks", result_count)
    if deduplicate:
        window = ibis.window(group_by="media_uuid", order_by=ibis.desc("similarity"))
        results = (
            results.order_by(ibis.desc("similarity"))
            .mutate(_rank=ibis.row_number().over(window))
            .filter(lambda t: t._rank < DEDUP_MAX_RANK)
            .drop("_rank")
            .order_by(ibis.desc("similarity"))
            .limit(top_k)
        )
        dedup_count = results.count().execute()
        logger.info("After deduplication: %s unique media files", dedup_count)
    return results


async def find_relevant_docs(  # noqa: PLR0913
    query: str,
    *,
    _client: genai.Client | None = None,  # Kept for compatibility but unused by direct implementation
    rag_dir: Path,
    storage: DuckDBStorageManager,
    embedding_model: str,
    top_k: int = 5,
    min_similarity_threshold: float = 0.7,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> list[dict[str, Any]]:
    """Find relevant documents from the vector store."""
    try:
        query_vector = embed_query_text(query, model=embedding_model)
        store = VectorStore(rag_dir / "chunks.parquet", storage=storage)
        results = store.search(
            query_vec=query_vector,
            top_k=top_k,
            min_similarity_threshold=min_similarity_threshold,
            mode=retrieval_mode,
            nprobe=retrieval_nprobe,
            overfetch=retrieval_overfetch,
        )
        dataframe = results.execute()
        if getattr(dataframe, "empty", False):
            logger.info("No relevant docs found for query: %s", query[:50])
            return []
        records = dataframe.to_dict("records")
        logger.info("Found %d relevant docs for query: %s", len(records), query[:50])
        return [
            {
                "content": record.get("content", ""),
                "post_title": record.get("post_title", "Untitled"),
                "post_date": str(record.get("post_date", "")),
                "tags": record.get("tags", []),
                "similarity": float(record.get("similarity", 0.0)),
                "post_slug": record.get("post_slug", ""),
            }
            for record in records
        ]
    except Exception as exc:
        logger.error("Failed to find relevant docs: %s", exc, exc_info=True)
        logger.info("RAG retrieval failed: %s", str(exc))
        return []


def format_rag_context(docs: list[dict[str, Any]]) -> str:
    """Format retrieved documents into context string."""
    if not docs:
        return ""
    lines = [
        "## Related Previous Posts (for continuity and linking):",
        "You can reference these posts in your writing to maintain conversation continuity.\n",
    ]
    for doc in docs:
        title = doc.get("post_title", "Untitled")
        post_date = doc.get("post_date", "")
        content = doc.get("content", "")[:400]
        tags = doc.get("tags", [])
        similarity = doc.get("similarity")
        lines.append(f"### [{title}] ({post_date})")
        lines.append(f"{content}...")
        lines.append(f"- Tags: {(', '.join(tags) if tags else 'none')}")
        if similarity is not None:
            lines.append(f"- Similarity: {similarity:.2f}")
        lines.append("")
    return "\n".join(lines).strip()


async def build_rag_context_for_writer(  # noqa: PLR0913
    query: str,
    *,
    client: genai.Client | None = None,
    rag_dir: Path,
    storage: DuckDBStorageManager,
    embedding_model: str,
    top_k: int = 5,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> str:
    r"""Build RAG context string for writer agent."""
    docs = await find_relevant_docs(
        query,
        _client=client,
        rag_dir=rag_dir,
        storage=storage,
        embedding_model=embedding_model,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
    )
    return format_rag_context(docs)


__all__ = [
    "format_rag_context",
    "query_media",
    "query_similar_posts",
]
