"""High-level retrieval and indexing functions."""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypedDict

import ibis
from ibis.expr.types import Table

from egregora.agents.tools.rag.chunker import chunk_document
from egregora.agents.tools.rag.embedder import embed_chunks, embed_query
from egregora.agents.tools.rag.store import VECTOR_STORE_SCHEMA, VectorStore
from egregora.config.site import MEDIA_DIR_NAME

logger = logging.getLogger(__name__)


class MediaEnrichmentMetadata(TypedDict):
    message_date: datetime | None
    author_uuid: str | None
    media_type: str | None
    media_path: str | None
    original_filename: str


DEDUP_MAX_RANK = 2


def index_post(
    post_path: Path,
    store: VectorStore,
    *,
    embedding_model: str,
    output_dimensionality: int = 3072,
) -> int:
    """
    Chunk, embed, and index a blog post.

    Args:
        post_path: Path to markdown file with YAML frontmatter
        store: Vector store
        embedding_model: Embedding model name
        output_dimensionality: Output dimensionality for embeddings

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
    embeddings = embed_chunks(
        chunk_texts,
        model=embedding_model,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=output_dimensionality,
    )

    # Build table for storage
    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
        metadata = chunk["metadata"]
        post_date = _coerce_post_date(metadata.get("date"))
        authors = metadata.get("authors", [])
        if isinstance(authors, str):
            authors = [authors]

        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        rows.append(
            {
                "chunk_id": f"{chunk['post_slug']}_{i}",
                "document_type": "post",
                "document_id": chunk["post_slug"],
                "post_slug": chunk["post_slug"],
                "post_title": chunk["post_title"],
                "post_date": post_date,
                "media_uuid": None,
                "media_type": None,
                "media_path": None,
                "original_filename": None,
                "message_date": None,
                "author_uuid": None,
                "chunk_index": i,
                "content": chunk["content"],
                "embedding": embedding,
                "tags": tags,
                "category": metadata.get("category"),
                "authors": authors,
            }
        )

    chunks_table = ibis.memtable(rows, schema=VECTOR_STORE_SCHEMA)

    # Add to store
    store.add(chunks_table)

    logger.info(f"Indexed {len(chunks)} chunks from {post_path.name}")

    return len(chunks)


def query_similar_posts(
    table: Table,
    store: VectorStore,
    *,
    embedding_model: str,
    top_k: int = 5,
    deduplicate: bool = True,
    output_dimensionality: int = 3072,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> Table:
    """
    Find similar previous blog posts for a period's table.

    Strategy:
    1. Convert table to text (markdown table)
    2. Embed using RETRIEVAL_QUERY task type
    3. Search vector store with cosine similarity
    4. Optionally deduplicate (keep best chunk per post)

    Args:
        table: Period's table (messages)
        store: Vector store
        embedding_model: Embedding model name
        top_k: Number of results to return
        deduplicate: Keep only 1 chunk per post (highest similarity)
        retrieval_mode: "ann" (default) or "exact" for brute-force search
        retrieval_nprobe: Override ANN ``nprobe`` when ``retrieval_mode='ann'``
        retrieval_overfetch: Candidate multiplier for ANN mode before filtering

    Returns:
        Table with columns: [post_title, content, similarity, post_date, tags, ...]
    """
    msg_count = table.count().execute()
    logger.info(f"Querying similar posts for period with {msg_count} messages")

    # Convert Table to markdown table for embedding
    query_text = table.execute().to_csv(sep="|", index=False)

    logger.debug(f"Query text length: {len(query_text)} chars")

    # Embed query (use RETRIEVAL_QUERY task type)
    query_vec = embed_query(
        query_text,
        model=embedding_model,
        output_dimensionality=output_dimensionality,
    )

    # Search vector store
    results = store.search(
        query_vec=query_vec,
        top_k=top_k * 3 if deduplicate else top_k,  # Get extras for dedup
        min_similarity=0.7,
        mode=retrieval_mode,
        nprobe=retrieval_nprobe,
        overfetch=retrieval_overfetch,
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
            .filter(lambda t: t._rank < DEDUP_MAX_RANK)
            .drop("_rank")
            .order_by(ibis.desc("similarity"))
            .limit(top_k)
        )

        dedup_count = results.count().execute()
        logger.info(f"After deduplication: {dedup_count} unique posts")

    return results


def _parse_media_enrichment(enrichment_path: Path) -> MediaEnrichmentMetadata | None:
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
        metadata: MediaEnrichmentMetadata = {
            "message_date": None,
            "author_uuid": None,
            "media_type": None,
            "media_path": None,
            "original_filename": enrichment_path.name,
        }

        # Extract from metadata section
        date_match = re.search(r"- \*\*Date:\*\* (.+)", content)
        time_match = re.search(r"- \*\*Time:\*\* (.+)", content)
        sender_match = re.search(r"- \*\*Sender:\*\* (.+)", content)
        media_type_match = re.search(r"- \*\*Media Type:\*\* (.+)", content)
        file_match = re.search(r"- \*\*File:\*\* (.+)", content)

        # Extract filename from title
        filename_match = re.search(r"# Enrichment: (.+)", content)
        original_filename_from_content = filename_match.group(1).strip() if filename_match else None

        if original_filename_from_content:
            metadata["original_filename"] = original_filename_from_content

        # Build metadata dict
        if date_match and time_match:
            date_str = date_match.group(1).strip()
            time_str = time_match.group(1).strip()
            try:
                parsed = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                metadata["message_date"] = parsed.replace(tzinfo=UTC)
            except ValueError:
                logger.warning(f"Failed to parse date/time: {date_str} {time_str}")
                metadata["message_date"] = None

        metadata["author_uuid"] = sender_match.group(1).strip() if sender_match else None
        metadata["media_type"] = media_type_match.group(1).strip() if media_type_match else None
        metadata["media_path"] = file_match.group(1).strip() if file_match else None

        metadata["original_filename"] = original_filename_from_content or enrichment_path.name

        return metadata

    except Exception as e:
        logger.error(f"Failed to parse media enrichment {enrichment_path}: {e}")
        return None


def index_media_enrichment(
    enrichment_path: Path,
    docs_dir: Path,
    store: VectorStore,
    *,
    embedding_model: str,
    output_dimensionality: int = 3072,
) -> int:
    """
    Chunk, embed, and index a media enrichment file.

    Args:
        enrichment_path: Path to enrichment .md file
        docs_dir: Docs directory (for resolving relative paths)
        store: Vector store
        embedding_model: Embedding model name
        output_dimensionality: Output dimensionality for embeddings

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
    embeddings = embed_chunks(
        chunk_texts,
        model=embedding_model,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=output_dimensionality,
    )

    # Build table for storage
    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
        message_date = _coerce_message_datetime(metadata.get("message_date"))

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
                "message_date": message_date,
                "author_uuid": metadata.get("author_uuid"),
                "chunk_index": i,
                "content": chunk["content"],
                "embedding": embedding,
                "tags": [],  # Could extract from content in future
                "category": None,
                "authors": [],
            }
        )

    chunks_table = ibis.memtable(rows, schema=VECTOR_STORE_SCHEMA)

    # Add to store
    store.add(chunks_table)

    logger.info(f"Indexed {len(chunks)} chunks from {enrichment_path.name}")

    return len(chunks)


