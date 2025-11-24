"""Vector storage for RAG knowledge system.

Provides DuckDB VSS-backed vector storage with Parquet persistence for
chunk embeddings and similarity search.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from datetime import time as dt_time
from pathlib import Path
from typing import Any

import duckdb
import ibis
import ibis.expr.datatypes as dt
from ibis.common.exceptions import IbisError
from ibis.expr.types import Table

from egregora.config import EMBEDDING_DIM
from egregora.database import ir_schema as database_schema
from egregora.database.duckdb_manager import DuckDBStorageManager

logger = logging.getLogger(__name__)

# Constants
TABLE_NAME = "rag_chunks"
INDEX_NAME = "rag_chunks_embedding_idx"
METADATA_TABLE_NAME = "rag_chunks_metadata"
INDEX_META_TABLE = "index_meta"
DEFAULT_ANN_OVERFETCH = 5
DEDUP_MAX_RANK = 2

VECTOR_STORE_SCHEMA = database_schema.RAG_CHUNKS_SCHEMA
SEARCH_RESULT_SCHEMA = database_schema.RAG_SEARCH_RESULT_SCHEMA


@dataclass(frozen=True)
class DatasetMetadata:
    """Lightweight container for persisted dataset metadata."""

    mtime_ns: int
    size: int
    row_count: int


class VectorStore:
    """
    Vector store backed by Parquet file.

    Uses DuckDB VSS extension for similarity search.
    Data lives in Parquet for portability and client-side access.
    """

    def __init__(
        self,
        parquet_path: Path,
        *,
        storage: DuckDBStorageManager,
    ) -> None:
        """Initialize vector store."""
        self.parquet_path = parquet_path
        self.index_path = parquet_path.with_suffix(".duckdb")
        # Removed: self.conn = _ConnectionProxy(storage.conn)
        self.backend = storage  # Use storage directly as backend
        self._vss_function = "vss_search"
        # DuckDBStorageManager provides generic connection access now
        # Initialize Ibis client from the storage manager's connection
        # Note: storage.ibis_conn exists, we can use that or create a new one
        # Ideally share the ibis connection if possible, or create one from the raw connection context
        # But VectorStore methods need persistent access to `ibis.duckdb.from_connection(self.conn)`.
        # Let's rely on `storage.ibis_conn` if available, or create a local one if needed.
        # Since `DuckDBStorageManager` has `ibis_conn`, let's use it.
        self._client = storage.ibis_conn
        self._table_synced = False

        # Ensure VSS function is detected (delegated to manager)
        self._vss_function = self.backend.detect_vss_function()

        self._ensure_index_meta_table()
        self._ensure_dataset_loaded()

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
        # Using quote_identifier from manager module not directly available here?
        # We can use generic sql execution from manager
        # Or just trust table name is constant safe string here
        quoted_table = f'"{TABLE_NAME}"'
        try:
            with self.backend.connection() as conn:
                conn.execute(
                    f"CREATE OR REPLACE TABLE {quoted_table} AS SELECT * FROM read_parquet(?)",
                    [str(self.parquet_path)],
                )
        except Exception:
            logger.exception("Failed to materialize chunks table")
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
        # Primary key handling needs connection
        with self.backend.connection() as conn:
             database_schema.add_primary_key(conn, METADATA_TABLE_NAME, "path")

    def _ensure_index_meta_table(self) -> None:
        """Create the table used to persist ANN index metadata."""
        database_schema.create_table_if_not_exists(
            self._client, INDEX_META_TABLE, database_schema.RAG_INDEX_META_SCHEMA
        )
        self._migrate_index_meta_table()
        with self.backend.connection() as conn:
            database_schema.add_primary_key(conn, INDEX_META_TABLE, "index_name")

    def _migrate_index_meta_table(self) -> None:
        """Ensure legacy index metadata tables gain any newly introduced columns."""
        with self.backend.connection() as conn:
            existing_columns = {
                row[1].lower() for row in conn.execute(f"PRAGMA table_info('{INDEX_META_TABLE}')").fetchall()
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
                conn.execute(f"ALTER TABLE {INDEX_META_TABLE} ADD COLUMN {column} {column_type}")

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
        with self.backend.connection() as conn:
            row = conn.execute(
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
        with self.backend.connection() as conn:
            conn.execute(f"DELETE FROM {METADATA_TABLE_NAME} WHERE path = ?", [str(self.parquet_path)])
            if metadata is None:
                return
            conn.execute(
                f"INSERT INTO {METADATA_TABLE_NAME} (path, mtime_ns, size, row_count) VALUES (?, ?, ?, ?)",
                [str(self.parquet_path), metadata.mtime_ns, metadata.size, metadata.row_count],
            )

    def _read_parquet_metadata(self) -> DatasetMetadata:
        """Inspect the Parquet file for structural metadata."""
        stats = self.parquet_path.stat()
        with self.backend.connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM read_parquet(?)", [str(self.parquet_path)]).fetchone()
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
        # VSS extensions managed by DuckDBStorageManager now
        # We just need to create the index
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
        with self.backend.connection() as conn:
            conn.execute(
                f"\n            INSERT INTO {INDEX_META_TABLE} (\n                index_name,\n                mode,\n                row_count,\n                threshold,\n                nlist,\n                embedding_dim,\n                created_at,\n                updated_at\n            )\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n            ON CONFLICT(index_name) DO UPDATE SET\n                mode=excluded.mode,\n                row_count=excluded.row_count,\n                threshold=excluded.threshold,\n                nlist=excluded.nlist,\n                embedding_dim=excluded.embedding_dim,\n                updated_at=excluded.updated_at\n            ",
                [INDEX_NAME, mode, row_count, threshold, nlist, embedding_dim, timestamp, timestamp],
            )

    def _clear_index_meta(self) -> None:
        """Remove metadata when the backing table is empty or missing."""
        with self.backend.connection() as conn:
            conn.execute(f"DELETE FROM {INDEX_META_TABLE} WHERE index_name = ?", [INDEX_NAME])

    def _get_stored_embedding_dim(self) -> int | None:
        """Fetch the stored embedding dimensionality from index metadata."""
        with self.backend.connection() as conn:
            row = conn.execute(
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
            # Legacy migration removed as per refactor goal
            # existing_table = self._migrate_legacy_schema(existing_table)

            # Instead, strict validation
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
            with self.backend.connection() as conn:
                conn.execute(
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
        # VSS detection is now handled by manager/init, we just check avail flag?
        # Actually manager loads it. If manager loaded it successfully, we can use it.
        # We can rely on self._vss_function presence or similar logic.
        # Let's assume if we got here, VSS is available unless configured otherwise.
        # Actually `detect_vss_function` returns a name, implying availability.
        # But we might want to check if `install_vss_extensions` succeeded?
        # The manager handles it. We can check a flag on self if we want, or re-check.
        # Re-checking via manager method is safest.
        # However, the logic here previously called `_init_vss` which did loading.
        # We can just return mode as is, assuming availability, OR fall back if detection failed.
        # If `self._vss_function` is "vss_search" (default) we assume it's fine or handled by DuckDB error.
        # The original code had explicit fallback. Let's keep it simple:
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

        # Use cached or detected VSS functions preference
        # We simplified this to just try the one we have, then maybe fallback
        function_name = self._vss_function

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

        # If failed, maybe try fallback if error suggests it?
        # Original code iterated candidates. We can keep that if we want robustness.
        # But we are refactoring to use detection from manager.
        # So we trust manager's detection. If that fails, we fail to exact search or error.

        return self._handle_ann_failure(
            getattr(self, "_last_ann_error", None), where_clause, order_clause, params, min_similarity_threshold
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
            logger.error("Search failed: VSS query execution failed")
        return self._empty_table(SEARCH_RESULT_SCHEMA)

    def _build_ann_query(
        self, function_name: str, *, ann_limit: int, nprobe_clause: str, _embedding_dimensionality: int
    ) -> str:
        return f"\n            WITH candidates AS (\n                SELECT\n                    base.*,\n                    1 - vs.distance AS similarity\n                FROM {function_name}(\n                    '{TABLE_NAME}',\n                    'embedding',\n                    ?::FLOAT[{EMBEDDING_DIM}],\n                    top_k := {ann_limit},\n                    metric := 'cosine'{nprobe_clause}\n                ) AS vs\n                JOIN {TABLE_NAME} AS base\n                  ON vs.rowid = base.rowid\n            )\n            SELECT * FROM candidates\n        "

    def _execute_search_query(self, query: str, params: list[Any], min_similarity_threshold: float) -> Table:
        """Execute the provided search query and normalize the results."""
        with self.backend.connection() as conn:
            cursor = conn.execute(query, params)
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

        with self.backend.connection() as conn:
            conn.execute(f"CREATE TEMP TABLE {temp_name} ({columns_sql})")
            column_names = list(schema.names)
            placeholders = ", ".join("?" for _ in column_names)
            values = [tuple(record.get(name) for name in column_names) for record in records]
            if values:
                conn.executemany(
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

            with self.backend.connection() as conn:
                result = conn.execute(
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


__all__ = [
    "DatasetMetadata",
    "VectorStore",
]
