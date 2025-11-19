"""This module contains the logic for indexing documents into the RAG vector store."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import ibis

from egregora.agents.model_limits import PromptTooLargeError
from egregora.agents.shared.rag.store import VectorStore
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.utils.frontmatter_utils import parse_frontmatter


def _load_document_from_path(path: Path) -> Document | None:
    """Load a Document from a filesystem path."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("Failed to read document at %s: %s", path, e)
        return None

    metadata, body = parse_frontmatter(content)

    path_str = str(path)
    if "/posts/" in path_str and "/journal/" not in path_str:
        doc_type = DocumentType.POST
    elif "/journal/" in path_str:
        doc_type = DocumentType.JOURNAL
    elif "/profiles/" in path_str:
        doc_type = DocumentType.PROFILE
    elif "/urls/" in path_str:
        doc_type = DocumentType.ENRICHMENT_URL
    elif path_str.endswith(".md") and "/media/" in path_str:
        doc_type = DocumentType.ENRICHMENT_MEDIA
    else:
        doc_type = DocumentType.MEDIA

    return Document(
        content=body,
        type=doc_type,
        metadata=metadata,
    )


from egregora.data_primitives.document import Document

if TYPE_CHECKING:
    from egregora.output_adapters.base import OutputAdapter

logger = logging.getLogger(__name__)


from egregora.agents.shared.rag.chunker import chunk_from_document
from egregora.agents.shared.rag.embedder import embed_chunks
from egregora.agents.shared.rag.retriever import _coerce_message_datetime, _coerce_post_date
from egregora.agents.shared.rag.store import VECTOR_STORE_SCHEMA
from egregora.data_primitives.document import DocumentType


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


def index_documents_for_rag(
    output_format: OutputAdapter,
    rag_dir: Path,
    storage: DuckDBStorageManager,
    *,
    embedding_model: str,
) -> int:
    """Index new/changed documents using incremental indexing via OutputAdapter.

    Uses OutputAdapter.list_documents() to get storage identifiers and mtimes,
    then compares with RAG metadata using Ibis joins to identify new/changed files.
    No filesystem assumptions - works with any storage backend.

    This should be called once at pipeline initialization before window processing.

    Args:
        output_format: OutputAdapter instance (initialized with site_root)
        rag_dir: Directory containing RAG vector store
        storage: The central DuckDB storage manager.
        embedding_model: Model to use for embeddings

    Returns:
        Number of NEW documents indexed (not total indexed documents)

    """
    try:
        format_documents = output_format.list_documents()

        doc_count = format_documents.count().execute()
        if doc_count == 0:
            logger.debug("No documents found by output format")
            return 0

        logger.debug("OutputAdapter reported %d documents", doc_count)

        def resolve_identifier(identifier: str) -> str:
            try:
                return str(output_format.resolve_document_path(identifier))
            except (ValueError, RuntimeError, OSError) as e:
                logger.warning("Failed to resolve identifier %s: %s", identifier, e)
                return ""

        docs_df = format_documents.execute()
        docs_df["source_path"] = docs_df["storage_identifier"].apply(resolve_identifier)

        docs_df = docs_df[docs_df["source_path"] != ""]

        if docs_df.empty:
            logger.warning("All document identifiers failed to resolve to paths")
            return 0

        docs_table = ibis.memtable(docs_df)

        store = VectorStore(rag_dir / "chunks.parquet", storage=storage)
        indexed_table = store.get_indexed_sources_table()

        indexed_count_val = indexed_table.count().execute()
        logger.debug("Found %d already indexed sources in RAG", indexed_count_val)

        indexed_renamed = indexed_table.select(
            indexed_path=indexed_table.source_path, indexed_mtime=indexed_table.source_mtime_ns
        )

        joined = docs_table.left_join(indexed_renamed, docs_table.source_path == indexed_renamed.indexed_path)

        new_or_changed = joined.filter(
            (joined.indexed_mtime.isnull()) | (joined.mtime_ns > joined.indexed_mtime)
        ).select(
            storage_identifier=joined.storage_identifier,
            source_path=joined.source_path,
            mtime_ns=joined.mtime_ns,
        )

        to_index = new_or_changed.execute()

        if to_index.empty:
            logger.debug("All documents already indexed with current mtime - no work needed")
            return 0

        logger.info(
            "Incremental indexing: %d new/changed documents (skipped %d unchanged)",
            len(to_index),
            doc_count - len(to_index),
        )

        indexed_count = 0
        for row in to_index.itertuples():
            try:
                document_path = Path(row.source_path)

                doc = _load_document_from_path(document_path)
                if doc is None:
                    logger.warning("Failed to load document %s, skipping", row.storage_identifier)
                    continue

                index_document(
                    doc,
                    store,
                    embedding_model=embedding_model,
                    source_path=str(document_path),
                    source_mtime_ns=row.mtime_ns,
                )
                indexed_count += 1
                logger.debug("Indexed document: %s", row.storage_identifier)
            except Exception as e:
                logger.warning("Failed to index document %s: %s", row.storage_identifier, e)
                continue

        if indexed_count > 0:
            logger.info("Indexed %d new/changed documents in RAG (incremental)", indexed_count)

        return indexed_count

    except PromptTooLargeError:
        raise
    except Exception:
        logger.exception("Failed to index documents in RAG")
        return 0
