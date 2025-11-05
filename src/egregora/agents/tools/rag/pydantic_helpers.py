"""Pydantic AI compatible RAG helpers.

This module provides integration between egregora's DuckDB vector store
and Pydantic AI's rag_context() helper for standardized retrieval prompts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from egregora.agents.tools.rag.embedder import embed_query
from egregora.agents.tools.rag.store import VectorStore
from egregora.utils.batch import GeminiBatchClient
from egregora.utils.logfire_config import logfire_info, logfire_span

logger = logging.getLogger(__name__)


async def find_relevant_docs(
    query: str,
    *,
    batch_client: GeminiBatchClient,
    rag_dir: Path,
    embedding_model: str,
    output_dimensionality: int = 3072,
    top_k: int = 5,
    min_similarity: float = 0.7,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> list[dict[str, Any]]:
    """Find relevant documents from the vector store.

    This is a Pydantic AI compatible retrieval function that can be used
    with pydantic_ai's rag_context() helper.

    Args:
        query: Natural language query
        batch_client: Gemini batch client for embeddings
        rag_dir: Directory containing vector store
        embedding_model: Embedding model name
        output_dimensionality: Embedding dimension size
        top_k: Number of results to return
        min_similarity: Minimum similarity threshold (0-1)
        retrieval_mode: "ann" or "exact" retrieval
        retrieval_nprobe: ANN nprobe parameter
        retrieval_overfetch: ANN overfetch multiplier

    Returns:
        List of document dictionaries with keys:
        - content: Document text
        - post_title: Title of the post
        - post_date: Publication date
        - tags: List of tags
        - similarity: Similarity score (0-1)

    Example:
        >>> docs = await find_relevant_docs(
        ...     "quantum computing",
        ...     batch_client=client,
        ...     rag_dir=Path("./rag"),
        ...     embedding_model="models/gemini-embedding-001"
        ... )
        >>> for doc in docs:
        ...     print(f"{doc['post_title']}: {doc['similarity']:.2f}")
    """
    with logfire_span("find_relevant_docs", query_length=len(query), top_k=top_k):
        try:
            # Embed query
            query_vector = embed_query(
                query,
                batch_client,
                model=embedding_model,
                output_dimensionality=output_dimensionality,
            )

            # Query vector store
            store = VectorStore(rag_dir / "chunks.parquet")
            results = store.search(
                query_vec=query_vector,
                top_k=top_k,
                min_similarity=min_similarity,
                mode=retrieval_mode,
                nprobe=retrieval_nprobe,
                overfetch=retrieval_overfetch,
            )

            # Execute and convert to list of dicts
            df = results.execute()

            if getattr(df, "empty", False):
                logfire_info("No relevant docs found", query=query)
                return []

            records = df.to_dict("records")
            logfire_info("Found relevant docs", count=len(records), query=query)

            # Format for Pydantic AI
            docs = [
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

            return docs

        except Exception as exc:
            logger.error("Failed to find relevant docs: %s", exc, exc_info=True)
            logfire_info("RAG retrieval failed", error=str(exc))
            return []


def format_rag_context(docs: list[dict[str, Any]]) -> str:
    """Format retrieved documents into context string.

    This provides the same format as the legacy _query_rag_for_context
    for backward compatibility.

    Args:
        docs: List of document dictionaries from find_relevant_docs()

    Returns:
        Formatted context string for LLM prompt
    """
    if not docs:
        return ""

    lines = [
        "## Related Previous Posts (for continuity and linking):",
        "You can reference these posts in your writing to maintain conversation continuity.\n",
    ]

    for doc in docs:
        title = doc.get("post_title", "Untitled")
        post_date = doc.get("post_date", "")
        content = doc.get("content", "")[:400]  # First 400 chars
        tags = doc.get("tags", [])
        similarity = doc.get("similarity")

        lines.append(f"### [{title}] ({post_date})")
        lines.append(f"{content}...")
        lines.append(f"- Tags: {', '.join(tags) if tags else 'none'}")
        if similarity is not None:
            lines.append(f"- Similarity: {similarity:.2f}")
        lines.append("")

    return "\n".join(lines).strip()


async def build_rag_context_for_writer(
    query: str,
    *,
    batch_client: GeminiBatchClient,
    rag_dir: Path,
    embedding_model: str,
    output_dimensionality: int = 3072,
    top_k: int = 5,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> str:
    """Build RAG context string for writer agent.

    High-level helper that combines find_relevant_docs() and format_rag_context().

    Args:
        query: Natural language query (usually conversation markdown)
        batch_client: Gemini batch client
        rag_dir: Vector store directory
        embedding_model: Embedding model name
        output_dimensionality: Embedding dimension
        top_k: Number of results
        retrieval_mode: "ann" or "exact"
        retrieval_nprobe: ANN nprobe
        retrieval_overfetch: ANN overfetch

    Returns:
        Formatted context string ready for LLM prompt

    Example:
        >>> context = await build_rag_context_for_writer(
        ...     "Discussion about quantum computing...",
        ...     batch_client=client,
        ...     rag_dir=Path("./rag"),
        ...     embedding_model="models/gemini-embedding-001"
        ... )
        >>> prompt = f"{conversation}\n\n{context}"
    """
    docs = await find_relevant_docs(
        query,
        batch_client=batch_client,
        rag_dir=rag_dir,
        embedding_model=embedding_model,
        output_dimensionality=output_dimensionality,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
        retrieval_nprobe=retrieval_nprobe,
        retrieval_overfetch=retrieval_overfetch,
    )

    return format_rag_context(docs)
