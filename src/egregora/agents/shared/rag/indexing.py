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
from egregora.agents.shared.rag.store import VECTOR_STORE_SCHEMA, VectorStore
from egregora.data_primitives.document import Document, DocumentType
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.utils.frontmatter_utils import parse_frontmatter

if TYPE_CHECKING:
    from egregora.data_primitives.protocols import OutputAdapter

logger = logging.getLogger(__name__)


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


def _create_index_row(
    chunk: dict[str, Any],
    embedding: list[float],
    doc_type: DocumentType,
    document_id: str,
    chunk_index: int,
    source_path: str,
    source_mtime_ns: int,
) -> dict[str, Any]:
    """Create a standardized row dictionary for the vector store."""
    metadata = chunk["metadata"]
    post_date = _coerce_post_date(metadata.get("date"))
    authors = metadata.get("authors", [])
    if isinstance(authors, str):
        authors = [authors]
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    row = {
        "chunk_id": f"{document_id}_{chunk_index}",
        "document_type": doc_type.value,
        "document_id": document_id,
        "source_path": source_path,
        "source_mtime_ns": source_mtime_ns,
        "chunk_index": chunk_index,
        "content": chunk["content"],
        "embedding": embedding,
        "tags": tags,
        "category": metadata.get("category"),
        "authors": authors,
        # Defaults for nullable columns
        "post_slug": None,
        "post_title": None,
        "post_date": None,
        "media_uuid": None,
        "media_type": None,
        "media_path": None,
        "original_filename": None,
        "message_date": None,
        "author_uuid": None,
    }

    # Populate specific fields based on type
    if doc_type in (DocumentType.ENRICHMENT_MEDIA, DocumentType.MEDIA):
        row["media_uuid"] = metadata.get("media_uuid") or metadata.get("uuid") or document_id
        row["media_type"] = metadata.get("media_type")
        row["media_path"] = metadata.get("media_path")
        row["original_filename"] = metadata.get("original_filename")
        row["message_date"] = _coerce_message_datetime(metadata.get("message_date"))
        row["author_uuid"] = metadata.get("author_uuid")
    else:
        # Post/Profile/Journal documents
        row["post_slug"] = chunk["post_slug"]
        row["post_title"] = chunk["post_title"]
        row["post_date"] = post_date

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

    chunks = chunk_from_document(document, max_tokens=1800)
    if not chunks:
        logger.warning("No chunks generated from Document %s", document.document_id[:8])
        return 0

    if source_path is None:
        source_path = f"document:{document.document_id}"
    if source_mtime_ns is None:
        source_mtime_ns = int(document.created_at.timestamp() * 1_000_000_000)

    chunk_texts = [chunk["content"] for chunk in chunks]
    embeddings = embed_chunks(chunk_texts, model=embedding_model, task_type="RETRIEVAL_DOCUMENT")

    rows = [
        _create_index_row(
            chunk, embedding, document.type, document.document_id, i, source_path, source_mtime_ns
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False))
    ]

    chunks_table = ibis.memtable(rows, schema=VECTOR_STORE_SCHEMA)
    store.add(chunks_table)
    logger.info("Indexed %s chunks from Document %s", len(chunks), document.document_id[:8])
    return len(chunks)


def _identify_indexing_candidates(output_format: OutputAdapter) -> tuple[list[dict[str, Any]], int]:
    """Identify all potential documents to index from the output adapter."""
    rows: list[dict[str, Any]] = []
    doc_count = 0

    for document in output_format.documents():
        doc_count += 1
        identifier = document.metadata.get("storage_identifier") or document.suggested_path
        if not identifier:
            continue

        source_path = document.metadata.get("source_path")
        if not source_path:
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


def _filter_existing_documents(
    rows: list[dict[str, Any]], store: VectorStore
) -> list[dict[str, Any]]:
    """Filter out documents that are already indexed and unchanged."""
    if not rows:
        return []

    docs_table = ibis.memtable(rows)
    docs_table = docs_table.filter(docs_table["source_path"] != "")

    remaining = docs_table.count().execute()
    remaining_count = int(remaining.iloc[0, 0]) if hasattr(remaining, "iloc") else int(remaining)

    if remaining_count == 0:
        logger.warning("All document identifiers failed to resolve to paths")
        return []

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

    return new_or_changed.execute().to_dict("records")


