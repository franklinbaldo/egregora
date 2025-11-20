"""Vector store using DuckDB VSS and Parquet."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import duckdb
import ibis
import ibis.expr.datatypes as dt
from ibis import IbisError
from ibis.expr.types import Table

from egregora.config import EMBEDDING_DIM
from egregora.database import ir_schema as database_schema
from egregora.database.duckdb_manager import DuckDBStorageManager

logger = logging.getLogger(__name__)
TABLE_NAME = "rag_chunks"
INDEX_NAME = "rag_chunks_embedding_idx"
METADATA_TABLE_NAME = "rag_chunks_metadata"
DEFAULT_ANN_OVERFETCH = 5
INDEX_META_TABLE = "index_meta"


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


VECTOR_STORE_SCHEMA = database_schema.RAG_CHUNKS_SCHEMA
SEARCH_RESULT_SCHEMA = database_schema.RAG_SEARCH_RESULT_SCHEMA


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
        """Initialize vector store.

        Args:
            parquet_path: Path to Parquet file (e.g., output/rag/chunks.parquet)
            storage: The central DuckDB storage manager.

        """
        self.parquet_path = parquet_path
        self.index_path = parquet_path.with_suffix(".duckdb")
        self.conn = _ConnectionProxy(storage.conn)
        self.backend = storage # Use storage directly as backend
        self._vss_available = False
        self._vss_function = "vss_search"
        self._client = ibis.duckdb.from_connection(self.conn)
        self._table_synced = False
        self._ensure_index_meta_table()
        self._ensure_dataset_loaded()

    def _init_vss(self) -> bool:
        """Initialize DuckDB VSS extension (lazy loading).

        Returns:
            True if VSS was successfully loaded, False otherwise.

        """
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
        # Use DuckDBStorageManager functionality or raw sql since method removed
        # But we can just do CREATE TABLE AS SELECT FROM read_parquet
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
            f"SELECT mtime_ns, size, row_count FROM {METADATA_TABLE_NAME} WHERE path = ?",  # nosec B608 - METADATA_TABLE_NAME is module constant
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
        self.conn.execute(f"DELETE FROM {METADATA_TABLE_NAME} WHERE path = ?", [str(self.parquet_path)])  # nosec B608 - METADATA_TABLE_NAME is module constant
        if metadata is None:
            return
        self.conn.execute(
            f"INSERT INTO {METADATA_TABLE_NAME} (path, mtime_ns, size, row_count) VALUES (?, ?, ?, ?)",  # nosec B608 - METADATA_TABLE_NAME is module constant
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
            f"\n            INSERT INTO {INDEX_META_TABLE} (\n                index_name,\n                mode,\n                row_count,\n                threshold,\n                nlist,\n                embedding_dim,\n                created_at,\n                updated_at\n            )\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n            ON CONFLICT(index_name) DO UPDATE SET\n                mode=excluded.mode,\n                row_count=excluded.row_count,\n                threshold=excluded.threshold,\n                nlist=excluded.nlist,\n                embedding_dim=excluded.embedding_dim,\n                updated_at=excluded.updated_at\n            ",  # nosec B608 - INDEX_META_TABLE is module constant
            [INDEX_NAME, mode, row_count, threshold, nlist, embedding_dim, timestamp, timestamp],
        )

    def _clear_index_meta(self) -> None:
        """Remove metadata when the backing table is empty or missing."""
        self.conn.execute(f"DELETE FROM {INDEX_META_TABLE} WHERE index_name = ?", [INDEX_NAME])  # nosec B608 - INDEX_META_TABLE is module constant

    def _get_stored_embedding_dim(self) -> int | None:
        """Fetch the stored embedding dimensionality from index metadata."""
        row = self.conn.execute(
            f"SELECT embedding_dim FROM {INDEX_META_TABLE} WHERE index_name = ?",  # nosec B608 - INDEX_META_TABLE is module constant
            [INDEX_NAME],
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def _validate_embedding_dimension(self, embeddings: list[list[float]], context: str) -> int:
        """Validate embedding dimensionality consistency.

        All embeddings must be exactly 768 dimensions.

        Args:
            embeddings: List of embedding vectors to validate
            context: Description of where these embeddings come from (for error messages)

        Returns:
            The embedding dimension (always 768)

        Raises:
            ValueError: If embeddings are not 768 dimensions

        """
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
        """Add chunks to the vector store.

        Appends to existing Parquet file or creates new one.

        Args:
            chunks_table: Ibis Table with columns:
                - chunk_id: str
                - document_type: str ("post" or "media")
                - document_id: str (post_slug or media_uuid)

                # Post-specific (optional)
                - post_slug: str | None
                - post_title: str | None
                - post_date: date | None

                # Media-specific (optional)
                - media_uuid: str | None
                - media_type: str | None ("image", "video", "audio", "document")
                - media_path: str | None (relative path to media file)
                - original_filename: str | None
                - message_date: datetime | None
                - author_uuid: str | None

                # Common fields
                - chunk_index: int
                - content: str
                - embedding: list[float] (exactly 768 dimensions)
                - tags: list[str]
                - category: str | None

        """
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
            # Migrate legacy schema: add missing columns with NULL defaults
            # ALPHA MINDSET: We do migrations even in alpha for smooth upgrades
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
                f"COPY (SELECT * FROM {view_name}) TO ? (FORMAT PARQUET)",  # nosec B608 - view_name is UUID-based temp identifier
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
        """Migrate legacy RAG schemas by adding missing columns with default values.

        ALPHA MINDSET: We do migrations even in alpha to ensure smooth upgrades.
        When the schema evolves (e.g., adding source_path/source_mtime_ns for
        incremental indexing), existing parquet files need migration.

        This method:
        1. Detects missing columns (expected in schema but not in table)
        2. Adds them with NULL defaults (all new columns must be nullable)
        3. Logs migration for transparency

        Args:
            table: Existing table from parquet file

        Returns:
            Table: Migrated table with all expected columns

        Raises:
            ValueError: If a missing column is NOT nullable (migration impossible)

        Example:
            # Existing file has no source_path/source_mtime_ns
            # After migration: source_path=NULL, source_mtime_ns=NULL for all rows

        """
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

        # Add missing columns with NULL defaults
        mutations = {}
        for column_name in missing:
            column_type = VECTOR_STORE_SCHEMA[column_name]

            # Verify column is nullable (required for migration)
            if not column_type.nullable:
                msg = (
                    f"Cannot migrate legacy schema: column '{column_name}' is NOT nullable. "
                    f"Migration requires all new columns to be nullable."
                )
                raise ValueError(msg)

            # Add column with NULL default
            # Use ibis.null() with explicit cast to ensure correct type
            mutations[column_name] = ibis.null().cast(column_type)

        # Apply mutations (add missing columns)
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
        """Search for similar chunks using cosine similarity.

        Args:
            query_vec: Query embedding vector
            top_k: Number of results to return
            min_similarity_threshold: Minimum cosine similarity (0-1)
            tag_filter: Filter by tags (OR logic)
            date_after: Filter by temporal boundary (``date``/``datetime``/ISO string)
            document_type: Filter by document type ("post" or "media")
            media_types: Filter by media type (e.g., ["image", "video"])
            mode: "ann" (VSS index) or "exact" (full scan)
            nprobe: Override the ANN search breadth (DuckDB VSS ``nprobe``)
            overfetch: Multiplier for ANN candidate pool before filtering

        Returns:
            Ibis Table with all stored columns plus similarity score

        """
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
        return f"\n            WITH candidates AS (\n                SELECT\n                    * EXCLUDE (embedding),\n                    array_cosine_similarity(\n                        embedding::FLOAT[{EMBEDDING_DIM}],\n                        ?::FLOAT[{EMBEDDING_DIM}]\n                    ) AS similarity\n                FROM {TABLE_NAME}\n            )\n            SELECT * FROM candidates\n        "  # nosec B608 - TABLE_NAME and EMBEDDING_DIM are module constants

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
        return f"\n            WITH candidates AS (\n                SELECT\n                    base.*,\n                    1 - vs.distance AS similarity\n                FROM {function_name}(\n                    '{TABLE_NAME}',\n                    'embedding',\n                    ?::FLOAT[{EMBEDDING_DIM}],\n                    top_k := {ann_limit},\n                    metric := 'cosine'{nprobe_clause}\n                ) AS vs\n                JOIN {TABLE_NAME} AS base\n                  ON vs.rowid = base.rowid\n            )\n            SELECT * FROM candidates\n        "  # nosec B608 - function_name is validated VSS function, TABLE_NAME/EMBEDDING_DIM are module constants

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
            return datetime.combine(value, time.min, tzinfo=UTC)
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
                return datetime.combine(parsed_date, time.min, tzinfo=UTC)
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
        self.conn.execute(f"CREATE TEMP TABLE {temp_name} ({columns_sql})")  # nosec B608 - temp_name is UUID-based temp identifier
        column_names = list(schema.names)
        placeholders = ", ".join("?" for _ in column_names)
        values = [tuple(record.get(name) for name in column_names) for record in records]
        if values:
            self.conn.executemany(
                f"INSERT INTO {temp_name} ({', '.join(column_names)}) VALUES ({placeholders})",  # nosec B608 - temp_name is UUID-based temp identifier
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
        """Get indexed source files with their modification times.

        Returns a mapping of absolute file paths to mtime (nanoseconds).
        This enables incremental indexing by comparing filesystem state
        with RAG metadata to identify new/changed files.

        Industry standard: Content-addressed storage with change detection
        (similar to Git, Docker layers, Make, rsync).

        Returns:
            dict[str, int]: Mapping of source_path -> source_mtime_ns
                Empty dict if no sources indexed or parquet doesn't exist

        Example:
            >>> store = VectorStore(rag_dir / "chunks.parquet")
            >>> indexed = store.get_indexed_sources()
            >>> {
            ...     "/path/to/post1.md": 1704067200000000000,
            ...     "/path/to/post2.md": 1704070800000000000,
            ... }

        """
        if not self.parquet_path.exists():
            return {}

        try:
            self._ensure_dataset_loaded()

            # Query distinct source files with their mtimes
            # Filter out rows without source_path (old data or media chunks)
            result = self.conn.execute(
                f"""
                SELECT DISTINCT source_path, source_mtime_ns
                FROM {TABLE_NAME}
                WHERE source_path IS NOT NULL
                """  # nosec B608 - TABLE_NAME is module constant
            ).fetchall()

            return {str(path): int(mtime) for path, mtime in result if path and mtime is not None}

        except (duckdb.Error, IbisError) as e:
            logger.warning("Failed to get indexed sources: %s", e)
            return {}

    def get_indexed_sources_table(self) -> Table:
        """Get indexed source files as an Ibis table for efficient delta detection.

        Returns Ibis table with columns:
            - source_path: string (absolute filesystem path)
            - source_mtime_ns: int64 (modification time in nanoseconds)

        This enables efficient Ibis joins/filters for incremental indexing.

        Returns:
            Ibis table with indexed sources
                Empty table with correct schema if no sources indexed

        Example:
            >>> store = VectorStore(rag_dir / "chunks.parquet")
            >>> indexed = store.get_indexed_sources_table()
            >>> indexed.head(2).execute()
               source_path                          source_mtime_ns
            0  /path/to/post1.md                    1704067200000000000
            1  /path/to/post2.md                    1704070800000000000

        """
        if not self.parquet_path.exists():
            # Return empty table with correct schema
            return ibis.memtable(
                [], schema=ibis.schema({"source_path": "string", "source_mtime_ns": "int64"})
            )

        try:
            self._ensure_dataset_loaded()

            # Query distinct source files with their mtimes as Ibis table
            # Filter out rows without source_path (old data or media chunks)
            table = self._client.table(TABLE_NAME)
            return (
                table.filter(table.source_path.notnull()).select("source_path", "source_mtime_ns").distinct()
            )
        except (duckdb.Error, IbisError) as e:
            logger.warning("Failed to get indexed sources table: %s", e)
            # Return empty table with correct schema
            return ibis.memtable(
                [], schema=ibis.schema({"source_path": "string", "source_mtime_ns": "int64"})
            )
