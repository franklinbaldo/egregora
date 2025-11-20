"""RAG Knowledge System: Indexing, Storage, and Retrieval.

This module consolidates the core RAG functionality including:
- Text Embedding (Google GenAI)
- Document Chunking
- Vector Storage (DuckDB VSS + Parquet)
- Indexing Operations (Documents, Media)
- Retrieval Operations (Similarity Search)
- Pydantic AI Integration Helpers

This is a "flattened" version of the previous rag/ package.
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from datetime import time as dt_time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

import duckdb
import httpx
import ibis
import ibis.expr.datatypes as dt
from ibis import IbisError
from ibis.expr.types import Table

from egregora.config import EMBEDDING_DIM
from egregora.data_primitives.document import Document, DocumentType
from egregora.database import ir_schema as database_schema
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.utils.frontmatter_utils import parse_frontmatter

if TYPE_CHECKING:
    from google import genai

    from egregora.output_adapters.base import OutputAdapter

logger = logging.getLogger(__name__)

# ============================================================================
# Constants & Schemas
# ============================================================================

GENAI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT = 60.0
HTTP_TOO_MANY_REQUESTS = 429

TABLE_NAME = "rag_chunks"
INDEX_NAME = "rag_chunks_embedding_idx"
METADATA_TABLE_NAME = "rag_chunks_metadata"
INDEX_META_TABLE = "index_meta"
DEFAULT_ANN_OVERFETCH = 5
DEDUP_MAX_RANK = 2

VECTOR_STORE_SCHEMA = database_schema.RAG_CHUNKS_SCHEMA
SEARCH_RESULT_SCHEMA = database_schema.RAG_SEARCH_RESULT_SCHEMA


# ============================================================================
# Embedder Logic (formerly core.py)
# ============================================================================


def _get_api_key() -> str:
    """Get Google API key from environment."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        msg = "GOOGLE_API_KEY environment variable is required"
        raise ValueError(msg)
    return api_key


def _parse_retry_delay(error_response: dict[str, Any]) -> float:
    """Parse retry delay from 429 error response."""
    try:
        details = error_response.get("error", {}).get("details", [])
        for detail in details:
            if detail.get("@type") == "type.googleapis.com/google.rpc.RetryInfo":
                retry_delay = detail.get("retryDelay", "10s")
                match = re.match(r"(\d+)s", retry_delay)
                if match:
                    # Use 100% of the suggested delay (respect server guidance)
                    return max(5.0, float(match.group(1)))
    except (KeyError, ValueError, AttributeError, TypeError):
        logger.debug("Could not parse retry delay")
    return 10.0


def _call_with_retries(func: Any, max_retries: int = 3) -> Any:
    """Retry wrapper for HTTP calls with rate limit handling."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == HTTP_TOO_MANY_REQUESTS:
                try:
                    error_data = e.response.json()
                    delay = _parse_retry_delay(error_data)
                    logger.warning(
                        "Rate limit exceeded (429). Waiting %s seconds before retry %s/%s...",
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(delay)
                    continue
                except (ValueError, KeyError, AttributeError):
                    logger.warning("429 error but could not parse response. Waiting 10s...")
                    time.sleep(10)
                    continue
            if attempt < max_retries - 1:
                logger.warning("Attempt %s/%s failed: %s. Retrying...", attempt + 1, max_retries, e)
                time.sleep(2)
            continue
        except httpx.HTTPError as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning("Attempt %s/%s failed: %s. Retrying...", attempt + 1, max_retries, e)
                time.sleep(2)
            continue
    msg = f"All {max_retries} attempts failed"
    raise RuntimeError(msg) from last_error


def _validate_embedding_response(data: dict[str, Any]) -> dict[str, Any]:
    """Validate embedding response."""
    embedding = data.get("embedding")
    if not embedding:
        msg = f"No embedding in response: {data}"
        raise RuntimeError(msg)
    return embedding


def _validate_batch_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate batch embedding response."""
    embeddings = data.get("embeddings")
    if not embeddings:
        msg = f"No embeddings in batch response: {data}"
        raise RuntimeError(msg)
    return embeddings


def _validate_embedding_values(values: Any, text_index: int, text: str) -> None:
    """Validate embedding vector values."""
    if not values:
        msg = f"No embedding returned for text {text_index}: {text[:50]}..."
        raise RuntimeError(msg)