def index_documents_for_rag(
    output_format: OutputAdapter,
    rag_dir: Path,
    storage: DuckDBStorageManager,
    *,
    embedding_model: str,
) -> int:
    """Index new/changed documents using incremental indexing via OutputSink."""
    try:
        # 1. Identify Candidates
        rows, doc_count = _identify_indexing_candidates(output_format)
        if doc_count == 0:
            logger.debug("No documents found by output format")
            return 0
        logger.debug("Output sink reported %d documents", doc_count)

        # 2. Filter Existing
        store = VectorStore(rag_dir / "chunks.parquet", storage=storage)
        to_index = _filter_existing_documents(rows, store)

        if not to_index:
            logger.debug("All documents already indexed with current mtime - no work needed")
            return 0

        logger.info(
            "Incremental indexing: %d new/changed documents (skipped %d unchanged)",
            len(to_index),
            doc_count - len(to_index),
        )

        # 3. Process Queue
        indexed_count = 0
        for row in to_index:
            try:
                document_path = Path(row["source_path"])

                doc = _load_document_from_path(document_path)
                if doc is None:
                    logger.warning("Failed to load document %s, skipping", row["storage_identifier"])
                    continue

                index_document(
                    doc,
                    store,
                    embedding_model=embedding_model,
                    source_path=str(document_path),
                    source_mtime_ns=row["mtime_ns"],
                )
                indexed_count += 1
                logger.debug("Indexed document: %s", row["storage_identifier"])
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to index document %s: %s", row["storage_identifier"], e)
                continue

        if indexed_count > 0:
            logger.info("Indexed %d new/changed documents in RAG (incremental)", indexed_count)

    except PromptTooLargeError:
        raise
    except Exception:
        logger.exception("Failed to index documents in RAG")
        return 0

    return indexed_count


def index_post(post_path: Path, store: VectorStore, *, embedding_model: str) -> int:
    """Chunk, embed, and index a blog post. Wrapper around index_document."""
    logger.info("Indexing post: %s", post_path.name)
    doc = _load_document_from_path(post_path)
    if doc is None:
        logger.warning("Failed to load post %s", post_path.name)
        return 0

    return index_document(
        doc,
        store,
        embedding_model=embedding_model,
        source_path=str(post_path.resolve()),
        source_mtime_ns=post_path.stat().st_mtime_ns
    )


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
    """Chunk, embed, and index a media enrichment file. Wrapper around index_document."""
    logger.info("Indexing media enrichment: %s", enrichment_path.name)
    # Note: _load_document_from_path parses frontmatter, but _parse_media_enrichment parses body text.
    # We need to ensure metadata is populated correctly.
    # The current _load_document_from_path logic for enrichment_media might not capture the body-parsed metadata.
    # So we manually construct the document here as before, or update _load_document_from_path.
    # For safety/parity, let's stick to manual construction but use the shared index_document.

    metadata_parsed = _parse_media_enrichment(enrichment_path)
    if not metadata_parsed:
        logger.warning("Failed to parse metadata from %s", enrichment_path.name)
        return 0

    absolute_path = str(enrichment_path.resolve())
    mtime_ns = enrichment_path.stat().st_mtime_ns
    media_uuid = enrichment_path.stem

    # Read content for chunking
    content = enrichment_path.read_text(encoding="utf-8")

    # Construct a Document. We inject the parsed body metadata into the document metadata.
    doc = Document(
        content=content,
        type=DocumentType.MEDIA, # Or ENRICHMENT_MEDIA? Original code used "media" string in row.
        metadata=metadata_parsed, # type: ignore
    )
    # Original code forced document_id to be media_uuid.
    # index_document uses content-hash ID.
    # To maintain strict parity with legacy logic (which used media_uuid as ID),
    # we should ideally pass that through.
    # However, VectorStore schema has `document_id` column.
    # index_document uses doc.document_id.
    # If we want custom ID, we might need to override behavior or accept that IDs change to content-hash.
    # Content-hash is generally better. Let's use standard index_document behavior.
    # BUT, `index_media_enrichment` had specific row mapping logic.
    # The `_create_index_row` handles `ENRICHMENT_MEDIA` / `MEDIA` types by looking at metadata.

    # Let's ensure doc type is correct for _create_index_row
    doc = Document(
        content=content,
        type=DocumentType.ENRICHMENT_MEDIA,
        metadata=metadata_parsed, # type: ignore
    )
    # We need to ensure `media_uuid` is set in metadata for _create_index_row
    doc.metadata["media_uuid"] = media_uuid

    return index_document(
        doc,
        store,
        embedding_model=embedding_model,
        source_path=absolute_path,
        source_mtime_ns=mtime_ns
    )


def index_all_media(docs_dir: Path, store: VectorStore, *, embedding_model: str) -> int:
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


__all__ = [
    "MediaEnrichmentMetadata",
    "index_all_media",
    "index_document",
    "index_documents_for_rag",
    "index_media_enrichment",
    "index_post",
]
