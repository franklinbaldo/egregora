"""Context building utilities for writer - RAG and profile loading."""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from ibis.expr.types import Table
from returns.result import Failure, Result, Success

from egregora.agents.shared.author_profiles import get_active_authors, read_profile
from egregora.agents.shared.rag import VectorStore, build_rag_context_for_writer
from egregora.agents.shared.rag.chunker import chunk_markdown
from egregora.agents.shared.rag.embedder import embed_query_text

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


def consolidate_messages_to_markdown(table: Table) -> str:
    """Convert conversation table to markdown string for chunking.

    Supports both CONVERSATION_SCHEMA and IR_MESSAGE_SCHEMA via column detection:
    - timestamp/ts (temporal)
    - author/author_uuid (author identifier)
    - message/text (message content)

    Format:
        ## Message 1
        **Author:** uuid-123
        **Timestamp:** 2025-01-15 10:30:00

        Message text here...

        ## Message 2
        **Author:** uuid-456
        **Timestamp:** 2025-01-15 10:35:00

        Another message...

    Args:
        table: Conversation table (CONVERSATION_SCHEMA or IR_MESSAGE_SCHEMA)

    Returns:
        Markdown-formatted string suitable for chunk_markdown()

    Raises:
        ValueError: If required columns are not found in either schema

    """
    # Detect schema and map column names (CONVERSATION_SCHEMA vs IR_MESSAGE_SCHEMA)
    cols = table.columns

    # Timestamp: 'timestamp' (CONVERSATION) or 'ts' (IR)
    time_col = "timestamp" if "timestamp" in cols else "ts" if "ts" in cols else None

    # Author: 'author' (CONVERSATION) or 'author_uuid' (IR)
    author_col = "author" if "author" in cols else "author_uuid" if "author_uuid" in cols else None

    # Message: 'message' (CONVERSATION) or 'text' (IR)
    message_col = "message" if "message" in cols else "text" if "text" in cols else None

    # Validate required columns exist
    if not time_col or not author_col or not message_col:
        missing = []
        if not time_col:
            missing.append("timestamp/ts")
        if not author_col:
            missing.append("author/author_uuid")
        if not message_col:
            missing.append("message/text")
        raise ValueError(
            f"Table missing required columns: {', '.join(missing)}. "
            f"Available columns: {', '.join(cols)}"
        )

    # Deterministic ordering
    order_columns: list[Any] = [table[time_col]]

    # Add message_id or msg_id for secondary sorting (if available)
    if "message_id" in cols:
        order_columns.append(table["message_id"])
    elif "msg_id" in cols:
        order_columns.append(table["msg_id"])

    ordered_table = table.order_by(order_columns)
    df = ordered_table.select(time_col, author_col, message_col).execute()

    if df.empty:
        return ""

    lines = []
    for idx, row in enumerate(df.itertuples(), start=1):
        lines.append(f"## Message {idx}")
        # Use column position (1, 2, 3) instead of names since select() order is deterministic
        timestamp_val = getattr(row, time_col)
        author_val = getattr(row, author_col)
        message_val = getattr(row, message_col)

        lines.append(f"**Author:** {author_val}")
        lines.append(f"**Timestamp:** {timestamp_val}")
        lines.append("")
        lines.append(message_val)
        lines.append("")

    markdown = "\n".join(lines).strip()
    logger.debug(
        "Consolidated %d messages to markdown (%d chars) using schema: %s/%s/%s",
        len(df),
        len(markdown),
        time_col,
        author_col,
        message_col,
    )
    return markdown


def deduplicate_by_document(results: list[dict], n: int = 1) -> list[dict]:
    """Keep top-n chunks per document_id, ranked by similarity.

    Args:
        results: List of result dicts with 'document_id' and 'similarity' keys
        n: Number of chunks to keep per document (default: 1)

    Returns:
        Deduplicated list of results

    Example:
        >>> results = [
        ...     {'document_id': 'post-123', 'similarity': 0.90, 'content': 'chunk 0'},
        ...     {'document_id': 'post-123', 'similarity': 0.85, 'content': 'chunk 1'},
        ...     {'document_id': 'post-456', 'similarity': 0.88, 'content': 'chunk 0'},
        ... ]
        >>> deduplicate_by_document(results, n=1)
        [
            {'document_id': 'post-123', 'similarity': 0.90, 'content': 'chunk 0'},
            {'document_id': 'post-456', 'similarity': 0.88, 'content': 'chunk 0'}
        ]

    """
    # Group by document_id
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        doc_id = result.get("document_id")
        if doc_id:
            by_doc[doc_id].append(result)

    # Keep top-n per document
    deduplicated = []
    for doc_id, doc_results in by_doc.items():
        # Sort by similarity (descending)
        sorted_results = sorted(doc_results, key=lambda x: x.get("similarity", 0.0), reverse=True)
        deduplicated.extend(sorted_results[:n])

    logger.debug(
        "Deduplication: %d results → %d unique documents (n=%d per doc)", len(results), len(deduplicated), n
    )

    return deduplicated


