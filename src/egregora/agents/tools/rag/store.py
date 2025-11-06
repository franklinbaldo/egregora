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
from ibis.expr.types import Table

from egregora.config import EMBEDDING_DIM
from egregora.database import schema as database_schema

logger = logging.getLogger(__name__)


TABLE_NAME = "rag_chunks"
INDEX_NAME = "rag_chunks_embedding_idx"
METADATA_TABLE_NAME = "rag_chunks_metadata"
DEFAULT_ANN_OVERFETCH = 5
INDEX_META_TABLE = "index_meta"
DEFAULT_EXACT_INDEX_THRESHOLD = 1_000


class _ConnectionProxy:
    """Allow attribute overrides on DuckDB connections (e.g., for monkeypatching)."""

    def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_overrides", {})

    def __getattr__(self, name: str) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_inner"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_inner", "_overrides"}:
            object.__setattr__(self, name, value)
            return
        overrides = object.__getattribute__(self, "_overrides")
        overrides[name] = value

    def __delattr__(self, name: str) -> None:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            del overrides[name]
            return
        delattr(object.__getattribute__(self, "_inner"), name)


# Use schemas from centralized database_schema module
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
    """
    Vector store backed by Parquet file.

    Uses DuckDB VSS extension for similarity search.
    Data lives in Parquet for portability and client-side access.
    """

    def __init__(
        self,
        parquet_path: Path,
        *,
        connection: duckdb.DuckDBPyConnection | None = None,
        exact_index_threshold: int = DEFAULT_EXACT_INDEX_THRESHOLD,
    ) -> None:
        """Initialize vector store.

        Args:
            parquet_path: Path to Parquet file (e.g., output/rag/chunks.parquet)
            exact_index_threshold: Maximum row count before switching to ANN indexing

        """
        self.parquet_path = parquet_path
        self.index_path = parquet_path.with_suffix(".duckdb")
        self._owns_connection = connection is None
        if self._owns_connection:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = _ConnectionProxy(duckdb.connect(str(self.index_path)))
        else:
            self.conn = _ConnectionProxy(connection)

        # Lazy loading: VSS is only initialized when needed (ANN mode)
        self._vss_available = False
        self._vss_function = "vss_search"  # Default function name
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

        try:
            self.conn.execute("INSTALL vss")
            self.conn.execute("LOAD vss")
            self._vss_available = True
            self._vss_function = self._detect_vss_function()
            logger.info("DuckDB VSS extension loaded")
            return True
        except Exception as e:
            logger.warning(f"VSS extension unavailable, falling back to exact search: {e}")
            self._vss_available = False
            return False

    def _ensure_dataset_loaded(self, force: bool = False) -> None:
        """Materialize the Parquet dataset into DuckDB and refresh the ANN index."""
        self._ensure_metadata_table()

        if not self.parquet_path.exists():
            self.conn.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
            self.conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
            self._store_metadata(None)
            self._table_synced = True
            return

        stored_metadata = self._get_stored_metadata()
        current_metadata = self._read_parquet_metadata()

        table_exists = self._duckdb_table_exists(TABLE_NAME)
        metadata_changed = stored_metadata != current_metadata

        if not force and not metadata_changed and table_exists:
            self._table_synced = True
            return

        self.conn.execute(
            f"CREATE OR REPLACE TABLE {TABLE_NAME} AS SELECT * FROM read_parquet(?)",
            [str(self.parquet_path)],
        )
        self._store_metadata(current_metadata)

        if force or metadata_changed or not table_exists:
            self._rebuild_index()

        self._table_synced = True

    def _ensure_metadata_table(self) -> None:
        """Create the internal metadata table when missing."""
        database_schema.create_table_if_not_exists(
            self._client,
            METADATA_TABLE_NAME,
            database_schema.RAG_CHUNKS_METADATA_SCHEMA,
        )
        database_schema.add_primary_key(self.conn, METADATA_TABLE_NAME, "path")

    def _ensure_index_meta_table(self) -> None:
        """Create the table used to persist ANN index metadata."""
        database_schema.create_table_if_not_exists(
            self._client,
            INDEX_META_TABLE,
            database_schema.RAG_INDEX_META_SCHEMA,
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
        # Preserve the functionality of the target branch but with the ruff fix
        # Reduce return statements for ruff compliance
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

        return DatasetMetadata(
            mtime_ns=int(mtime_ns),
            size=int(size),
            row_count=int(row_count),
        )

    def _store_metadata(self, metadata: DatasetMetadata | None) -> None:
        """Persist or remove cached metadata for the backing Parquet file."""
        self.conn.execute(
            f"DELETE FROM {METADATA_TABLE_NAME} WHERE path = ?",
            [str(self.parquet_path)],
        )

        if metadata is None:
            return

        self.conn.execute(
            (f"INSERT INTO {METADATA_TABLE_NAME} (path, mtime_ns, size, row_count) VALUES (?, ?, ?, ?)"),
            [
                str(self.parquet_path),
                metadata.mtime_ns,
                metadata.size,
                metadata.row_count,
            ],
        )

    def _read_parquet_metadata(self) -> DatasetMetadata:
        """Inspect the Parquet file for structural metadata."""
        stats = self.parquet_path.stat()
        row = self.conn.execute(
            "SELECT COUNT(*) FROM read_parquet(?)",
            [str(self.parquet_path)],
        ).fetchone()
        row_count = int(row[0]) if row and row[0] is not None else 0
        return DatasetMetadata(
            mtime_ns=int(stats.st_mtime_ns),
            size=int(stats.st_size),
            row_count=int(row_count),
        )

    def _duckdb_table_exists(self, table_name: str) -> bool:
        """Check whether a DuckDB table is materialized in the current database."""
        row = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE lower(table_name) = lower(?)
        """,
            [table_name],
        ).fetchone()
        return bool(row and row[0] > 0)

    def _rebuild_index(self) -> None:
        """Recreate the VSS index for the materialized chunks table."""
        self.conn.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
        self._ensure_index_meta_table()
        table_present = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE lower(table_name) = lower(?)
        """,
            [TABLE_NAME],
        ).fetchone()
        if not table_present or table_present[0] == 0:
            self._clear_index_meta()
            return

        row = self.conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()
        if not row or row[0] == 0:
            self._clear_index_meta()
            return

        # Only attempt to create VSS index if extension is available
        if not self._init_vss():
            logger.info("VSS not available, skipping index creation")
            self._clear_index_meta()
            return

        # Use HNSW index for better performance with fixed-dimension vectors
        try:
            self.conn.execute(
                f"""
                CREATE INDEX {INDEX_NAME}
                ON {TABLE_NAME}
                USING HNSW (embedding)
                WITH (metric = 'cosine')
                """
            )
            logger.info("Created HNSW index on embedding column")
        except duckdb.Error as exc:  # pragma: no cover - depends on extension availability
            logger.warning("Skipping HNSW index creation: %s", exc)

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
        timestamp = datetime.now()
        self.conn.execute(
            f"""
            INSERT INTO {INDEX_META_TABLE} (
                index_name,
                mode,
                row_count,
                threshold,
                nlist,
                embedding_dim,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(index_name) DO UPDATE SET
                mode=excluded.mode,
                row_count=excluded.row_count,
                threshold=excluded.threshold,
                nlist=excluded.nlist,
                embedding_dim=excluded.embedding_dim,
                updated_at=excluded.updated_at
            """,
            [INDEX_NAME, mode, row_count, threshold, nlist, embedding_dim, timestamp, timestamp],
        )

    def _clear_index_meta(self) -> None:
        """Remove metadata when the backing table is empty or missing."""
        self.conn.execute(
            f"DELETE FROM {INDEX_META_TABLE} WHERE index_name = ?",
            [INDEX_NAME],
        )

    def _get_stored_embedding_dim(self) -> int | None:
        """Fetch the stored embedding dimensionality from index metadata."""
        row = self.conn.execute(
            f"SELECT embedding_dim FROM {INDEX_META_TABLE} WHERE index_name = ?",
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

        # Check that all embeddings are 768 dimensions
        dimensions = {len(emb) for emb in embeddings}
        if len(dimensions) > 1:
            msg = f"{context}: Inconsistent embedding dimensions within batch: {sorted(dimensions)}"
            raise ValueError(msg)

        current_dim = dimensions.pop()

        # All embeddings must be exactly 768 dimensions
        if current_dim != EMBEDDING_DIM:
            msg = (
                f"{context}: Embedding dimension mismatch. "
                f"Expected {EMBEDDING_DIM} (fixed dimension), got {current_dim}. "
                f"All embeddings must use 768 dimensions."
            )
            raise ValueError(msg)
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

        # Validate embedding dimensionality
        chunks_df = chunks_table.execute()
        if len(chunks_df) > 0 and "embedding" in chunks_df.columns:
            embeddings = chunks_df["embedding"].tolist()
            embedding_dim = self._validate_embedding_dimension(embeddings, "New chunks")
            logger.info(f"Validated embedding dimension: {embedding_dim}")
        else:
            embedding_dim = None

        if self.parquet_path.exists():
            # Read existing and append
            existing_table = self._client.read_parquet(self.parquet_path)
            self._validate_table_schema(existing_table, context="existing vector store")
            existing_table, chunks_table = self._align_schemas(existing_table, chunks_table)
            combined_table = existing_table.union(chunks_table, distinct=False)
            existing_count = existing_table.count().execute()
            new_count = chunks_table.count().execute()
            logger.info(f"Appending {new_count} chunks to existing {existing_count} chunks")
        else:
            combined_table = self._cast_to_vector_store_schema(chunks_table)
            chunk_count = chunks_table.count().execute()
            logger.info(f"Creating new vector store with {chunk_count} chunks")

        # Write to Parquet using DuckDB COPY to avoid Arrow round-trips
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

        # Persist embedding dimension in metadata
        if embedding_dim is not None:
            row_count = combined_table.count().execute()
            self._upsert_index_meta(
                mode="unknown",  # Will be updated when index is rebuilt
                row_count=row_count,
                threshold=0,
                nlist=None,
                embedding_dim=embedding_dim,
            )

        logger.info(f"Vector store saved to {self.parquet_path}")

    def _align_schemas(self, existing_table: Table, new_table: Table) -> tuple[Table, Table]:
        """Cast both tables to the canonical vector store schema."""
        existing_table = self._cast_to_vector_store_schema(existing_table)
        new_table = self._cast_to_vector_store_schema(new_table)

        return existing_table, new_table

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

    def search(  # noqa: PLR0911, PLR0913, PLR0915
        self,
        query_vec: list[float],
        top_k: int = 5,
        min_similarity: float = 0.7,
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
            min_similarity: Minimum cosine similarity (0-1)
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
        if not self.parquet_path.exists():
            logger.warning("Vector store does not exist yet")
            return self._empty_table(SEARCH_RESULT_SCHEMA)

        self._ensure_dataset_loaded()

        table_present = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE lower(table_name) = lower(?)
        """,
            [TABLE_NAME],
        ).fetchone()

        if not table_present or table_present[0] == 0:
            return self._empty_table(SEARCH_RESULT_SCHEMA)

        # All embeddings must be fixed 768 dimensions
        embedding_dimensionality = len(query_vec)
        if embedding_dimensionality != EMBEDDING_DIM:
            msg = (
                f"Query embedding dimension mismatch. "
                f"Expected {EMBEDDING_DIM} (fixed dimension), got {embedding_dimensionality}. "
                f"All embeddings must use 768 dimensions."
            )
            raise ValueError(msg)
            raise ValueError(msg)

        mode_normalized = mode.lower()
        if mode_normalized not in {"ann", "exact"}:
            msg = "mode must be either 'ann' or 'exact'"
            raise ValueError(msg)

        # Fallback to exact mode if ANN requested but VSS not available
        if mode_normalized == "ann" and not self._init_vss():
            logger.info("ANN mode requested but VSS unavailable, using exact search")
            mode_normalized = "exact"

        if nprobe is not None and nprobe <= 0:
            msg = "nprobe must be a positive integer"
            raise ValueError(msg)

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
        params.append(min_similarity)

        where_clause = ""
        if filters:
            where_clause = " WHERE " + " AND ".join(filters)

        order_clause = f"\n            ORDER BY similarity DESC\n            LIMIT {top_k}\n        "

        # Use fixed 768-dimension arrays for HNSW optimization
        exact_base_query = f"""
            WITH candidates AS (
                SELECT
                    * EXCLUDE (embedding),
                    array_cosine_similarity(
                        embedding::FLOAT[{EMBEDDING_DIM}],
                        ?::FLOAT[{EMBEDDING_DIM}]
                    ) AS similarity
                FROM {TABLE_NAME}
            )
            SELECT * FROM candidates
        """

        if mode_normalized == "exact":
            query = exact_base_query + where_clause + order_clause
            try:
                return self._execute_search_query(query, params, min_similarity)
            except Exception as exc:  # pragma: no cover - unexpected execution failure
                logger.exception(f"Search failed: {exc}")
                return self._empty_table(SEARCH_RESULT_SCHEMA)

        fetch_factor = overfetch if overfetch and overfetch > 1 else DEFAULT_ANN_OVERFETCH
        ann_limit = max(top_k * fetch_factor, top_k + 10)
        nprobe_clause = f", nprobe := {int(nprobe)}" if nprobe else ""

        last_error: Exception | None = None
        for function_name in self._candidate_vss_functions():
            base_query = self._build_ann_query(
                function_name,
                ann_limit=ann_limit,
                nprobe_clause=nprobe_clause,
                embedding_dimensionality=embedding_dimensionality,
            )
            query = base_query + where_clause + order_clause

            try:
                result = self._execute_search_query(query, params, min_similarity)
                self._vss_function = function_name
                return result
            except duckdb.Error as exc:
                last_error = exc
                logger.warning("ANN search failed with %s: %s", function_name, exc)
                continue
            except Exception as exc:  # pragma: no cover - unexpected execution failure
                last_error = exc
                logger.exception("ANN search aborted: %s", exc)
                break

        if last_error is not None and "does not support the supplied arguments" in str(last_error).lower():
            logger.info("Falling back to exact search due to VSS compatibility issues")
            try:
                return self._execute_search_query(
                    exact_base_query + where_clause + order_clause,
                    params,
                    min_similarity,
                )
            except Exception as exc:  # pragma: no cover - unexpected execution failure
                logger.exception("Exact fallback search failed: %s", exc)

        if last_error is not None:
            logger.error("Search failed: %s", last_error)
        else:
            logger.error("Search failed: no compatible VSS table function available")
        return self._empty_table(SEARCH_RESULT_SCHEMA)

    def _build_ann_query(
        self,
        function_name: str,
        *,
        ann_limit: int,
        nprobe_clause: str,
        embedding_dimensionality: int,
    ) -> str:
        # Use fixed 768-dimension arrays for HNSW optimization (ignore embedding_dimensionality param)
        return f"""
            WITH candidates AS (
                SELECT
                    base.*,
                    1 - vs.distance AS similarity
                FROM {function_name}(
                    '{TABLE_NAME}',
                    'embedding',
                    ?::FLOAT[{EMBEDDING_DIM}],
                    top_k := {ann_limit},
                    metric := 'cosine'{nprobe_clause}
                ) AS vs
                JOIN {TABLE_NAME} AS base
                  ON vs.rowid = base.rowid
            )
            SELECT * FROM candidates
        """

    def _detect_vss_function(self) -> str:
        """Return the appropriate DuckDB VSS function name."""
        try:
            rows = self.conn.execute("SELECT name FROM pragma_table_functions()").fetchall()
        except duckdb.Error as exc:  # pragma: no cover - DuckDB compatibility
            logger.debug("Unable to inspect table functions: %s", exc)
            return "vss_search"

        function_names = {str(row[0]).lower() for row in rows if row}

        if "vss_search" in function_names:
            return "vss_search"
        if "vss_match" in function_names:
            logger.debug("Using vss_match table function for ANN queries")
            return "vss_match"

        logger.debug("No VSS table function detected; defaulting to vss_search")
        return "vss_search"

    def _candidate_vss_functions(self) -> list[str]:
        """Return preferred VSS table functions in fallback order."""
        candidates = [self._vss_function]
        for function_name in ("vss_match", "vss_search"):
            if function_name not in candidates:
                candidates.append(function_name)
        return candidates

    def _execute_search_query(self, query: str, params: list[Any], min_similarity: float) -> Table:
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
        logger.info("Found %d similar chunks (min_similarity=%s)", row_count, min_similarity)

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
                except ValueError as exc:  # pragma: no cover - defensive guard
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
        except (AttributeError, RuntimeError) as e:  # pragma: no cover - defensive against Ibis internals
            # _find_backend() is an internal Ibis method that may fail or not exist
            logger.debug("Could not determine table backend: %s", e)
            backend = None

        if backend is self._client:
            return table

        source_schema = table.schema()
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

    def close(self) -> None:
        """Close the DuckDB connection if owned by this store."""
        if self._owns_connection:
            self.conn.close()

    def get_all(self) -> Table:
        """Read entire vector store.

        Useful for analytics, exports, client-side usage.
        """
        if not self.parquet_path.exists():
            return self._empty_table(VECTOR_STORE_SCHEMA)

        return self._client.read_parquet(self.parquet_path)

    def stats(self) -> dict[str, Any]:
        """Get vector store statistics."""
        if not self.parquet_path.exists():
            return {
                "total_chunks": 0,
                "total_posts": 0,
                "total_media": 0,
                "media_by_type": {},
            }

        table = self.get_all()
        total_chunks = table.count().execute()

        if total_chunks == 0:
            return {
                "total_chunks": 0,
                "total_posts": 0,
                "date_range": (None, None),
                "total_tags": 0,
            }

        # Check if document_type column exists (for backward compatibility)
        df_executed = table.execute()
        has_doc_type = "document_type" in df_executed.columns

        stats = {
            "total_chunks": total_chunks,
        }

        if has_doc_type:
            # New schema with document types
            post_table = table.filter(table.document_type == "post")
            media_table = table.filter(table.document_type == "media")

            post_count = post_table.count().execute()
            media_count = media_table.count().execute()

            stats["total_posts"] = post_table.post_slug.nunique().execute() if post_count > 0 else 0
            stats["total_media"] = media_table.media_uuid.nunique().execute() if media_count > 0 else 0

            # Media breakdown by type
            if media_count > 0:
                media_types_agg = (
                    media_table.group_by("media_type")
                    .aggregate(count=lambda t: t.media_uuid.nunique())
                    .execute()
                )
                stats["media_by_type"] = {
                    row["media_type"]: row["count"]
                    for _, row in media_types_agg.iterrows()
                    if row["media_type"]
                }
            else:
                stats["media_by_type"] = {}

            # Date ranges
            if post_count > 0:
                stats["post_date_range"] = (
                    post_table.post_date.min().execute(),
                    post_table.post_date.max().execute(),
                )
            if media_count > 0:
                stats["media_date_range"] = (
                    media_table.message_date.min().execute(),
                    media_table.message_date.max().execute(),
                )

        else:
            # Old schema - all posts
            stats["total_posts"] = table.post_slug.nunique().execute()
            stats["total_media"] = 0
            stats["media_by_type"] = {}
            stats["date_range"] = (
                table.post_date.min().execute(),
                table.post_date.max().execute(),
            )
            stats["total_tags"] = table.tags.unnest().nunique().execute()

        return stats