def embed_text(
    text: Annotated[str, "The text to embed"],
    *,
    model: Annotated[str, "The embedding model to use (Google format, e.g., 'models/text-embedding-004')"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    api_key: Annotated[str | None, "Optional API key (reads from GOOGLE_API_KEY if not provided)"] = None,
    timeout: Annotated[float, "Request timeout in seconds"] = DEFAULT_TIMEOUT,
) -> Annotated[list[float], "The embedding vector (768 dimensions)"]:
    """Embed a single text using the Google Generative AI HTTP API."""
    effective_api_key = api_key or _get_api_key()
    google_model = model
    payload: dict[str, Any] = {
        "model": google_model,
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": EMBEDDING_DIM,
    }
    if task_type:
        payload["taskType"] = task_type
    url = f"{GENAI_API_BASE}/{google_model}:embedContent"

    def _make_request() -> list[float]:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, params={"key": effective_api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
            embedding = _validate_embedding_response(data)
            return list(embedding["values"])

    return _call_with_retries(_make_request)


def embed_texts_in_batch(
    texts: Annotated[list[str], "List of texts to embed"],
    *,
    model: Annotated[str, "The embedding model to use (Google format, e.g., 'models/text-embedding-004')"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    api_key: Annotated[str | None, "Optional API key (reads from GOOGLE_API_KEY if not provided)"] = None,
    timeout: Annotated[float, "Request timeout in seconds"] = DEFAULT_TIMEOUT,
) -> Annotated[list[list[float]], "List of embedding vectors (768 dimensions each)"]:
    """Embed multiple texts using the Google Generative AI batch HTTP API."""
    if not texts:
        return []
    logger.info("Embedding %d text(s) with model %s", len(texts), model)
    effective_api_key = api_key or _get_api_key()
    google_model = model
    requests = []
    for text in texts:
        request: dict[str, Any] = {
            "model": google_model,
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": EMBEDDING_DIM,
        }
        if task_type:
            request["taskType"] = task_type
        requests.append(request)
    payload = {"requests": requests}
    url = f"{GENAI_API_BASE}/{google_model}:batchEmbedContents"

    def _make_request() -> list[list[float]]:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, params={"key": effective_api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
            embeddings_data = _validate_batch_response(data)
            embeddings: list[list[float]] = []
            for i, embedding_result in enumerate(embeddings_data):
                values = embedding_result.get("values")
                _validate_embedding_values(values, i, texts[i])
                embeddings.append(list(values))
            logger.info("Embedded %d text(s)", len(embeddings))
            return embeddings

    return _call_with_retries(_make_request)


def embed_chunks(
    chunks: Annotated[list[str], "A list of text chunks to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
    task_type: Annotated[str, "The task type for the embedding model"] = "RETRIEVAL_DOCUMENT",
) -> Annotated[list[list[float]], "A list of 768-dimensional embedding vectors for the chunks"]:
    """Embed text chunks using the Google Generative AI HTTP API.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
    """
    if not chunks:
        return []
    embeddings = embed_texts_in_batch(chunks, model=model, task_type=task_type)
    logger.info("Embedded %d chunks (%d dimensions)", len(embeddings), EMBEDDING_DIM)
    return embeddings


def embed_query_text(
    query_text: Annotated[str, "The query text to embed"],
    *,
    model: Annotated[str, "The name of the embedding model to use"],
) -> Annotated[list[float], "The 768-dimensional embedding vector for the query"]:
    """Embed a single query string for retrieval.

    All embeddings use fixed 768-dimension output for consistency and HNSW optimization.
    """
    return embed_text(query_text, model=model, task_type="RETRIEVAL_QUERY")


def is_rag_available() -> bool:
    """Check if RAG functionality is available (API key present)."""
    return bool(os.environ.get("GOOGLE_API_KEY"))


# ============================================================================
# Chunker Logic (formerly core.py)
# ============================================================================


def estimate_tokens(text: str) -> int:
    """Estimate token count (rough approximation: ~4 chars per token)."""
    # Centralized implementation
    from egregora.agents.model_limits import estimate_tokens as _estimate  # noqa: PLC0415

    return _estimate(text)


def chunk_markdown(content: str, max_tokens: int = 1800, overlap_tokens: int = 150) -> list[str]:
    r"""Chunk markdown content respecting token limits."""
    paragraphs = content.split("\n\n")
    chunks = []
    current_chunk: list[str] = []
    current_tokens = 0
    for paragraph in paragraphs:
        para = paragraph.strip()
        if not para:
            continue
        para_tokens = estimate_tokens(para)
        if current_tokens + para_tokens > max_tokens and current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)
            overlap_paras: list[str] = []
            overlap_tokens_count = 0
            for prev_para in reversed(current_chunk):
                prev_tokens = estimate_tokens(prev_para)
                if overlap_tokens_count + prev_tokens <= overlap_tokens:
                    overlap_paras.insert(0, prev_para)
                    overlap_tokens_count += prev_tokens
                else:
                    break
            current_chunk = overlap_paras
            current_tokens = overlap_tokens_count
        current_chunk.append(para)
        current_tokens += para_tokens
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append(chunk_text)
    return chunks


def parse_post(post_path: Path) -> tuple[dict[str, Any], str]:
    """Parse blog post with YAML frontmatter."""
    content = post_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    if "slug" not in metadata:
        filename = post_path.stem
        match = re.match("\\d{4}-\\d{2}-\\d{2}-(.+)", filename)
        if match:
            metadata["slug"] = match.group(1)
        else:
            metadata["slug"] = filename
    if "title" not in metadata:
        metadata["title"] = metadata["slug"].replace("-", " ").title()
    if "date" not in metadata:
        filename = post_path.stem
        match = re.match("(\\d{4}-\\d{2}-\\d{2})", filename)
        if match:
            metadata["date"] = match.group(1)
        else:
            metadata["date"] = None
    return (metadata, body)


def chunk_document(post_path: Path, max_tokens: int = 1800) -> list[dict[str, Any]]:
    """Chunk a blog post into indexable chunks."""
    metadata, content = parse_post(post_path)
    text_chunks = chunk_markdown(content, max_tokens=max_tokens)
    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        chunks.append(
            {
                "content": chunk_text,
                "chunk_index": i,
                "post_slug": metadata["slug"],
                "post_title": metadata["title"],
                "metadata": metadata,
            }
        )
    logger.info("Chunked %s into %s chunks", post_path.name, len(chunks))
    return chunks


def chunk_from_document(document: Document, max_tokens: int = 1800) -> list[dict[str, Any]]:
    """Chunk a Document object into indexable chunks."""
    # Extract slug and title from metadata
    metadata = document.metadata
    slug = metadata.get("slug", document.document_id[:8])
    title = metadata.get("title", slug.replace("-", " ").title())

    # Chunk the document content
    text_chunks = chunk_markdown(document.content, max_tokens=max_tokens)

    chunks = []
    for i, chunk_text in enumerate(text_chunks):
        chunks.append(
            {
                "content": chunk_text,
                "chunk_index": i,
                "post_slug": slug,
                "post_title": title,
                "metadata": metadata,
                "document_id": document.document_id,  # Include content-addressed ID
            }
        )

    logger.info("Chunked Document %s into %s chunks", document.document_id[:8], len(chunks))
    return chunks


# ============================================================================
# Vector Store (formerly store.py)
# ============================================================================


class _ConnectionProxy:
    """Allow attribute overrides on DuckDB connections (e.g., for monkeypatching)."""

    def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_overrides", {})

    def __getattr__(self, name: str) -> Any:  # Proxy pattern requires Any for attribute access
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_inner"), name)

    def __setattr__(
        self, name: str, value: Any
    ) -> None:  # Proxy pattern requires Any for attribute assignment
        if name in {"_inner", "_overrides"}:
            object.__setattr__(self, name, value)
            return
        overrides = object.__getattribute__(self, "_overrides")
        overrides[name] = value


@dataclass(frozen=True)
class DatasetMetadata:
    """Lightweight container for persisted dataset metadata."""

    mtime_ns: int
    size: int
    row_count: int


class VectorStore:
    conn: _ConnectionProxy
    "\n    Vector store backed by Parquet file.\n\n    Uses DuckDB VSS extension for similarity search.\n    Data lives in Parquet for portability and client-side access.\n    "

    def __init__(
        self,
        parquet_path: Path,
        *,
        storage: DuckDBStorageManager,
    ) -> None:
        """Initialize vector store."""
        self.parquet_path = parquet_path
        self.index_path = parquet_path.with_suffix(".duckdb")
        self.conn = _ConnectionProxy(storage.conn)
        self.backend = storage  # Use storage directly as backend
        self._vss_available = False
        self._vss_function = "vss_search"
        self._client = ibis.duckdb.from_connection(self.conn)
        self._table_synced = False
        self._ensure_index_meta_table()
        self._ensure_dataset_loaded()

    def _init_vss(self) -> bool:
        """Initialize DuckDB VSS extension (lazy loading)."""
        if self._vss_available:
            return True
        self._vss_available = self.backend.install_vss_extensions()
        if not self._vss_available:
            logger.info("VSS extension unavailable; ANN mode disabled")
            return False
        self._vss_function = self.backend.detect_vss_function()
        logger.info("DuckDB VSS extension loaded")
        return True

    def _ensure_dataset_loaded(self, *, force: bool = False) -> None:
        """Materialize the Parquet dataset into DuckDB and refresh the ANN index."""
        self._ensure_metadata_table()
        if not self.parquet_path.exists():
            self.backend.drop_index(INDEX_NAME)
            self.backend.drop_table(TABLE_NAME, checkpoint_too=False)
            self._store_metadata(None)
            self._table_synced = True
            return
        stored_metadata = self._get_stored_metadata()
        current_metadata = self._read_parquet_metadata()
        table_exists = self.backend.table_exists(TABLE_NAME)
        metadata_changed = stored_metadata != current_metadata
        if not force and (not metadata_changed) and table_exists:
            self._table_synced = True
            return

        # Materialize chunks table from parquet
        quoted_table = f'"{TABLE_NAME}"'
        try:
            self.backend.conn.execute(
                f"CREATE OR REPLACE TABLE {quoted_table} AS SELECT * FROM read_parquet(?)",
                [str(self.parquet_path)],
            )
        except Exception as e:
            logger.error(f"Failed to materialize chunks table: {e}")
            raise

        self._store_metadata(current_metadata)
        if force or metadata_changed or (not table_exists):
            self._rebuild_index()
        self._table_synced = True

    def _ensure_metadata_table(self) -> None:
        """Create the internal metadata table when missing."""
        database_schema.create_table_if_not_exists(
            self._client, METADATA_TABLE_NAME, database_schema.RAG_CHUNKS_METADATA_SCHEMA
        )
        database_schema.add_primary_key(self.conn, METADATA_TABLE_NAME, "path")

    def _ensure_index_meta_table(self) -> None:
        """Create the table used to persist ANN index metadata."""
        database_schema.create_table_if_not_exists(
            self._client, INDEX_META_TABLE, database_schema.RAG_INDEX_META_SCHEMA
        )
        self._migrate_index_meta_table()
        database_schema.add_primary_key(self.conn, INDEX_META_TABLE, "index_name")

    def _migrate_index_meta_table(self) -> None:
        """Ensure legacy index metadata tables gain any newly introduced columns."""
        existing_columns = {
            row[1].lower() for row in self.conn.execute(f"PRAGMA table_info('{INDEX_META_TABLE}')").fetchall()
        }
        schema = database_schema.RAG_INDEX_META_SCHEMA
        for column in schema.names:
            if column.lower() in existing_columns:
                continue
            column_type = self._duckdb_type_from_ibis(schema[column])
            if column_type is None:
                logger.warning(
                    "Skipping migration for %s.%s due to unsupported type %s",
                    INDEX_META_TABLE,
                    column,
                    schema[column],
                )
                continue
            self.conn.execute(f"ALTER TABLE {INDEX_META_TABLE} ADD COLUMN {column} {column_type}")

    @staticmethod
    def _duckdb_type_from_ibis(dtype: dt.DataType) -> str | None:
        """Map a subset of Ibis data types to DuckDB column definitions."""
        if dtype.is_string():
            result = "VARCHAR"
        elif dtype.is_int64():
            result = "BIGINT"
        elif dtype.is_int32():
            result = "INTEGER"
        elif dtype.is_float64():
            result = "DOUBLE"
        elif dtype.is_boolean():
            result = "BOOLEAN"
        elif dtype.is_timestamp():
            result = "TIMESTAMP WITH TIME ZONE" if getattr(dtype, "timezone", None) else "TIMESTAMP"
        elif dtype.is_date():
            result = "DATE"
        elif dtype.is_array():
            inner = VectorStore._duckdb_type_from_ibis(dtype.value_type)
            result = None if inner is None else f"{inner}[]"
        else:
            result = None
        return result

    def _get_stored_metadata(self) -> DatasetMetadata | None:
        """Fetch cached metadata for the backing Parquet file."""
        row = self.conn.execute(
            f"SELECT mtime_ns, size, row_count FROM {METADATA_TABLE_NAME} WHERE path = ?",
            [str(self.parquet_path)],
        ).fetchone()
        if not row:
            return None
        mtime_ns, size, row_count = row
        if mtime_ns is None or size is None or row_count is None:
            return None
        return DatasetMetadata(mtime_ns=int(mtime_ns), size=int(size), row_count=int(row_count))

    def _store_metadata(self, metadata: DatasetMetadata | None) -> None:
        """Persist or remove cached metadata for the backing Parquet file."""
        self.conn.execute(f"DELETE FROM {METADATA_TABLE_NAME} WHERE path = ?", [str(self.parquet_path)])
        if metadata is None:
            return
        self.conn.execute(
            f"INSERT INTO {METADATA_TABLE_NAME} (path, mtime_ns, size, row_count) VALUES (?, ?, ?, ?)",
            [str(self.parquet_path), metadata.mtime_ns, metadata.size, metadata.row_count],
        )

    def _read_parquet_metadata(self) -> DatasetMetadata:
        """Inspect the Parquet file for structural metadata."""
        stats = self.parquet_path.stat()
        row = self.conn.execute("SELECT COUNT(*) FROM read_parquet(?)", [str(self.parquet_path)]).fetchone()
        row_count = int(row[0]) if row and row[0] is not None else 0
        return DatasetMetadata(
            mtime_ns=int(stats.st_mtime_ns), size=int(stats.st_size), row_count=int(row_count)
        )

    def _rebuild_index(self) -> None:
        """Recreate the VSS index for the materialized chunks table."""
        self.backend.drop_index(INDEX_NAME)
        self._ensure_index_meta_table()
        if not self.backend.table_exists(TABLE_NAME):
            self._clear_index_meta()
            return
        row_count = self.backend.row_count(TABLE_NAME)
        if row_count == 0:
            self._clear_index_meta()
            return
        if not self._init_vss():
            logger.info("VSS not available, skipping index creation")
            self._clear_index_meta()
            return
        if not self.backend.create_hnsw_index(table_name=TABLE_NAME, index_name=INDEX_NAME):
            self._clear_index_meta()
            return
        self._upsert_index_meta(
            mode="ann",
            row_count=row_count,
            threshold=0,
            nlist=None,
        )

    def _upsert_index_meta(
        self,
        *,
        mode: str,
        row_count: int,
        threshold: int,
        nlist: int | None,
        embedding_dim: int | None = None,
    ) -> None:
        """Persist the latest index configuration for observability and telemetry."""
        timestamp = datetime.now(tz=UTC)
        self.conn.execute(
            f"\n            INSERT INTO {INDEX_META_TABLE} (\n                index_name,\n                mode,\n                row_count,\n                threshold,\n                nlist,\n                embedding_dim,\n                created_at,\n                updated_at\n            )\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n            ON CONFLICT(index_name) DO UPDATE SET\n                mode=excluded.mode,\n                row_count=excluded.row_count,\n                threshold=excluded.threshold,\n                nlist=excluded.nlist,\n                embedding_dim=excluded.embedding_dim,\n                updated_at=excluded.updated_at\n            ",
            [INDEX_NAME, mode, row_count, threshold, nlist, embedding_dim, timestamp, timestamp],
        )

    def _clear_index_meta(self) -> None:
        """Remove metadata when the backing table is empty or missing."""
        self.conn.execute(f"DELETE FROM {INDEX_META_TABLE} WHERE index_name = ?", [INDEX_NAME])

    def _get_stored_embedding_dim(self) -> int | None:
        """Fetch the stored embedding dimensionality from index metadata."""
        row = self.conn.execute(
            f"SELECT embedding_dim FROM {INDEX_META_TABLE} WHERE index_name = ?",
            [INDEX_NAME],
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def _validate_embedding_dimension(self, embeddings: list[list[float]], context: str) -> int:
        """Validate embedding dimensionality consistency."""
        if not embeddings:
            msg = f"{context}: No embeddings provided"
            raise ValueError(msg)
        dimensions = {len(emb) for emb in embeddings}
        if len(dimensions) > 1:
            msg = f"{context}: Inconsistent embedding dimensions within batch: {sorted(dimensions)}"
            raise ValueError(msg)
        current_dim = dimensions.pop()
        if current_dim != EMBEDDING_DIM:
            msg = f"{context}: Embedding dimension mismatch. Expected {EMBEDDING_DIM} (fixed dimension), got {current_dim}. All embeddings must use 768 dimensions."
            raise ValueError(msg)
        return current_dim

    def add(self, chunks_table: Table) -> None:
        """Add chunks to the vector store."""
        self._validate_table_schema(chunks_table, context="new chunks")
        chunks_table = self._ensure_local_table(chunks_table)
        chunks_df = chunks_table.execute()
        if len(chunks_df) > 0 and "embedding" in chunks_df.columns:
            embeddings = chunks_df["embedding"].tolist()
            embedding_dim = self._validate_embedding_dimension(embeddings, "New chunks")
            logger.info("Validated embedding dimension: %s", embedding_dim)
        else:
            embedding_dim = None
        if self.parquet_path.exists():
            existing_table = self._client.read_parquet(self.parquet_path)
            existing_table = self._migrate_legacy_schema(existing_table)
            self._validate_table_schema(existing_table, context="existing vector store")
            existing_table, chunks_table = self._align_schemas(existing_table, chunks_table)
            combined_table = existing_table.union(chunks_table, distinct=False)
            existing_count = existing_table.count().execute()
            new_count = chunks_table.count().execute()
            logger.info("Appending %s chunks to existing %s chunks", new_count, existing_count)
        else:
            combined_table = self._cast_to_vector_store_schema(chunks_table)
            chunk_count = chunks_table.count().execute()
            logger.info("Creating new vector store with %s chunks", chunk_count)
        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        view_name = f"_egregora_chunks_{uuid.uuid4().hex}"
        self._client.create_view(view_name, combined_table, overwrite=True)
        try:
            self.conn.execute(
                f"COPY (SELECT * FROM {view_name}) TO ? (FORMAT PARQUET)",
                [str(self.parquet_path)],
            )
        finally:
            self._client.drop_view(view_name, force=True)
        self._table_synced = False
        self._ensure_dataset_loaded(force=True)
        if embedding_dim is not None:
            row_count = combined_table.count().execute()
            self._upsert_index_meta(
                mode="unknown", row_count=row_count, threshold=0, nlist=None, embedding_dim=embedding_dim
            )
        logger.info("Vector store saved to %s", self.parquet_path)

    def _align_schemas(self, existing_table: Table, new_table: Table) -> tuple[Table, Table]:
        """Cast both tables to the canonical vector store schema."""
        existing_table = self._cast_to_vector_store_schema(existing_table)
        new_table = self._cast_to_vector_store_schema(new_table)
        return (existing_table, new_table)

    def _migrate_legacy_schema(self, table: Table) -> Table:
        """Migrate legacy RAG schemas by adding missing columns with default values."""
        expected_columns = set(VECTOR_STORE_SCHEMA.names)
        table_columns = set(table.columns)
        missing = sorted(expected_columns - table_columns)

        if not missing:
            return table  # No migration needed

        logger.info(
            "Migrating legacy RAG schema: adding %d missing columns with NULL defaults: %s",
            len(missing),
            ", ".join(missing),
        )

        mutations = {}
        for column_name in missing:
            column_type = VECTOR_STORE_SCHEMA[column_name]

            if not column_type.nullable:
                msg = (
                    f"Cannot migrate legacy schema: column '{column_name}' is NOT nullable. "
                    f"Migration requires all new columns to be nullable."
                )
                raise ValueError(msg)

            mutations[column_name] = ibis.null().cast(column_type)

        migrated_table = table.mutate(**mutations)

        logger.debug("Migration complete - all expected columns present")
        return migrated_table

    def _validate_table_schema(self, table: Table, *, context: str) -> None:
        """Ensure the provided table matches the expected vector store schema."""
        expected_columns = set(VECTOR_STORE_SCHEMA.names)
        table_columns = set(table.columns)
        missing = sorted(expected_columns - table_columns)
        unexpected = sorted(table_columns - expected_columns)
        if missing or unexpected:
            parts = []
            if missing:
                parts.append(f"missing columns: {', '.join(missing)}")
            if unexpected:
                parts.append(f"unexpected columns: {', '.join(unexpected)}")
            detail = "; ".join(parts)
            msg = f"{context} do not match the vector store schema ({detail})."
            raise ValueError(msg)

    def _cast_to_vector_store_schema(self, table: Table) -> Table:
        """Cast the table to the canonical vector store schema ordering and types."""
        casts = {}
        for column_name, dtype in VECTOR_STORE_SCHEMA.items():
            column = table[column_name]
            if column.type() != dtype:
                casts[column_name] = column.cast(dtype)
        if casts:
            table = table.mutate(**casts)
        return table.select(VECTOR_STORE_SCHEMA.names)

    def search(  # noqa: PLR0913
        self,
        query_vec: list[float],
        top_k: int = 5,
        min_similarity_threshold: float = 0.7,
        tag_filter: list[str] | None = None,
        date_after: date | datetime | str | None = None,
        document_type: str | None = None,
        media_types: list[str] | None = None,
        *,
        mode: str = "ann",
        nprobe: int | None = None,
        overfetch: int | None = None,
    ) -> Table:
        """Search for similar chunks using cosine similarity."""
        if not self._table_available():
            return self._empty_table(SEARCH_RESULT_SCHEMA)

        mode_normalized = self._validate_and_normalize_mode(mode)
        embedding_dimensionality = self._validate_query_vector(query_vec)
        self._validate_search_parameters(nprobe)

        params, filters = self._build_search_filters(
            query_vec, min_similarity_threshold, tag_filter, date_after, document_type, media_types
        )
        where_clause, order_clause = self._build_query_clauses(filters, top_k)

        if mode_normalized == "exact":
            return self._search_exact(where_clause, order_clause, params, min_similarity_threshold)

        return self._search_ann(
            where_clause,
            order_clause,
            params,
            min_similarity_threshold,
            top_k,
            nprobe,
            overfetch,
            embedding_dimensionality,
        )

    def _table_available(self) -> bool:
        """Check if vector store parquet file and table exist."""
        if not self.parquet_path.exists():
            logger.warning("Vector store does not exist yet")
            return False
        self._ensure_dataset_loaded()
        return self.backend.table_exists(TABLE_NAME)

    def _validate_and_normalize_mode(self, mode: str) -> str:
        """Normalize and validate search mode, switching to exact if VSS unavailable."""
        mode_normalized = mode.lower()
        if mode_normalized not in {"ann", "exact"}:
            msg = "mode must be either 'ann' or 'exact'"
            raise ValueError(msg)
        if mode_normalized == "ann" and (not self._init_vss()):
            logger.info("ANN mode requested but VSS unavailable, using exact search")
            mode_normalized = "exact"
        return mode_normalized

    def _validate_query_vector(self, query_vec: list[float]) -> int:
        """Validate query vector dimensionality."""
        embedding_dimensionality = len(query_vec)
        if embedding_dimensionality != EMBEDDING_DIM:
            msg = f"Query embedding dimension mismatch. Expected {EMBEDDING_DIM} (fixed dimension), got {embedding_dimensionality}. All embeddings must use 768 dimensions."
            raise ValueError(msg)
        return embedding_dimensionality

    def _validate_search_parameters(self, nprobe: int | None) -> None:
        """Validate nprobe parameter."""
        if nprobe is not None and nprobe <= 0:
            msg = "nprobe must be a positive integer"
            raise ValueError(msg)

    def _build_search_filters(  # noqa: PLR0913
        self,
        query_vec: list[float],
        min_similarity_threshold: float,
        tag_filter: list[str] | None,
        date_after: date | datetime | str | None,
        document_type: str | None,
        media_types: list[str] | None,
    ) -> tuple[list[Any], list[str]]:
        """Build filter clauses and parameter list for search query."""
        params: list[Any] = [query_vec]
        filters: list[str] = []

        if document_type:
            filters.append("document_type = ?")
            params.append(document_type)
        if media_types:
            placeholders = ", ".join(["?"] * len(media_types))
            filters.append(f"media_type IN ({placeholders})")
            params.extend(media_types)
        if tag_filter:
            filters.append("list_has_any(tags, ?::VARCHAR[])")
            params.append(tag_filter)
        if date_after is not None:
            normalized_date = self._normalize_date_filter(date_after)
            filters.append("coalesce(CAST(post_date AS TIMESTAMPTZ), message_date) > ?::TIMESTAMPTZ")
            params.append(normalized_date.isoformat())

        filters.append("similarity >= ?")
        params.append(min_similarity_threshold)

        return params, filters

    def _build_query_clauses(self, filters: list[str], top_k: int) -> tuple[str, str]:
        """Build WHERE and ORDER BY clauses for search query."""
        where_clause = ""
        if filters:
            where_clause = " WHERE " + " AND ".join(filters)
        order_clause = f"\n            ORDER BY similarity DESC\n            LIMIT {top_k}\n        "
        return where_clause, order_clause

    def _build_exact_query(self) -> str:
        """Build base query for exact cosine similarity search."""
        return f"\n            WITH candidates AS (\n                SELECT\n                    * EXCLUDE (embedding),\n                    array_cosine_similarity(\n                        embedding::FLOAT[{EMBEDDING_DIM}],\n                        ?::FLOAT[{EMBEDDING_DIM}]\n                    ) AS similarity\n                FROM {TABLE_NAME}\n            )\n            SELECT * FROM candidates\n        "

    def _search_exact(
        self,
        where_clause: str,
        order_clause: str,
        params: list[Any],
        min_similarity_threshold: float,
    ) -> Table:
        """Execute exact cosine similarity search."""
        query = self._build_exact_query() + where_clause + order_clause
        try:
            return self._execute_search_query(query, params, min_similarity_threshold)
        except Exception:
            logger.exception("Search failed")
            return self._empty_table(SEARCH_RESULT_SCHEMA)

    def _search_ann(  # noqa: PLR0913
        self,
        where_clause: str,
        order_clause: str,
        params: list[Any],
        min_similarity_threshold: float,
        top_k: int,
        nprobe: int | None,
        overfetch: int | None,
        embedding_dimensionality: int,
    ) -> Table:
        """Execute ANN search with fallback to exact search."""
        fetch_factor = overfetch if overfetch and overfetch > 1 else DEFAULT_ANN_OVERFETCH
        ann_limit = max(top_k * fetch_factor, top_k + 10)
        nprobe_clause = f", nprobe := {int(nprobe)}" if nprobe else ""

        last_error: Exception | None = None
        for function_name in self._candidate_vss_functions():
            result = self._try_ann_search(
                function_name,
                where_clause,
                order_clause,
                params,
                min_similarity_threshold,
                ann_limit,
                nprobe_clause,
                embedding_dimensionality,
            )
            if result is not None:
                return result
            last_error = getattr(self, "_last_ann_error", None)

        return self._handle_ann_failure(
            last_error, where_clause, order_clause, params, min_similarity_threshold
        )

    def _try_ann_search(  # noqa: PLR0913
        self,
        function_name: str,
        where_clause: str,
        order_clause: str,
        params: list[Any],
        min_similarity_threshold: float,
        ann_limit: int,
        nprobe_clause: str,
        embedding_dimensionality: int,
    ) -> Table | None:
        """Attempt ANN search with given VSS function."""
        base_query = self._build_ann_query(
            function_name,
            ann_limit=ann_limit,
            nprobe_clause=nprobe_clause,
            _embedding_dimensionality=embedding_dimensionality,
        )
        query = base_query + where_clause + order_clause
        try:
            result = self._execute_search_query(query, params, min_similarity_threshold)
        except duckdb.Error as exc:
            self._last_ann_error = exc
            logger.warning("ANN search failed with %s: %s", function_name, exc)
            return None
        except Exception as exc:
            self._last_ann_error = exc
            logger.exception("ANN search aborted")
            return None
        else:
            self._vss_function = function_name
            return result

    def _handle_ann_failure(
        self,
        last_error: Exception | None,
        where_clause: str,
        order_clause: str,
        params: list[Any],
        min_similarity_threshold: float,
    ) -> Table:
        """Handle ANN search failure with fallback to exact search or error logging."""
        if last_error is not None and "does not support the supplied arguments" in str(last_error).lower():
            logger.info("Falling back to exact search due to VSS compatibility issues")
            try:
                query = self._build_exact_query() + where_clause + order_clause
                return self._execute_search_query(query, params, min_similarity_threshold)
            except Exception:
                logger.exception("Exact fallback search failed")

        if last_error is not None:
            logger.error("Search failed: %s", last_error)
        else:
            logger.error("Search failed: no compatible VSS table function available")
        return self._empty_table(SEARCH_RESULT_SCHEMA)

    def _build_ann_query(
        self, function_name: str, *, ann_limit: int, nprobe_clause: str, _embedding_dimensionality: int
    ) -> str:
        return f"\n            WITH candidates AS (\n                SELECT\n                    base.*,\n                    1 - vs.distance AS similarity\n                FROM {function_name}(\n                    '{TABLE_NAME}',\n                    'embedding',\n                    ?::FLOAT[{EMBEDDING_DIM}],\n                    top_k := {ann_limit},\n                    metric := 'cosine'{nprobe_clause}\n                ) AS vs\n                JOIN {TABLE_NAME} AS base\n                  ON vs.rowid = base.rowid\n            )\n            SELECT * FROM candidates\n        "

    def _candidate_vss_functions(self) -> list[str]:
        """Return preferred VSS table functions in fallback order."""
        candidates = [self._vss_function]
        for function_name in ("vss_match", "vss_search"):
            if function_name not in candidates:
                candidates.append(function_name)
        return candidates

    def _execute_search_query(self, query: str, params: list[Any], min_similarity_threshold: float) -> Table:
        """Execute the provided search query and normalize the results."""
        cursor = self.conn.execute(query, params)
        columns = [description[0] for description in cursor.description or []]
        rows = cursor.fetchall()
        if not rows:
            return self._empty_table(SEARCH_RESULT_SCHEMA)
        raw_records = [dict(zip(columns, row, strict=False)) for row in rows]
        prepared_records = self._prepare_search_results(raw_records)
        table = self._table_from_rows(prepared_records, SEARCH_RESULT_SCHEMA)
        row_count = table.count().execute()
        logger.info(
            "Found %d similar chunks (min_similarity_threshold=%s)", row_count, min_similarity_threshold
        )
        return table

    def _prepare_search_results(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize DuckDB result rows to match the search schema."""
        if not records:
            return []
        normalized: list[dict[str, Any]] = []
        valid_columns = set(SEARCH_RESULT_SCHEMA.names) | {"similarity"}
        for index, record in enumerate(records):
            filtered = {key: value for key, value in record.items() if key in valid_columns}
            filtered.setdefault("document_type", "post")
            chunk_id = filtered.get("chunk_id") or ""
            post_slug = filtered.get("post_slug")
            document_id = filtered.get("document_id") or post_slug or chunk_id
            filtered["document_id"] = document_id
            for column_name in ("tags", "authors"):
                value = filtered.get(column_name)
                filtered[column_name] = list(value or [])
            for column_name in (
                "post_slug",
                "post_title",
                "post_date",
                "media_uuid",
                "media_type",
                "media_path",
                "original_filename",
                "message_date",
                "author_uuid",
                "category",
            ):
                filtered.setdefault(column_name, None)
            filtered.setdefault("chunk_index", index)
            normalized.append(filtered)
        return normalized

    @staticmethod
    def _normalize_date_filter(value: date | datetime | str) -> datetime:
        """Normalize date filter inputs to UTC-aware datetimes."""
        if isinstance(value, datetime):
            return VectorStore._ensure_utc_datetime(value)
        if isinstance(value, date):
            return datetime.combine(value, dt_time.min, tzinfo=UTC)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            try:
                parsed_dt = datetime.fromisoformat(cleaned)
            except ValueError:
                try:
                    parsed_date = date.fromisoformat(cleaned)
                except ValueError as exc:
                    msg = f"Invalid date_after value: {value!r}"
                    raise ValueError(msg) from exc
                return datetime.combine(parsed_date, dt_time.min, tzinfo=UTC)
            return VectorStore._ensure_utc_datetime(parsed_dt)
        msg = "date_after must be a date, datetime, or ISO8601 string"
        raise TypeError(msg)

    @staticmethod
    def _ensure_utc_datetime(value: datetime) -> datetime:
        """Coerce datetime objects to UTC-aware variants."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _table_from_rows(self, records: list[dict[str, Any]], schema: ibis.Schema) -> Table:
        """Create a DuckDB-backed table from an in-memory sequence of records."""
        if not records:
            return self._empty_table(schema)
        temp_name = f"_vector_store_{uuid.uuid4().hex}"
        column_defs = []
        for column_name, dtype in schema.items():
            column_type = self._duckdb_type_from_ibis(dtype)
            if column_type is None:
                msg = f"Unsupported dtype {dtype!r} for column {column_name}"
                raise TypeError(msg)
            column_defs.append(f"{column_name} {column_type}")
        columns_sql = ", ".join(column_defs)
        self.conn.execute(f"CREATE TEMP TABLE {temp_name} ({columns_sql})")
        column_names = list(schema.names)
        placeholders = ", ".join("?" for _ in column_names)
        values = [tuple(record.get(name) for name in column_names) for record in records]
        if values:
            self.conn.executemany(
                f"INSERT INTO {temp_name} ({', '.join(column_names)}) VALUES ({placeholders})",
                values,
            )
        return self._client.table(temp_name)

    def _ensure_local_table(self, table: Table) -> Table:
        """Materialize a table on the store backend when necessary."""
        try:
            backend = table._find_backend()
        except (AttributeError, RuntimeError, IbisError) as e:
            logger.debug("Could not determine table backend: %s", e)
            backend = None
        if backend is self._client:
            return table

        source_schema = table.schema()
        dataframe = None
        if backend is None:
            op = getattr(table, "op", lambda: None)()
            data_proxy = getattr(op, "data", None)
            if data_proxy is not None:
                dataframe = data_proxy.to_frame()
        if dataframe is None:
            dataframe = table.execute()

        records = (
            dataframe.to_dict("records")
            if hasattr(dataframe, "to_dict")
            else [dict(zip(source_schema.names, row, strict=False)) for row in dataframe]
        )
        return self._table_from_rows(records, source_schema)

    def _empty_table(self, schema: ibis.Schema) -> Table:
        """Create an empty table with the given schema using the local backend."""
        return ibis.memtable([], schema=schema)

    def get_indexed_sources(self) -> dict[str, int]:
        """Get indexed source files with their modification times."""
        if not self.parquet_path.exists():
            return {}

        try:
            self._ensure_dataset_loaded()

            result = self.conn.execute(
                f"""
                SELECT DISTINCT source_path, source_mtime_ns
                FROM {TABLE_NAME}
                WHERE source_path IS NOT NULL
                """
            ).fetchall()

            return {str(path): int(mtime) for path, mtime in result if path and mtime is not None}

        except (duckdb.Error, IbisError) as e:
            logger.warning("Failed to get indexed sources: %s", e)
            return {}

    def get_indexed_sources_table(self) -> Table:
        """Get indexed source files as an Ibis table for efficient delta detection."""
        if not self.parquet_path.exists():
            return ibis.memtable(
                [], schema=ibis.schema({"source_path": "string", "source_mtime_ns": "int64"})
            )

        try:
            self._ensure_dataset_loaded()
            table = self._client.table(TABLE_NAME)
            return (
                table.filter(table.source_path.notnull()).select("source_path", "source_mtime_ns").distinct()
            )
        except (duckdb.Error, IbisError) as e:
            logger.warning("Failed to get indexed sources table: %s", e)
            return ibis.memtable(
                [], schema=ibis.schema({"source_path": "string", "source_mtime_ns": "int64"})
            )


# ============================================================================
# Indexing Operations (formerly operations.py)
# ============================================================================


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


def index_documents_for_rag(  # noqa: C901
    output_format: OutputAdapter,
    rag_dir: Path,
    storage: DuckDBStorageManager,
    *,
    embedding_model: str,
) -> int:
    """Index new/changed documents using incremental indexing via OutputAdapter."""
    try:
        from egregora.agents.model_limits import PromptTooLargeError

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
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to index document %s: %s", row.storage_identifier, e)
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
    """Chunk, embed, and index a blog post."""
    logger.info("Indexing post: %s", post_path.name)
    chunks = chunk_document(post_path, max_tokens=1800)
    if not chunks:
        logger.warning("No chunks generated from %s", post_path.name)
        return 0

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
    """Chunk, embed, and index a media enrichment file."""
    logger.info("Indexing media enrichment: %s", enrichment_path.name)
    metadata = _parse_media_enrichment(enrichment_path)
    if not metadata:
        logger.warning("Failed to parse metadata from %s", enrichment_path.name)
        return 0

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


# ============================================================================
# Retrieval Operations (formerly operations.py & pydantic_helpers.py)
# ============================================================================


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
        df = results.execute()
        if getattr(df, "empty", False):
            logger.info("No relevant docs found for query: %s", query[:50])
            return []
        records = df.to_dict("records")
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