def query_rag_per_chunk(
    chunks: list[str],
    store: VectorStore,
    embedding_model: str,
    top_k: int = 5,
    min_similarity_threshold: float = 0.7,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> list[dict]:
    """Query RAG for each chunk and collect all results.

    Args:
        chunks: List of text chunks from chunk_markdown()
        store: VectorStore instance
        embedding_model: Embedding model name (e.g., "google-gla:gemini-embedding-001")
        top_k: Number of results per chunk query
        min_similarity_threshold: Minimum cosine similarity (0-1)
        retrieval_mode: "ann" (approximate) or "exact" (brute-force)
        retrieval_nprobe: ANN nprobe parameter (IVF index)
        retrieval_overfetch: Candidate multiplier for ANN

    Returns:
        List of result dicts with keys:
            - content: chunk text
            - similarity: cosine similarity score
            - document_id: unique document identifier
            - post_slug: post slug (if post document)
            - post_title: post title
            - chunk_index: chunk index within document
            - metadata: additional metadata

    """
    all_results = []

    for i, chunk in enumerate(chunks):
        logger.debug("Querying RAG for chunk %d/%d", i + 1, len(chunks))
        query_vec = embed_query_text(chunk, model=embedding_model)
        results = store.search(
            query_vec=query_vec,
            top_k=top_k,
            min_similarity_threshold=min_similarity_threshold,
            mode=retrieval_mode,
            nprobe=retrieval_nprobe,
            overfetch=retrieval_overfetch,
        )

        # Convert Ibis table to dict records
        df = results.execute()
        chunk_results = df.to_dict("records")
        all_results.extend(chunk_results)

    logger.info("Collected %d total results from %d chunks", len(all_results), len(chunks))
    return all_results


def build_rag_context_for_prompt(
    table_markdown: str,
    rag_dir: Path,
    client: genai.Client,
    *,
    embedding_model: str,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    top_k: int = 5,
    use_pydantic_helpers: bool = False,
) -> str:
    """Build a lightweight RAG context string from the conversation markdown.

    This mirrors the pattern from the Pydantic-AI RAG example: embed the query,
    fetch similar chunks, and convert them into a short "Relevant context" block
    for the LLM prompt.

    All embeddings use fixed 768 dimensions.

    Args:
        table_markdown: Conversation text to use as query
        rag_dir: Directory containing vector store
        client: Gemini client
        embedding_model: Embedding model name
        retrieval_mode: "ann" or "exact"
        retrieval_nprobe: ANN nprobe
        retrieval_overfetch: ANN overfetch
        top_k: Number of results
        use_pydantic_helpers: If True, use async pydantic_helpers instead of sync code

    Returns:
        Formatted RAG context string

    """
    if use_pydantic_helpers:
        return asyncio.run(
            build_rag_context_for_writer(
                query=table_markdown,
                client=client,
                rag_dir=rag_dir,
                embedding_model=embedding_model,
                top_k=top_k,
                retrieval_mode=retrieval_mode,
                retrieval_nprobe=retrieval_nprobe,
                retrieval_overfetch=retrieval_overfetch,
            )
        )
    if not table_markdown.strip():
        return ""
    query_vector = embed_query_text(table_markdown, model=embedding_model)
    store = VectorStore(rag_dir / "chunks.parquet")
    search_results = store.search(
        query_vec=query_vector,
        top_k=top_k,
        min_similarity_threshold=0.7,
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
        lines.append(f"- Tags: {(', '.join(tags) if tags else 'none')}")
        if similarity is not None:
            lines.append(f"- Similarity: {float(similarity):.2f}")
        lines.append("")
    return "\n".join(lines).strip()


def _query_rag_for_context(
    table: Table,
    _client: genai.Client,
    rag_dir: Path,
    *,
    embedding_model: str,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    return_records: bool = False,
) -> Result[RagContext, str] | tuple[str, list[dict[str, Any]]]:
    """Query RAG using chunked conversation approach.

    NEW IMPLEMENTATION (Phase 8):
    1. Consolidate messages to markdown
    2. Chunk markdown (paragraph boundaries, 1800 tokens, 150 overlap)
    3. Query RAG for each chunk (top-5 per chunk)
    4. Deduplicate: keep top-1 chunk per document
    5. Sort by similarity and return top-5 overall

    This provides better topic coverage for multi-topic conversations
    compared to the old single-query approach.

    All embeddings use fixed 768 dimensions.

    Args:
        table: Conversation table to query
        client: Gemini client for embeddings (unused in new implementation)
        rag_dir: Directory containing RAG vector store
        embedding_model: Model name for embeddings
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

        # Step 1: Consolidate to markdown
        markdown = consolidate_messages_to_markdown(table)
        if not markdown.strip():
            logger.info("No messages to consolidate for RAG query")
            if return_records:
                return ("", [])
            return Failure(RagErrorReason.NO_HITS)

        # Step 2: Chunk markdown (reuse existing chunker)
        chunks = chunk_markdown(markdown, max_tokens=1800, overlap_tokens=150)
        logger.info("Chunked conversation into %d chunks for RAG query", len(chunks))

        # Step 3: Query RAG for each chunk
        all_results = query_rag_per_chunk(
            chunks=chunks,
            store=store,
            embedding_model=embedding_model,
            top_k=5,
            min_similarity_threshold=0.7,
            retrieval_mode=retrieval_mode,
            retrieval_nprobe=retrieval_nprobe,
            retrieval_overfetch=retrieval_overfetch,
        )

        if not all_results:
            logger.info("No similar posts found (0 results from all chunks)")
            if return_records:
                return ("", [])
            return Failure(RagErrorReason.NO_HITS)

        # Step 4: Deduplicate (keep top-1 per document)
        deduped = deduplicate_by_document(all_results, n=1)

        # Step 5: Sort by similarity and take top-5
        final_results = sorted(deduped, key=lambda x: x.get("similarity", 0.0), reverse=True)[:5]

        logger.info(
            "RAG query complete: %d chunks → %d results → %d deduped → %d final",
            len(chunks),
            len(all_results),
            len(deduped),
            len(final_results),
        )

        # Step 6: Format context (reuse existing formatting logic)
        rag_text = "\n\n## Related Previous Posts (for continuity and linking):\n"
        rag_text += "You can reference these posts in your writing to maintain conversation continuity.\n\n"

        for row in final_results:
            rag_text += f"### [{row['post_title']}] ({row['post_date']})\n"
            rag_text += f"{row['content'][:400]}...\n"
            rag_text += f"- Tags: {(', '.join(row['tags']) if row.get('tags') else 'none')}\n"
            rag_text += f"- Similarity: {row['similarity']:.2f}\n\n"

        if return_records:
            return (rag_text, final_results)
        return Success(RagContext(text=rag_text, records=final_results))

    except Exception as e:
        logger.error("RAG query failed: %s", e, exc_info=True)
        if return_records:
            return ("", [])
        return Failure(RagErrorReason.SYSTEM_ERROR)


def _load_profiles_context(table: Table, profiles_dir: Path) -> str:
    """Load profiles for top active authors."""
    top_authors = get_active_authors(table, limit=20)
    if not top_authors:
        return ""
    logger.info("Loading profiles for %s active authors", len(top_authors))
    profiles_context = "\n\n## Active Participants (Profiles):\n"
    profiles_context += "Understanding the participants helps you write posts that match their style, voice, and interests.\n\n"
    for author_uuid in top_authors:
        profile_content = read_profile(author_uuid, profiles_dir)
        if profile_content:
            profiles_context += f"### Author: {author_uuid}\n"
            profiles_context += f"{profile_content}\n\n"
        else:
            profiles_context += f"### Author: {author_uuid}\n"
            profiles_context += "(No profile yet - first appearance)\n\n"
    logger.info("Profiles context: %s characters", len(profiles_context))
    return profiles_context
