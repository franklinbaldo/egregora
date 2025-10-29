"""Vector store using DuckDB VSS and Parquet."""

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import duckdb
import ibis
import ibis.expr.datatypes as dt
import pyarrow as pa
import pyarrow.parquet as pq
from ibis.expr.types import Table

logger = logging.getLogger(__name__)


TABLE_NAME = "rag_chunks"
INDEX_NAME = "rag_chunks_embedding_idx"
METADATA_TABLE_NAME = "rag_chunks_metadata"
DEFAULT_ANN_OVERFETCH = 5
INDEX_META_TABLE = "index_meta"
DEFAULT_EXACT_INDEX_THRESHOLD = 1_000


class _ConnectionProxy:
    """Allow attribute overrides on DuckDB connections (e.g., for monkeypatching)."""

    def __init__(self, inner: duckdb.DuckDBPyConnection):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_overrides", {})

    def __getattr__(self, name: str):  # noqa: D401 - simple forwarder
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

VECTOR_STORE_SCHEMA = ibis.schema(
    {
        "chunk_id": dt.string,
        "document_type": dt.string,
        "document_id": dt.string,
        "post_slug": dt.String(nullable=True),
        "post_title": dt.String(nullable=True),
        "post_date": dt.date(nullable=True),
        "media_uuid": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        "media_path": dt.String(nullable=True),
        "original_filename": dt.String(nullable=True),
        "message_date": dt.Timestamp(timezone="UTC", nullable=True),
        "author_uuid": dt.String(nullable=True),
        "chunk_index": dt.int64,
        "content": dt.string,
        "embedding": dt.Array(dt.float64),
        "tags": dt.Array(dt.string),
        "authors": dt.Array(dt.string),
        "category": dt.String(nullable=True),
    }
)


