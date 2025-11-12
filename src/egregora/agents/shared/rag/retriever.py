"""High-level retrieval and indexing functions."""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, TypedDict

import ibis
from ibis.expr.types import Table

from egregora.agents.shared.rag.chunker import chunk_document, chunk_from_document
from egregora.agents.shared.rag.embedder import embed_chunks, embed_query_text
from egregora.agents.shared.rag.store import VECTOR_STORE_SCHEMA, VectorStore
from egregora.core.document import DocumentType

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table

    from egregora.core.document import Document

logger = logging.getLogger(__name__)


class MediaEnrichmentMetadata(TypedDict):
    message_date: datetime | None
    author_uuid: str | None
    media_type: str | None
    media_path: str | None
    original_filename: str


DEDUP_MAX_RANK = 2


def index_post(post_path: Path, store: VectorStore, *, embedding_model: str) -> int:
    """Chunk, embed, and index a blog post.

    All embeddings use fixed 768-dimension output.

    Stores source file path and mtime for incremental indexing support.
    This enables change detection and prevents re-indexing unchanged files.

    Args:
        post_path: Path to markdown file with YAML frontmatter
        store: Vector store
        embedding_model: Embedding model name

    Returns:
        Number of chunks indexed

    """
    logger.info("Indexing post: %s", post_path.name)
    chunks = chunk_document(post_path, max_tokens=1800)
    if not chunks:
        logger.warning("No chunks generated from %s", post_path.name)
        return 0

    # Get file metadata for change detection (industry standard: content-addressed storage)
    absolute_path = str(post_path.resolve())
    mtime_ns = post_path.stat().st_mtime_ns

    chunk_texts = [chunk["content"] for chunk in chunks]
    embeddings = embed_chunks(chunk_texts, model=embedding_model, task_type="RETRIEVAL_DOCUMENT")
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
                "source_path": absolute_path,
                "source_mtime_ns": mtime_ns,
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
    store.add(chunks_table)
    logger.info("Indexed %s chunks from %s", len(chunks), post_path.name)
    return len(chunks)


def index_document(
    document: Document,
    store: VectorStore,
    *,
    embedding_model: str,
    source_path: str | None = None,
    source_mtime_ns: int | None = None,
) -> int:
    """Chunk, embed, and index a Document object.

    MODERN (Phase 4): Works with Document abstraction instead of filesystem paths.
    Uses content-addressed document_id for deduplication.

    Args:
        document: Content-addressed Document object
        store: Vector store
        embedding_model: Embedding model name
        source_path: Optional source path for tracking (backward compatibility)
        source_mtime_ns: Optional mtime for tracking (backward compatibility)

    Returns:
        Number of chunks indexed

    """
    logger.info("Indexing Document %s (type=%s)", document.document_id[:8], document.type.value)

    # Chunk the document
    chunks = chunk_from_document(document, max_tokens=1800)
    if not chunks:
        logger.warning("No chunks generated from Document %s", document.document_id[:8])
        return 0

    # Use document_id as source_path fallback (content-addressed)
    if source_path is None:
        source_path = f"document:{document.document_id}"
    if source_mtime_ns is None:
        # Use document creation time as mtime (content changes → new ID → new timestamp)
        source_mtime_ns = int(document.created_at.timestamp() * 1_000_000_000)

    # Embed chunks
    chunk_texts = [chunk["content"] for chunk in chunks]
    embeddings = embed_chunks(chunk_texts, model=embedding_model, task_type="RETRIEVAL_DOCUMENT")

    # Build rows for vector store
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

        # Handle media-specific fields for enrichments
        if document.type in (DocumentType.ENRICHMENT_MEDIA, DocumentType.MEDIA):
            media_uuid = metadata.get("media_uuid") or metadata.get("uuid")
            media_type = metadata.get("media_type")
            media_path = metadata.get("media_path")
            original_filename = metadata.get("original_filename")
            message_date = _coerce_message_datetime(metadata.get("message_date"))
            author_uuid = metadata.get("author_uuid")
            # Media documents don't have post fields
            post_slug_val = None
            post_title_val = None
            post_date_val = None
        else:
            # Post/Profile/Journal documents
            media_uuid = None
            media_type = None
            media_path = None
            original_filename = None
            message_date = None
            author_uuid = None
            post_slug_val = chunk["post_slug"]
            post_title_val = chunk["post_title"]
            post_date_val = post_date

        rows.append(
            {
                "chunk_id": f"{document.document_id}_{i}",
                "document_type": document.type.value,  # Use DocumentType enum
                "document_id": document.document_id,  # Content-addressed ID
                "source_path": source_path,
                "source_mtime_ns": source_mtime_ns,
                "post_slug": post_slug_val,
                "post_title": post_title_val,
                "post_date": post_date_val,
                "media_uuid": media_uuid,
                "media_type": media_type,
                "media_path": media_path,
                "original_filename": original_filename,
                "message_date": message_date,
                "author_uuid": author_uuid,
                "chunk_index": i,
                "content": chunk["content"],
                "embedding": embedding,
                "tags": tags,
                "category": metadata.get("category"),
                "authors": authors,
            }
        )

    # Add to store
    chunks_table = ibis.memtable(rows, schema=VECTOR_STORE_SCHEMA)
    store.add(chunks_table)
    logger.info("Indexed %s chunks from Document %s", len(chunks), document.document_id[:8])
    return len(chunks)


