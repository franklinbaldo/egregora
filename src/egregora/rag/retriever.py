"""High-level retrieval and indexing functions."""

import logging
import re
from datetime import datetime
from pathlib import Path

import ibis
from google import genai
from ibis.expr.types import Table

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
    chunk_texts = [chunk["content"] for chunk in chunks]

    # Embed chunks (RETRIEVAL_DOCUMENT task type)
    embeddings = await embed_chunks(
        chunk_texts,
        client,
        task_type="RETRIEVAL_DOCUMENT",
        output_dim=3072,
    )

    # Build DataFrame for storage
    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
        metadata = chunk["metadata"]

        rows.append(
            {
                "chunk_id": f"{chunk['post_slug']}_{i}",
                "document_type": "post",
                "document_id": chunk["post_slug"],
                "post_slug": chunk["post_slug"],
                "post_title": chunk["post_title"],
                "post_date": metadata.get("date"),
                "media_uuid": None,
                "media_type": None,
                "media_path": None,
                "original_filename": None,
                "message_date": None,
                "author_uuid": None,
                "chunk_index": i,
                "content": chunk["content"],
                "embedding": embedding,
                "tags": metadata.get("tags", []),
                "category": metadata.get("category"),
            }
        )

    chunks_df = ibis.memtable(rows)

    # Add to store
    store.add(chunks_df)

    logger.info(f"Indexed {len(chunks)} chunks from {post_path.name}")

    return len(chunks)


async def query_similar_posts(
    df: Table,
    client: genai.Client,
    store: VectorStore,
    top_k: int = 5,
    deduplicate: bool = True,
) -> Table:
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
    msg_count = df.count().execute()
    logger.info(f"Querying similar posts for period with {msg_count} messages")

    # Convert Table to markdown table for embedding
    query_text = df.execute().to_csv(sep="|", index=False)

    logger.debug(f"Query text length: {len(query_text)} chars")

    # Embed query (use RETRIEVAL_QUERY task type)
    query_vec = await embed_query(query_text, client, output_dim=3072)

    # Search vector store
    results = store.search(
        query_vec=query_vec,
        top_k=top_k * 3 if deduplicate else top_k,  # Get extras for dedup
        min_similarity=0.7,
    )

    if results.count().execute() == 0:
        logger.info("No similar posts found")
        return results

    result_count = results.count().execute()
    logger.info(f"Found {result_count} similar chunks")

    # Deduplicate: keep only best chunk per post
    if deduplicate:
        window = ibis.window(group_by="post_slug", order_by=ibis.desc("similarity"))
        results = (
            results.order_by(ibis.desc("similarity"))
            .mutate(_rank=ibis.row_number().over(window))
            .filter(lambda t: t._rank < 2)
            .drop("_rank")
            .order_by(ibis.desc("similarity"))
            .limit(top_k)
        )

        dedup_count = results.count().execute()
        logger.info(f"After deduplication: {dedup_count} unique posts")

    return results


def _parse_media_enrichment(enrichment_path: Path) -> dict | None:
    """
    Parse a media enrichment markdown file to extract metadata.

    Args:
        enrichment_path: Path to enrichment .md file

    Returns:
        Dict with extracted metadata or None if parsing fails
    """
    try:
        content = enrichment_path.read_text(encoding="utf-8")

        # Extract metadata from the markdown
        metadata = {}

        # Extract from metadata section
        date_match = re.search(r"- \*\*Date:\*\* (.+)", content)
        time_match = re.search(r"- \*\*Time:\*\* (.+)", content)
        sender_match = re.search(r"- \*\*Sender:\*\* (.+)", content)
        media_type_match = re.search(r"- \*\*Media Type:\*\* (.+)", content)
        file_match = re.search(r"- \*\*File:\*\* (.+)", content)

        # Extract filename from title
        filename_match = re.search(r"# Enrichment: (.+)", content)
        original_filename = filename_match.group(1).strip() if filename_match else None

        # Build metadata dict
        if date_match and time_match:
            date_str = date_match.group(1).strip()
            time_str = time_match.group(1).strip()
            try:
                metadata["message_date"] = datetime.strptime(
                    f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
                )
            except ValueError:
                logger.warning(f"Failed to parse date/time: {date_str} {time_str}")
                metadata["message_date"] = None

        metadata["author_uuid"] = sender_match.group(1).strip() if sender_match else None
        metadata["media_type"] = media_type_match.group(1).strip() if media_type_match else None
        metadata["media_path"] = file_match.group(1).strip() if file_match else None
        metadata["original_filename"] = original_filename

        return metadata

    except Exception as e:
        logger.error(f"Failed to parse media enrichment {enrichment_path}: {e}")
        return None