def index_all_media(
    docs_dir: Path,
    store: VectorStore,
    *,
    embedding_model: str,
    output_dimensionality: int = 3072,
) -> int:
    """
    Index all media enrichment files from media directories.

    Enrichment files are co-located with media (e.g., video.mp4.md).
    Scans all subdirectories under docs/media/ for .md files.

    Args:
        docs_dir: Docs directory
        store: Vector store
        embedding_model: Embedding model name
        output_dimensionality: Output dimensionality for embeddings

    Returns:
        Total number of chunks indexed
    """
    media_dir = docs_dir / MEDIA_DIR_NAME

    if not media_dir.exists():
        logger.warning(f"Media directory does not exist: {media_dir}")
        return 0

    # Find all .md files in media directory and subdirectories
    # These are enrichment files co-located with media (e.g., video.mp4.md)
    enrichment_files = list(media_dir.rglob("*.md"))

    # Filter out index.md files (navigation pages, not enrichments)
    enrichment_files = [f for f in enrichment_files if f.name != "index.md"]

    if not enrichment_files:
        logger.info("No media enrichments to index")
        return 0

    logger.info(f"Found {len(enrichment_files)} media enrichments to index")

    total_chunks = 0
    for enrichment_path in enrichment_files:
        chunks_count = index_media_enrichment(
            enrichment_path,
            docs_dir,
            store,
            embedding_model=embedding_model,
            output_dimensionality=output_dimensionality,
        )
        total_chunks += chunks_count

    logger.info(f"Indexed {total_chunks} total chunks from {len(enrichment_files)} media files")

    return total_chunks