def query_similar_posts(
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
    """Find similar previous blog posts for a period's table.

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


def _parse_media_enrichment(enrichment_path: Path) -> MediaEnrichmentMetadata | None:
    """Parse a media enrichment markdown file to extract metadata.

    Args:
        enrichment_path: Path to enrichment .md file

    Returns:
        Dict with extracted metadata or None if parsing fails

    """
    try:
        content = enrichment_path.read_text(encoding="utf-8")
        metadata: MediaEnrichmentMetadata = {
            "message_date": None,
            "author_uuid": None,
            "media_type": None,
            "media_path": None,
            "original_filename": enrichment_path.name,
        }
        date_match = re.search("- \\*\\*Date:\\*\\* (.+)", content)
        time_match = re.search("- \\*\\*Time:\\*\\* (.+)", content)
        sender_match = re.search("- \\*\\*Sender:\\*\\* (.+)", content)
        media_type_match = re.search("- \\*\\*Media Type:\\*\\* (.+)", content)
        file_match = re.search("- \\*\\*File:\\*\\* (.+)", content)
        filename_match = re.search("# Enrichment: (.+)", content)
        original_filename_from_content = filename_match.group(1).strip() if filename_match else None
        if original_filename_from_content:
            metadata["original_filename"] = original_filename_from_content
        if date_match and time_match:
            date_str = date_match.group(1).strip()
            time_str = time_match.group(1).strip()
            try:
                metadata["message_date"] = datetime.strptime(
                    f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=UTC)
            except ValueError:
                logger.warning("Failed to parse date/time: %s %s", date_str, time_str)
                metadata["message_date"] = None
        metadata["author_uuid"] = sender_match.group(1).strip() if sender_match else None
        metadata["media_type"] = media_type_match.group(1).strip() if media_type_match else None
        metadata["media_path"] = file_match.group(1).strip() if file_match else None
        metadata["original_filename"] = original_filename_from_content or enrichment_path.name
    except Exception:
        logger.exception("Failed to parse media enrichment %s", enrichment_path)
        return None
    else:
        return metadata


def index_media_enrichment(
    enrichment_path: Path, _docs_dir: Path, store: VectorStore, *, embedding_model: str
) -> int:
    """Chunk, embed, and index a media enrichment file.

    Args:
        enrichment_path: Path to enrichment .md file
        docs_dir: Docs directory (for resolving relative paths)
        store: Vector store
        embedding_model: Embedding model name

    Returns:
        Number of chunks indexed

    """
    logger.info("Indexing media enrichment: %s", enrichment_path.name)
    metadata = _parse_media_enrichment(enrichment_path)
    if not metadata:
        logger.warning("Failed to parse metadata from %s", enrichment_path.name)
        return 0

    # Get file metadata for change detection (industry standard: content-addressed storage)
    absolute_path = str(enrichment_path.resolve())
    mtime_ns = enrichment_path.stat().st_mtime_ns

    media_uuid = enrichment_path.stem
    chunks = chunk_document(enrichment_path, max_tokens=1800)
    if not chunks:
        logger.warning("No chunks generated from %s", enrichment_path.name)
        return 0
    chunk_texts = [chunk["content"] for chunk in chunks]
    embeddings = embed_chunks(chunk_texts, model=embedding_model, task_type="RETRIEVAL_DOCUMENT")
    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
        message_date = _coerce_message_datetime(metadata.get("message_date"))
        rows.append(
            {
                "chunk_id": f"{media_uuid}_{i}",
                "document_type": "media",
                "document_id": media_uuid,
                "source_path": absolute_path,
                "source_mtime_ns": mtime_ns,
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
                "tags": [],
                "category": None,
                "authors": [],
            }
        )
    chunks_table = ibis.memtable(rows, schema=VECTOR_STORE_SCHEMA)
    store.add(chunks_table)
    logger.info("Indexed %s chunks from %s", len(chunks), enrichment_path.name)
    return len(chunks)


def index_all_media(docs_dir: Path, store: VectorStore, *, embedding_model: str) -> int:
    """Index new/changed media enrichments using incremental indexing (delta detection).

    Uses industry-standard incremental build pattern: compares filesystem state
    with RAG metadata to identify only new or modified files, avoiding re-indexing.

    Similar to: Make (mtime-based builds), rsync (delta sync), Git (content addressing),
    Docker layers (incremental caching), Webpack (changed file detection).

    Enrichment files are co-located with media (e.g., video.mp4.md).
    Scans all subdirectories under docs/media/ for .md files.

    Args:
        docs_dir: Docs directory
        store: Vector store
        embedding_model: Embedding model name

    Returns:
        Total number of NEW chunks indexed (not total chunks)

    Algorithm:
        1. Query RAG for all indexed sources (path -> mtime mapping)
        2. Scan filesystem for all enrichment .md files
        3. Compare: find files that are missing from RAG or have newer mtime
        4. Index only those changed files (incremental, not full reindex)

    """
    # Compute media_dir using MkDocs convention
    media_dir = docs_dir / "media"
    if not media_dir.exists():
        logger.warning("Media directory does not exist: %s", media_dir)
        return 0

    # Phase 1: Get already indexed sources (path -> mtime mapping)
    indexed_sources = store.get_indexed_sources()
    logger.debug("Found %d already indexed sources in RAG", len(indexed_sources))

    # Phase 2: Scan filesystem for all enrichment files
    enrichment_files = list(media_dir.rglob("*.md"))
    enrichment_files = [f for f in enrichment_files if f.name != "index.md"]

    if not enrichment_files:
        logger.info("No media enrichments to index")
        return 0

    # Phase 3: Delta detection - find new or changed files
    filesystem_enrichments = {}
    for enrichment_path in enrichment_files:
        absolute_path = str(enrichment_path.resolve())
        try:
            mtime_ns = enrichment_path.stat().st_mtime_ns
            filesystem_enrichments[absolute_path] = (enrichment_path, mtime_ns)
        except OSError as e:
            logger.warning("Failed to stat file %s: %s", enrichment_path.name, e)
            continue

    files_to_index = []
    for absolute_path, (enrichment_path, mtime_ns) in filesystem_enrichments.items():
        indexed_mtime = indexed_sources.get(absolute_path)

        if indexed_mtime is None:
            # File not in RAG - needs indexing
            files_to_index.append((enrichment_path, "new"))
        elif mtime_ns > indexed_mtime:
            # File modified since last index - needs re-indexing
            files_to_index.append((enrichment_path, "changed"))
        # else: file unchanged, skip

    if not files_to_index:
        logger.debug("All media enrichments already indexed with current mtime - no work needed")
        return 0

    logger.info(
        "Incremental indexing: %d new/changed media enrichments (skipped %d unchanged)",
        len(files_to_index),
        len(filesystem_enrichments) - len(files_to_index),
    )

    # Phase 4: Index only new/changed files
    total_chunks = 0
    for enrichment_path, change_type in files_to_index:
        chunks_count = index_media_enrichment(
            enrichment_path, docs_dir, store, embedding_model=embedding_model
        )
        total_chunks += chunks_count
        logger.debug(
            "Indexed %s media enrichment: %s (%d chunks)", change_type, enrichment_path.name, chunks_count
        )

    logger.info("Indexed %s total chunks from %s new/changed media files", total_chunks, len(files_to_index))
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
        result = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
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
                result = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    else:
        logger.warning("Unsupported message datetime type: %s", type(value))
    return result


def query_media(
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
    """Search for relevant media by description or topic.

    Args:
        query: Natural language search query (e.g., "funny meme about AI")
        store: Vector store
        media_types: Optional filter by media type (e.g., ["image", "video"])
        top_k: Number of results to return
        min_similarity_threshold: Minimum cosine similarity (0-1)
        deduplicate: Keep only 1 chunk per media file (highest similarity)
        embedding_model: Embedding model name
        retrieval_mode: "ann" (default) or "exact" for brute-force search
        retrieval_nprobe: Override ANN ``nprobe`` when ``retrieval_mode='ann'``
        retrieval_overfetch: Candidate multiplier for ANN mode before filtering

    Returns:
        Ibis Table with columns: [media_uuid, media_type, media_path, content, similarity, ...]

    """
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