SEARCH_RESULT_SCHEMA = ibis.schema(
    {
        "chunk_id": dt.string,
        "document_type": dt.string,
        "document_id": dt.string,
        "post_slug": dt.String(nullable=True),
        "post_title": dt.String(nullable=True),
        "post_date": dt.date(nullable=True),
        "media_uuid": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        "media_path": dt.String(nullable=True),
        "original_filename": dt.String(nullable=True),
        "message_date": dt.Timestamp(timezone="UTC", nullable=True),
        "author_uuid": dt.String(nullable=True),
        "chunk_index": dt.int64,
        "content": dt.string,
        "tags": dt.Array(dt.string),
        "authors": dt.Array(dt.string),
        "category": dt.String(nullable=True),
        "similarity": dt.float64,
    }
)


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
        connection: duckdb.DuckDBPyConnection | None = None,
        exact_index_threshold: int = DEFAULT_EXACT_INDEX_THRESHOLD,
    ):
        """
        Initialize vector store.

        Args:
            parquet_path: Path to Parquet file (e.g., output/rag/chunks.parquet)
            exact_index_threshold: Maximum row count before switching to ANN indexing
        """
        self.parquet_path = parquet_path
        self.index_path = parquet_path.with_suffix(".duckdb")
        self._owns_connection = connection is None
        if self._owns_connection:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = duckdb.connect(str(self.index_path))
        else:
            self.conn = connection
        self.conn = _ConnectionProxy(self.conn)
        self._init_vss()
        self._client = ibis.duckdb.from_connection(self.conn)
        self._table_synced = False
        self._ensure_index_meta_table()
        self._ensure_dataset_loaded()

    def _init_vss(self):
        """Initialize DuckDB VSS extension."""
        try:
            self.conn.execute("INSTALL vss")
            self.conn.execute("LOAD vss")
            logger.info("DuckDB VSS extension loaded")
        except Exception as e:
            logger.error(f"Failed to load VSS extension: {e}")
            raise

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

        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {METADATA_TABLE_NAME} (
                path TEXT PRIMARY KEY,
                mtime_ns BIGINT,
                size BIGINT,
                row_count BIGINT
            )
            """
        )

    def _get_stored_metadata(self) -> DatasetMetadata | None:
        """Fetch cached metadata for the backing Parquet file."""

        row = self.conn.execute(
            f"SELECT mtime_ns, size, row_count FROM {METADATA_TABLE_NAME} WHERE path = ?",
            [str(self.parquet_path)],
        ).fetchone()
        if not row:
            return None

        return DatasetMetadata(mtime_ns=int(row[0]), size=int(row[1]), row_count=int(row[2]))

    def _store_metadata(self, metadata: DatasetMetadata | None) -> None:
        """Persist or remove cached metadata for the backing Parquet file."""

        self.conn.execute(
            f"DELETE FROM {METADATA_TABLE_NAME} WHERE path = ?",
            [str(self.parquet_path)],
        )

        if metadata is None:
            return

        self.conn.execute(
            f"INSERT INTO {METADATA_TABLE_NAME} (path, mtime_ns, size, row_count) VALUES (?, ?, ?, ?)",
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
        metadata = pq.read_metadata(self.parquet_path)
        return DatasetMetadata(
            mtime_ns=int(stats.st_mtime_ns),
            size=int(stats.st_size),
            row_count=int(metadata.num_rows),
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

        try:
            self.conn.execute(
                f"""
                CREATE INDEX {INDEX_NAME}
                ON {TABLE_NAME}(embedding)
                USING vss(metric='cosine', storage_type='ivfflat')
                """
            )
        except duckdb.Error as exc:  # pragma: no cover - depends on extension availability
            logger.warning("Skipping VSS index rebuild: %s", exc)

    def _upsert_index_meta(
        self,
        *,
        mode: str,
        row_count: int,
        threshold: int,
        nlist: int | None,
    ) -> None:
        """Persist the latest index configuration for observability and telemetry."""

        timestamp = datetime.now()
        self.conn.execute(
            f"""
            INSERT INTO {INDEX_META_TABLE} (index_name, mode, row_count, threshold, nlist, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(index_name) DO UPDATE SET
                mode=excluded.mode,
                row_count=excluded.row_count,
                threshold=excluded.threshold,
                nlist=excluded.nlist,
                updated_at=excluded.updated_at
            """,
            [INDEX_NAME, mode, row_count, threshold, nlist, timestamp],
        )

    def _clear_index_meta(self) -> None:
        """Remove metadata when the backing table is empty or missing."""

        self.conn.execute(
            f"DELETE FROM {INDEX_META_TABLE} WHERE index_name = ?",
            [INDEX_NAME],
        )

    def add(self, chunks_df: Table):
        """
        Add chunks to the vector store.

        Appends to existing Parquet file or creates new one.

        Args:
            chunks_df: Ibis Table with columns:
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
                - embedding: list[float] (configured dimensionality)
                - tags: list[str]
                - category: str | None
        """
        self._validate_table_schema(chunks_df, context="new chunks")

        chunks_df = self._ensure_local_table(chunks_df)

        if self.parquet_path.exists():
            # Read existing and append
            existing_df = self._client.read_parquet(self.parquet_path)
            self._validate_table_schema(existing_df, context="existing vector store")
            existing_df, chunks_df = self._align_schemas(existing_df, chunks_df)
            combined_df = existing_df.union(chunks_df, distinct=False)
            existing_count = existing_df.count().execute()
            new_count = chunks_df.count().execute()
            logger.info(f"Appending {new_count} chunks to existing {existing_count} chunks")
        else:
            combined_df = self._cast_to_vector_store_schema(chunks_df)
            chunk_count = chunks_df.count().execute()
            logger.info(f"Creating new vector store with {chunk_count} chunks")

        # Write to Parquet
        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        combined_df.execute().to_parquet(self.parquet_path)

        self._table_synced = False
        self._ensure_dataset_loaded(force=True)

        logger.info(f"Vector store saved to {self.parquet_path}")

    def _align_schemas(self, existing_df: Table, new_df: Table) -> tuple[Table, Table]:
        """Cast both tables to the canonical vector store schema."""

        existing_df = self._cast_to_vector_store_schema(existing_df)
        new_df = self._cast_to_vector_store_schema(new_df)

        return existing_df, new_df

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
            raise ValueError(
                f"{context} do not match the vector store schema ({detail})."
            )

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
        """
        Search for similar chunks using cosine similarity.

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

        embedding_dimensionality = len(query_vec)
        if embedding_dimensionality == 0:
            raise ValueError("Query embedding vector must not be empty")

        mode_normalized = mode.lower()
        if mode_normalized not in {"ann", "exact"}:
            raise ValueError("mode must be either 'ann' or 'exact'")

        if nprobe is not None and nprobe <= 0:
            raise ValueError("nprobe must be a positive integer")

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
            filters.append(
                "coalesce(CAST(post_date AS TIMESTAMPTZ), message_date) > ?::TIMESTAMPTZ"
            )
            params.append(normalized_date.isoformat())

        filters.append("similarity >= ?")
        params.append(min_similarity)

        where_clause = ""
        if filters:
            where_clause = " WHERE " + " AND ".join(filters)

        if mode_normalized == "exact":
            base_query = f"""
                WITH candidates AS (
                    SELECT
                        * EXCLUDE (embedding),
                        array_cosine_similarity(
                            embedding::FLOAT[{embedding_dimensionality}],
                            ?::FLOAT[{embedding_dimensionality}]
                        ) AS similarity
                    FROM {TABLE_NAME}
                )
                SELECT * FROM candidates
            """
        else:
            fetch_factor = overfetch if overfetch and overfetch > 1 else DEFAULT_ANN_OVERFETCH
            ann_limit = max(top_k * fetch_factor, top_k + 10)
            nprobe_clause = f", nprobe := {int(nprobe)}" if nprobe else ""
            base_query = f"""
                WITH candidates AS (
                    SELECT
                        base.*,
                        1 - vs.distance AS similarity
                    FROM vss_search(
                        '{TABLE_NAME}',
                        'embedding',
                        ?::FLOAT[{embedding_dimensionality}],
                        top_k := {ann_limit},
                        metric := 'cosine'{nprobe_clause}
                    ) AS vs
                    JOIN {TABLE_NAME} AS base
                      ON vs.rowid = base.rowid
                )
                SELECT * FROM candidates
            """

        query = (
            base_query
            + where_clause
            + f"\n            ORDER BY similarity DESC\n            LIMIT {top_k}\n        "
        )

        try:
            result_table = self.conn.execute(query, params).arrow()
            if result_table.num_rows == 0:
                return self._empty_table(SEARCH_RESULT_SCHEMA)

            prepared_table = self._prepare_search_results(result_table)
            df = self._table_from_arrow(prepared_table, SEARCH_RESULT_SCHEMA)

            row_count = df.count().execute()
            logger.info(f"Found {row_count} similar chunks (min_similarity={min_similarity})")

            return df

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return self._empty_table(SEARCH_RESULT_SCHEMA)

    def _prepare_search_results(self, result_table: pa.Table) -> pa.Table:
        """Normalize DuckDB arrow results to match the search schema."""

        data = result_table.to_pydict()
        row_count = result_table.num_rows

        valid_columns = set(SEARCH_RESULT_SCHEMA.names) | {"similarity"}
        for key in list(data.keys()):
            if key not in valid_columns:
                data.pop(key)

        if "document_type" in data:
            data["document_type"] = [value or "post" for value in data["document_type"]]
        else:
            data["document_type"] = ["post"] * row_count

        chunk_ids = data.get("chunk_id", [""] * row_count)
        post_slugs = data.get("post_slug", [None] * row_count)
        if "document_id" in data:
            document_ids = []
            for index, existing in enumerate(data["document_id"]):
                slug = post_slugs[index] if index < len(post_slugs) else None
                chunk_id = chunk_ids[index] if index < len(chunk_ids) else ""
                document_ids.append(existing or slug or chunk_id)
            data["document_id"] = document_ids
        else:
            document_ids = []
            for index in range(row_count):
                slug = post_slugs[index] if index < len(post_slugs) else None
                chunk_id = chunk_ids[index] if index < len(chunk_ids) else ""
                document_ids.append(slug or chunk_id)
            data["document_id"] = document_ids

        array_columns = ("tags", "authors")
        for column_name in array_columns:
            if column_name not in data:
                data[column_name] = [[] for _ in range(row_count)]
            else:
                data[column_name] = [value or [] for value in data[column_name]]

        optional_defaults: dict[str, list[Any]] = {}
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
            if column_name not in data:
                optional_defaults[column_name] = [None] * row_count

        if optional_defaults:
            data.update(optional_defaults)

        if "chunk_index" not in data:
            data["chunk_index"] = list(range(row_count))

        schema = SEARCH_RESULT_SCHEMA.to_pyarrow()
        arrays = []
        for field in schema:
            values = data.get(field.name)
            if values is None:
                values = [None] * row_count
            arrays.append(pa.array(values, type=field.type))

        return pa.Table.from_arrays(arrays, schema=schema)

    @staticmethod
    def _normalize_date_filter(value: date | datetime | str) -> datetime:
        """Normalize date filter inputs to UTC-aware datetimes."""

        if isinstance(value, datetime):
            return VectorStore._ensure_utc_datetime(value)

        if isinstance(value, date):
            return datetime.combine(value, time.min, tzinfo=timezone.utc)

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
                    raise ValueError(f"Invalid date_after value: {value!r}") from exc
                return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)

            return VectorStore._ensure_utc_datetime(parsed_dt)

        raise TypeError(
            "date_after must be a date, datetime, or ISO8601 string"
        )

    @staticmethod
    def _ensure_utc_datetime(value: datetime) -> datetime:
        """Coerce datetime objects to UTC-aware variants."""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    def _table_from_arrow(self, arrow_table: pa.Table, schema: ibis.Schema) -> Table:
        """Register an Arrow table with DuckDB and return an Ibis table."""

        table_name = f"_vector_store_{uuid.uuid4().hex}"
        self.conn.register(table_name, arrow_table)
        table = self._client.table(table_name)

        casts = {}
        for column_name, dtype in schema.items():
            column = table[column_name]
            if column.type() != dtype:
                casts[column_name] = column.cast(dtype)

        if casts:
            table = table.mutate(**casts)

        return table.select(schema.names)

    def _ensure_local_table(self, table: Table) -> Table:
        """Materialize a table on the store backend when necessary."""

        try:
            backend = table._find_backend()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive against Ibis internals
            backend = None

        if backend is self._client:
            return table

        source_schema = table.schema()
        op = table.op() if hasattr(table, "op") else None
        pandas_proxy = getattr(op, "data", None) if op is not None else None

        if pandas_proxy is not None and hasattr(pandas_proxy, "to_frame"):
            dataframe = pandas_proxy.to_frame()
            missing_columns = [
                column for column in source_schema.names if column not in dataframe.columns
            ]
            for column in missing_columns:
                dataframe[column] = None
            dataframe = dataframe.reindex(columns=source_schema.names)
        else:
            dataframe = table.execute()

        arrow_table = pa.Table.from_pandas(
            dataframe,
            schema=source_schema.to_pyarrow(),
            preserve_index=False,
            safe=False,
        )
        return self._table_from_arrow(arrow_table, source_schema)

    def _empty_table(self, schema: ibis.Schema) -> Table:
        """Create an empty table with the given schema using the local backend."""

        arrow_schema = schema.to_pyarrow()
        arrays = [pa.array([], type=field.type) for field in arrow_schema]
        empty_arrow = pa.Table.from_arrays(arrays, schema=arrow_schema)
        return self._table_from_arrow(empty_arrow, schema)

    def close(self) -> None:
        """Close the DuckDB connection if owned by this store."""

        if self._owns_connection:
            self.conn.close()

    def get_all(self) -> Table:
        """
        Read entire vector store.

        Useful for analytics, exports, client-side usage.
        """
        if not self.parquet_path.exists():
            return self._empty_table(VECTOR_STORE_SCHEMA)

        return self._client.read_parquet(self.parquet_path)

    def stats(self) -> dict:
        """Get vector store statistics."""
        if not self.parquet_path.exists():
            return {
                "total_chunks": 0,
                "total_posts": 0,
                "total_media": 0,
                "media_by_type": {},
            }

        df = self.get_all()
        total_chunks = df.count().execute()

        if total_chunks == 0:
            return {
                "total_chunks": 0,
                "total_posts": 0,
                "date_range": (None, None),
                "total_tags": 0,
            }

        # Check if document_type column exists (for backward compatibility)
        df_executed = df.execute()
        has_doc_type = "document_type" in df_executed.columns

        stats = {
            "total_chunks": total_chunks,
        }

        if has_doc_type:
            # New schema with document types
            post_df = df.filter(df.document_type == "post")
            media_df = df.filter(df.document_type == "media")

            post_count = post_df.count().execute()
            media_count = media_df.count().execute()

            stats["total_posts"] = post_df.post_slug.nunique().execute() if post_count > 0 else 0
            stats["total_media"] = media_df.media_uuid.nunique().execute() if media_count > 0 else 0

            # Media breakdown by type
            if media_count > 0:
                media_types_agg = (
                    media_df.group_by("media_type")
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
                    post_df.post_date.min().execute(),
                    post_df.post_date.max().execute(),
                )
            if media_count > 0:
                stats["media_date_range"] = (
                    media_df.message_date.min().execute(),
                    media_df.message_date.max().execute(),
                )

        else:
            # Old schema - all posts
            stats["total_posts"] = df.post_slug.nunique().execute()
            stats["total_media"] = 0
            stats["media_by_type"] = {}
            stats["date_range"] = (
                df.post_date.min().execute(),
                df.post_date.max().execute(),
            )
            stats["total_tags"] = df.tags.unnest().nunique().execute()

        return stats