def _coerce_post_date(value: object) -> date | None:
    """Normalize post metadata values to ``date`` objects."""

    if value is None:
        return None

    result: date | None = None
    if isinstance(value, datetime):
        result = value.date()
    elif isinstance(value, date):
        result = value
    elif isinstance(value, str):
        text = value.strip()
        text = text.removesuffix("Z")

        if text:
            try:
                result = datetime.fromisoformat(text).date()
            except ValueError:
                try:
                    result = date.fromisoformat(text)
                except ValueError:
                    logger.warning("Unable to parse post date: %s", value)
        else:
            result = None
    else:
        logger.warning("Unsupported post date type: %s", type(value))

    return result


def _coerce_message_datetime(value: object) -> datetime | None:
    """Ensure message timestamps are timezone-aware UTC datetimes."""

    if value is None:
        return None

    result: datetime | None = None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            result = value.replace(tzinfo=UTC)
        else:
            result = value.astimezone(UTC)
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        if text:
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                logger.warning("Unable to parse message datetime: %s", value)
            else:
                if parsed.tzinfo is None:
                    result = parsed.replace(tzinfo=UTC)
                else:
                    result = parsed.astimezone(UTC)
    else:
        logger.warning("Unsupported message datetime type: %s", type(value))

    return result


def query_media(
    query: str,
    store: VectorStore,
    media_types: list[str] | None = None,
    top_k: int = 5,
    min_similarity: float = 0.7,
    deduplicate: bool = True,
    *,
    embedding_model: str,
    output_dimensionality: int = 3072,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> Table:
    """
    Search for relevant media by description or topic.

    Args:
        query: Natural language search query (e.g., "funny meme about AI")
        store: Vector store
        media_types: Optional filter by media type (e.g., ["image", "video"])
        top_k: Number of results to return
        min_similarity: Minimum cosine similarity (0-1)
        deduplicate: Keep only 1 chunk per media file (highest similarity)
        embedding_model: Embedding model name
        output_dimensionality: Output dimensionality for embeddings
        retrieval_mode: "ann" (default) or "exact" for brute-force search
        retrieval_nprobe: Override ANN ``nprobe`` when ``retrieval_mode='ann'``
        retrieval_overfetch: Candidate multiplier for ANN mode before filtering

    Returns:
        Ibis Table with columns: [media_uuid, media_type, media_path, content, similarity, ...]
    """
    logger.info(f"Searching media for: {query}")

    # Embed query (use RETRIEVAL_QUERY task type)
    query_vec = embed_query(
        query,
        model=embedding_model,
        output_dimensionality=output_dimensionality,
    )

    # Search vector store (filter to media documents only)
    results = store.search(
        query_vec=query_vec,
        top_k=top_k * 3 if deduplicate else top_k,  # Get extras for dedup
        min_similarity=min_similarity,
        document_type="media",  # Only search media documents
        media_types=media_types,
        mode=retrieval_mode,
        nprobe=retrieval_nprobe,
        overfetch=retrieval_overfetch,
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
            .filter(lambda t: t._rank < DEDUP_MAX_RANK)
            .drop("_rank")
            .order_by(ibis.desc("similarity"))
            .limit(top_k)
        )

        dedup_count = results.count().execute()
        logger.info(f"After deduplication: {dedup_count} unique media files")

    return results