async def index_media_enrichment(
    enrichment_path: Path,
    output_dir: Path,
    client: genai.Client,
    store: VectorStore,
) -> int:
    """
    Chunk, embed, and index a media enrichment file.

    Args:
        enrichment_path: Path to enrichment .md file
        output_dir: Output directory (for resolving relative paths)
        client: Gemini client
        store: Vector store

    Returns:
        Number of chunks indexed
    """
    logger.info(f"Indexing media enrichment: {enrichment_path.name}")

    # Parse metadata
    metadata = _parse_media_enrichment(enrichment_path)
    if not metadata:
        logger.warning(f"Failed to parse metadata from {enrichment_path.name}")
        return 0

    # Use enrichment file UUID as media_uuid (filename without extension)
    media_uuid = enrichment_path.stem

    # Chunk document
    chunks = chunk_document(enrichment_path, max_tokens=1800)

    if not chunks:
        logger.warning(f"No chunks generated from {enrichment_path.name}")
        return 0

    # Extract content for embedding
    chunk_texts = [chunk["content"] for chunk in chunks]

    # Embed chunks (RETRIEVAL_DOCUMENT task type)
    embeddings = await embed_chunks(
        chunk_texts,
        client,
        task_type="RETRIEVAL_DOCUMENT",
        output_dim=3072,
    )

    # Build DataFrame for storage
    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
        rows.append(
            {
                "chunk_id": f"{media_uuid}_{i}",
                "document_type": "media",
                "document_id": media_uuid,
                "post_slug": None,
                "post_title": None,
                "post_date": None,
                "media_uuid": media_uuid,
                "media_type": metadata.get("media_type"),
                "media_path": metadata.get("media_path"),
                "original_filename": metadata.get("original_filename"),
                "message_date": metadata.get("message_date"),
                "author_uuid": metadata.get("author_uuid"),
                "chunk_index": i,
                "content": chunk["content"],
                "embedding": embedding,
                "tags": [],  # Could extract from content in future
                "category": None,
            }
        )

    chunks_df = ibis.memtable(rows)

    # Add to store
    store.add(chunks_df)

    logger.info(f"Indexed {len(chunks)} chunks from {enrichment_path.name}")

    return len(chunks)


async def index_all_media(
    output_dir: Path,
    client: genai.Client,
    store: VectorStore,
) -> int:
    """
    Index all media enrichment files from output/media/enrichments/.

    Args:
        output_dir: Output directory
        client: Gemini client
        store: Vector store

    Returns:
        Total number of chunks indexed
    """
    enrichments_dir = output_dir / "media" / "enrichments"

    if not enrichments_dir.exists():
        logger.warning(f"Enrichments directory does not exist: {enrichments_dir}")
        return 0

    enrichment_files = list(enrichments_dir.glob("*.md"))

    if not enrichment_files:
        logger.info("No media enrichments to index")
        return 0

    logger.info(f"Found {len(enrichment_files)} media enrichments to index")

    total_chunks = 0
    for enrichment_path in enrichment_files:
        chunks_count = await index_media_enrichment(
            enrichment_path,
            output_dir,
            client,
            store,
        )
        total_chunks += chunks_count

    logger.info(f"Indexed {total_chunks} total chunks from {len(enrichment_files)} media files")

    return total_chunks


async def query_media(  # noqa: PLR0913
    query: str,
    client: genai.Client,
    store: VectorStore,
    media_types: list[str] | None = None,
    top_k: int = 5,
    min_similarity: float = 0.7,
    deduplicate: bool = True,
) -> Table:
    """
    Search for relevant media by description or topic.

    Args:
        query: Natural language search query (e.g., "funny meme about AI")
        client: Gemini client
        store: Vector store
        media_types: Optional filter by media type (e.g., ["image", "video"])
        top_k: Number of results to return
        min_similarity: Minimum cosine similarity (0-1)
        deduplicate: Keep only 1 chunk per media file (highest similarity)

    Returns:
        Ibis Table with columns: [media_uuid, media_type, media_path, content, similarity, ...]
    """
    logger.info(f"Searching media for: {query}")

    # Embed query (use RETRIEVAL_QUERY task type)
    query_vec = await embed_query(query, client, output_dim=3072)

    # Search vector store (filter to media documents only)
    results = store.search(
        query_vec=query_vec,
        top_k=top_k * 3 if deduplicate else top_k,  # Get extras for dedup
        min_similarity=min_similarity,
        document_type="media",  # Only search media documents
        media_types=media_types,
    )

    result_count = results.count().execute()
    if result_count == 0:
        logger.info("No matching media found")
        return results

    logger.info(f"Found {result_count} matching media chunks")

    # Deduplicate: keep only best chunk per media file
    if deduplicate:
        window = ibis.window(group_by="media_uuid", order_by=ibis.desc("similarity"))
        results = (
            results.order_by(ibis.desc("similarity"))
            .mutate(_rank=ibis.row_number().over(window))
            .filter(lambda t: t._rank < 2)
            .drop("_rank")
            .order_by(ibis.desc("similarity"))
            .limit(top_k)
        )

        dedup_count = results.count().execute()
        logger.info(f"After deduplication: {dedup_count} unique media files")

    return results
