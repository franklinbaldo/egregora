"""Indexing operations for RAG knowledge system.

Handles indexing of Documents and media enrichments into the vector store.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

import ibis

# Import from other RAG modules
from egregora.agents.model_limits import PromptTooLargeError
from egregora.agents.shared.rag.chunker import chunk_document, chunk_from_document
from egregora.agents.shared.rag.embedder import embed_chunks
from egregora.data_primitives.document import Document, DocumentType
from egregora.database import ir_schema
from egregora.utils.frontmatter_utils import parse_frontmatter

if TYPE_CHECKING:
    from egregora.agents.shared.rag.store import VectorStore
    from egregora.data_primitives.protocols import OutputAdapter

# Use schema directly to avoid circular import with store.py
VECTOR_STORE_SCHEMA = ir_schema.RAG_CHUNKS_SCHEMA

logger = logging.getLogger(__name__)

# Default chunk size for indexing
DEFAULT_INDEX_MAX_TOKENS = 1800

# Regex patterns for media enrichment parsing
DATE_MATCH_PATTERN = re.compile(r"- \*\*Date:\*\* (.+)")
TIME_MATCH_PATTERN = re.compile(r"- \*\*Time:\*\* (.+)")
SENDER_MATCH_PATTERN = re.compile(r"- \*\*Sender:\*\* (.+)")
MEDIA_TYPE_MATCH_PATTERN = re.compile(r"- \*\*Media Type:\*\* (.+)")
FILE_MATCH_PATTERN = re.compile(r"- \*\*File:\*\* (.+)")
FILENAME_MATCH_PATTERN = re.compile(r"# Enrichment: (.+)")


class MediaEnrichmentMetadata(TypedDict):
    message_date: datetime | None
    author_uuid: str | None
    media_type: str | None
    media_path: str | None
    original_filename: str


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


def _build_vector_store_row(
    chunk: dict[str, Any],
    chunk_index: int,
    embedding: list[float],
    *,
    document_type: str,
    document_id: str,
    source_path: str,
    source_mtime_ns: int,
) -> dict[str, Any]:
    """Build a single vector store row from chunk data.

    Args:
        chunk: Chunk dictionary with content and metadata
        chunk_index: Index of chunk within document
        embedding: Embedding vector for the chunk
        document_type: Type of document (post, media, etc.)
        document_id: Unique document identifier
        source_path: Filesystem path to source document
        source_mtime_ns: Modification time in nanoseconds

    Returns:
        Dictionary compatible with VECTOR_STORE_SCHEMA

    """
    metadata = chunk.get("metadata", {})
    post_slug = chunk.get("post_slug")
    post_title = chunk.get("post_title")

    # Normalize authors and tags
    authors = metadata.get("authors", [])
    if isinstance(authors, str):
        authors = [authors]
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    # Build base row structure
    row = {
        "chunk_id": f"{document_id}_{chunk_index}",
        "document_type": document_type,
        "document_id": document_id,
        "source_path": source_path,
        "source_mtime_ns": source_mtime_ns,
        "chunk_index": chunk_index,
        "content": chunk["content"],
        "embedding": embedding,
        "tags": tags,
        "category": metadata.get("category"),
        "authors": authors,
    }

    # Add document-type-specific fields
    if document_type in ("media", "enrichment_media"):
        # Media documents
        row.update(
            {
                "post_slug": None,
                "post_title": None,
                "post_date": None,
                "media_uuid": metadata.get("media_uuid") or metadata.get("uuid"),
                "media_type": metadata.get("media_type"),
                "media_path": metadata.get("media_path"),
                "original_filename": metadata.get("original_filename"),
                "message_date": _coerce_message_datetime(metadata.get("message_date")),
                "author_uuid": metadata.get("author_uuid"),
            }
        )
    else:
        # Post/Profile/Journal documents
        post_date = _coerce_post_date(metadata.get("date"))
        row.update(
            {
                "post_slug": post_slug,
                "post_title": post_title,
                "post_date": post_date,
                "media_uuid": None,
                "media_type": None,
                "media_path": None,
                "original_filename": None,
                "message_date": None,
                "author_uuid": None,
            }
        )

    return row


def index_document(
    document: Document,
    store: VectorStore,
    *,
    embedding_model: str,
    source_path: str | None = None,
    source_mtime_ns: int | None = None,
) -> int:
    """Chunk, embed, and index a Document object."""
    logger.info("Indexing Document %s (type=%s)", document.document_id[:8], document.type.value)

    # Chunk the document
    chunks = chunk_from_document(document, max_tokens=DEFAULT_INDEX_MAX_TOKENS)
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

    # Build rows for vector store using helper function
    rows = [
        _build_vector_store_row(
            chunk,
            i,
            embedding,
            document_type=document.type.value,
            document_id=document.document_id,
            source_path=source_path,
            source_mtime_ns=source_mtime_ns,
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False))
    ]

    # Add to store
    chunks_table = ibis.memtable(rows, schema=VECTOR_STORE_SCHEMA)
    store.add(chunks_table)
    logger.info("Indexed %s chunks from Document %s", len(chunks), document.document_id[:8])
    return len(chunks)


def _collect_document_metadata(output_format: OutputAdapter) -> tuple[list[dict[str, Any]], int]:
    """Collect metadata from all documents in the output adapter.

    Args:
        output_format: Output adapter providing documents

    Returns:
        Tuple of (metadata rows list, total document count)

    """
    rows: list[dict[str, Any]] = []
    doc_count = 0

    for document in output_format.documents():
        doc_count += 1
        identifier = document.metadata.get("storage_identifier") or document.suggested_path
        if not identifier:
            continue

        source_path = document.metadata.get("source_path")
        # Note: source_path might be missing if the document was not loaded from a filesystem adapter
        # that populates it (e.g. MkDocsAdapter populates it). Without source_path, we can't index
        # the document as it requires a physical path for the vector store schema.
        if not source_path and hasattr(output_format, "resolve_document_path"):
            try:
                source_path = str(output_format.resolve_document_path(identifier))
            except (ValueError, RuntimeError, OSError) as e:
                logger.warning("Failed to resolve identifier %s: %s", identifier, e)
                source_path = ""

        rows.append(
            {
                "storage_identifier": identifier,
                "source_path": source_path or "",
                "mtime_ns": document.metadata.get("mtime_ns") or 0,
            }
        )

    return rows, doc_count


def _identify_documents_to_index(docs_table: ibis.Table, store: VectorStore) -> ibis.Table:
    """Perform delta detection to identify new or changed documents.

    Args:
        docs_table: Table of document metadata from output adapter
        store: Vector store with indexed sources

    Returns:
        Table of documents that need indexing (new or changed)

    """
    indexed_table = store.get_indexed_sources_table()
    logger.debug("Found %d already indexed sources in RAG", indexed_table.count().execute())

    indexed_renamed = indexed_table.select(
        indexed_path=indexed_table.source_path, indexed_mtime=indexed_table.source_mtime_ns
    )

    joined = docs_table.left_join(indexed_renamed, docs_table.source_path == indexed_renamed.indexed_path)

    needs_index = (joined.indexed_mtime.isnull()) | (joined.mtime_ns > joined.indexed_mtime)

    return joined.filter(needs_index).select(
        storage_identifier=joined.storage_identifier,
        source_path=joined.source_path,
        mtime_ns=joined.mtime_ns,
    )


def _index_new_documents(to_index, store: VectorStore, *, embedding_model: str) -> int:
    """Index a set of new or changed documents.

    Args:
        to_index: DataFrame/table of documents to index
        store: Vector store for indexing
        embedding_model: Model name for embeddings

    Returns:
        Count of successfully indexed documents

    """
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
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to index document %s: %s", row.storage_identifier, e)
            continue

    return indexed_count


def index_documents_for_rag(
    output_format: OutputAdapter,
    store: VectorStore,
    *,
    embedding_model: str,
) -> int:
    """Index new/changed documents using incremental indexing via OutputSink.

    Args:
        output_format: Output adapter providing documents
        store: Vector store instance
        embedding_model: Model name for embeddings

    Returns:
        Number of documents successfully indexed

    """
    try:
        # Step 1: Collect metadata from all documents
        rows, doc_count = _collect_document_metadata(output_format)

        if doc_count == 0:
            logger.debug("No documents found by output format")
            return 0

        logger.debug("Output sink reported %d documents", doc_count)

        # Step 2: Build table and filter out unresolved paths
        docs_table = ibis.memtable(rows)
        docs_table = docs_table.filter(docs_table["source_path"] != "")

        remaining = docs_table.count().execute()
        if hasattr(remaining, "iloc"):
            remaining_count = int(remaining.iloc[0, 0])
        else:
            remaining_count = int(remaining)

        if remaining_count == 0:
            logger.warning("All document identifiers failed to resolve to paths")
            return 0

        # Step 3: Perform delta detection
        new_or_changed = _identify_documents_to_index(docs_table, store)

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
        all_chunks_rows = []  # Accumulate all chunks here

        for row in to_index.itertuples():
            try:
                document_path = Path(row.source_path)

                doc = _load_document_from_path(document_path)
                if doc is None:
                    logger.warning("Failed to load document %s, skipping", row.storage_identifier)
                    continue

                # Chunk and embed the document, but don't persist yet
                chunks = chunk_from_document(doc)
                if not chunks:
                    logger.debug("No chunks generated from document %s", doc.document_id[:8])
                    continue

                chunk_texts = [chunk["content"] for chunk in chunks]
                embeddings = embed_chunks(chunk_texts, model=embedding_model, task_type="RETRIEVAL_DOCUMENT")

                # Build chunk rows for this document
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
                    if doc.type in (DocumentType.ENRICHMENT_MEDIA, DocumentType.MEDIA):
                        media_uuid = metadata.get("media_uuid") or metadata.get("uuid")
                        media_type = metadata.get("media_type")
                        media_path = metadata.get("media_path")
                        original_filename = metadata.get("original_filename")
                        message_date = _coerce_message_datetime(metadata.get("message_date"))
                        author_uuid = metadata.get("author_uuid")
                        post_slug_val = None
                        post_title_val = None
                        post_date_val = None
                    else:
                        media_uuid = None
                        media_type = None
                        media_path = None
                        original_filename = None
                        message_date = None
                        author_uuid = None
                        post_slug_val = chunk["post_slug"]
                        post_title_val = chunk["post_title"]
                        post_date_val = post_date

                    all_chunks_rows.append(
                        {
                            "chunk_id": f"{doc.document_id}_{i}",
                            "document_type": doc.type.value,
                            "document_id": doc.document_id,
                            "source_path": str(document_path),
                            "source_mtime_ns": row.mtime_ns,
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

                indexed_count += 1
                logger.debug("Indexed document: %s (%d chunks)", row.storage_identifier, len(chunks))
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to index document %s: %s", row.storage_identifier, e)
                continue

        # Persist all chunks at once
        if all_chunks_rows:
            chunks_table = ibis.memtable(all_chunks_rows, schema=VECTOR_STORE_SCHEMA)
            store.add(chunks_table)
            logger.info(
                "Indexed %d chunks from %d documents (batched save)",
                len(all_chunks_rows),
                indexed_count,
            )
        elif indexed_count > 0:
            logger.info("Indexed %d new/changed documents in RAG (incremental)", indexed_count)

        return indexed_count

    except PromptTooLargeError:
        raise
    except Exception:
        logger.exception("Failed to index documents in RAG")
        return 0


def index_post(post_path: Path, store: VectorStore, *, embedding_model: str) -> int:
    """Chunk, embed, and index a blog post."""
    logger.info("Indexing post: %s", post_path.name)
    chunks = chunk_document(post_path, max_tokens=DEFAULT_INDEX_MAX_TOKENS)
    if not chunks:
        logger.warning("No chunks generated from %s", post_path.name)
        return 0

    absolute_path = str(post_path.resolve())
    mtime_ns = post_path.stat().st_mtime_ns

    chunk_texts = [chunk["content"] for chunk in chunks]
    embeddings = embed_chunks(chunk_texts, model=embedding_model, task_type="RETRIEVAL_DOCUMENT")

    # Build rows using helper function
    rows = [
        _build_vector_store_row(
            chunk,
            i,
            embedding,
            document_type="post",
            document_id=chunk["post_slug"],
            source_path=absolute_path,
            source_mtime_ns=mtime_ns,
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False))
    ]

    chunks_table = ibis.memtable(rows, schema=VECTOR_STORE_SCHEMA)
    store.add(chunks_table)
    logger.info("Indexed %s chunks from %s", len(chunks), post_path.name)
    return len(chunks)


def _parse_media_enrichment(enrichment_path: Path) -> MediaEnrichmentMetadata | None:
    """Parse a media enrichment markdown file to extract metadata."""
    try:
        content = enrichment_path.read_text(encoding="utf-8")
        metadata: MediaEnrichmentMetadata = {
            "message_date": None,
            "author_uuid": None,
            "media_type": None,
            "media_path": None,
            "original_filename": enrichment_path.name,
        }
        date_match = DATE_MATCH_PATTERN.search(content)
        time_match = TIME_MATCH_PATTERN.search(content)
        sender_match = SENDER_MATCH_PATTERN.search(content)
        media_type_match = MEDIA_TYPE_MATCH_PATTERN.search(content)
        file_match = FILE_MATCH_PATTERN.search(content)
        filename_match = FILENAME_MATCH_PATTERN.search(content)
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
    """Chunk, embed, and index a media enrichment file."""
    logger.info("Indexing media enrichment: %s", enrichment_path.name)
    media_metadata = _parse_media_enrichment(enrichment_path)
    if not media_metadata:
        logger.warning("Failed to parse metadata from %s", enrichment_path.name)
        return 0

    absolute_path = str(enrichment_path.resolve())
    mtime_ns = enrichment_path.stat().st_mtime_ns

    media_uuid = enrichment_path.stem
    chunks = chunk_document(enrichment_path, max_tokens=DEFAULT_INDEX_MAX_TOKENS)
    if not chunks:
        logger.warning("No chunks generated from %s", enrichment_path.name)
        return 0

    # Merge media metadata into chunk metadata
    for chunk in chunks:
        chunk["metadata"].update(
            {
                "media_uuid": media_uuid,
                "media_type": media_metadata.get("media_type"),
                "media_path": media_metadata.get("media_path"),
                "original_filename": media_metadata.get("original_filename"),
                "message_date": media_metadata.get("message_date"),
                "author_uuid": media_metadata.get("author_uuid"),
            }
        )

    chunk_texts = [chunk["content"] for chunk in chunks]
    embeddings = embed_chunks(chunk_texts, model=embedding_model, task_type="RETRIEVAL_DOCUMENT")

    # Build rows using helper function
    rows = [
        _build_vector_store_row(
            chunk,
            i,
            embedding,
            document_type="media",
            document_id=media_uuid,
            source_path=absolute_path,
            source_mtime_ns=mtime_ns,
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False))
    ]

    chunks_table = ibis.memtable(rows, schema=VECTOR_STORE_SCHEMA)
    store.add(chunks_table)
    logger.info("Indexed %s chunks from %s", len(chunks), enrichment_path.name)
    return len(chunks)


def index_all_media(docs_dir: Path, store: VectorStore, *, embedding_model: str) -> int:  # noqa: C901, PLR0912, PLR0915
    """Index new/changed media enrichments using incremental indexing."""
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
    all_media_rows = []  # Accumulate all media chunks here

    for enrichment_path, change_type in files_to_index:
        try:
            # Parse metadata
            metadata = _parse_media_enrichment(enrichment_path)
            if not metadata:
                logger.warning("Failed to parse metadata from %s", enrichment_path.name)
                continue

            absolute_path = str(enrichment_path.resolve())
            mtime_ns = enrichment_path.stat().st_mtime_ns
            media_uuid = enrichment_path.stem

            # Chunk and embed
            chunks = chunk_document(enrichment_path, max_tokens=1800)
            if not chunks:
                logger.warning("No chunks generated from %s", enrichment_path.name)
                continue

            chunk_texts = [chunk["content"] for chunk in chunks]
            embeddings = embed_chunks(chunk_texts, model=embedding_model, task_type="RETRIEVAL_DOCUMENT")

            # Build rows for this media enrichment
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
                message_date = _coerce_message_datetime(metadata.get("message_date"))
                all_media_rows.append(
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

            total_chunks += len(chunks)
            logger.debug(
                "Indexed %s media enrichment: %s (%d chunks)", change_type, enrichment_path.name, len(chunks)
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to index media enrichment %s: %s", enrichment_path.name, e)
            continue

    # Persist all media chunks at once
    if all_media_rows:
        chunks_table = ibis.memtable(all_media_rows, schema=VECTOR_STORE_SCHEMA)
        store.add(chunks_table)
        logger.info("Indexed %s chunks from %s media files (batched save)", total_chunks, len(files_to_index))

    return total_chunks


__all__ = [
    "MediaEnrichmentMetadata",
    "index_all_media",
    "index_document",
    "index_documents_for_rag",
    "index_media_enrichment",
    "index_post",
]
