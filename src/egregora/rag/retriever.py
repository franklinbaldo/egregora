"""High-level retrieval and indexing functions."""

import logging
from pathlib import Path
import polars as pl
from google import genai

from .chunker import chunk_document
from .embedder import embed_chunks, embed_query
from .store import VectorStore

logger = logging.getLogger(__name__)


async def index_post(
    post_path: Path,
    client: genai.Client,
    store: VectorStore,
) -> int:
    """
    Chunk, embed, and index a blog post.

    Args:
        post_path: Path to markdown file with YAML frontmatter
        client: Gemini client
        store: Vector store

    Returns:
        Number of chunks indexed
    """
    logger.info(f"Indexing post: {post_path.name}")

    # Chunk document
    chunks = chunk_document(post_path, max_tokens=1800)

    if not chunks:
        logger.warning(f"No chunks generated from {post_path.name}")
        return 0

    # Extract content for embedding
    chunk_texts = [chunk['content'] for chunk in chunks]

    # Embed chunks (RETRIEVAL_DOCUMENT task type)
    embeddings = await embed_chunks(
        chunk_texts,
        client,
        task_type="RETRIEVAL_DOCUMENT",
        output_dim=3072,
    )

    # Build DataFrame for storage
    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        metadata = chunk['metadata']

        rows.append({
            "chunk_id": f"{chunk['post_slug']}_{i}",
            "post_slug": chunk['post_slug'],
            "post_title": chunk['post_title'],
            "post_date": metadata.get('date'),
            "chunk_index": i,
            "content": chunk['content'],
            "embedding": embedding,
            "tags": metadata.get('tags', []),
            "authors": metadata.get('authors', []),
            "category": metadata.get('category'),
        })

    chunks_df = pl.DataFrame(rows)

    # Add to store
    store.add(chunks_df)

    logger.info(f"Indexed {len(chunks)} chunks from {post_path.name}")

    return len(chunks)


async def query_similar_posts(
    df: pl.DataFrame,
    client: genai.Client,
    store: VectorStore,
    top_k: int = 5,
    deduplicate: bool = True,
) -> pl.DataFrame:
    """
    Find similar previous blog posts for a period's DataFrame.

    Strategy:
    1. Convert DataFrame to text (markdown table)
    2. Embed using RETRIEVAL_QUERY task type
    3. Search vector store with cosine similarity
    4. Optionally deduplicate (keep best chunk per post)

    Args:
        df: Period's DataFrame (messages)
        client: Gemini client
        store: Vector store
        top_k: Number of results to return
        deduplicate: Keep only 1 chunk per post (highest similarity)

    Returns:
        DataFrame with columns: [post_title, content, similarity, post_date, tags, ...]
    """
    logger.info(f"Querying similar posts for period with {len(df)} messages")

    # Convert DataFrame to markdown table for embedding
    query_text = df.write_csv(separator="|")

    logger.debug(f"Query text length: {len(query_text)} chars")

    # Embed query (use RETRIEVAL_QUERY task type)
    query_vec = await embed_query(query_text, client, output_dim=3072)

    # Search vector store
    results = store.search(
        query_vec=query_vec,
        top_k=top_k * 3 if deduplicate else top_k,  # Get extras for dedup
        min_similarity=0.7,
    )

    if results.is_empty():
        logger.info("No similar posts found")
        return results

    logger.info(f"Found {len(results)} similar chunks")

    # Deduplicate: keep only best chunk per post
    if deduplicate:
        results = (
            results
            .sort("similarity", descending=True)
            .group_by("post_slug")
            .first()
            .sort("similarity", descending=True)
            .head(top_k)
        )

        logger.info(f"After deduplication: {len(results)} unique posts")

    return results
