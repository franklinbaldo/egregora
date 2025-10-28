"""Vector store using DuckDB VSS and Parquet."""

import logging
from pathlib import Path
from typing import Any

import duckdb
import ibis
import ibis.expr.datatypes as dt
from ibis.expr.types import Table

logger = logging.getLogger(__name__)


VECTOR_STORE_SCHEMA = ibis.schema(
    {
        "chunk_id": dt.string,
        "document_type": dt.string,
        "document_id": dt.string,
        "post_slug": dt.String(nullable=True),
        "post_title": dt.String(nullable=True),
        "post_date": dt.String(nullable=True),
        "media_uuid": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        "media_path": dt.String(nullable=True),
        "original_filename": dt.String(nullable=True),
        "message_date": dt.String(nullable=True),
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
        "post_date": dt.String(nullable=True),
        "media_uuid": dt.String(nullable=True),
        "media_type": dt.String(nullable=True),
        "media_path": dt.String(nullable=True),
        "original_filename": dt.String(nullable=True),
        "message_date": dt.String(nullable=True),
        "author_uuid": dt.String(nullable=True),
        "chunk_index": dt.int64,
        "content": dt.string,
        "tags": dt.Array(dt.string),
        "authors": dt.Array(dt.string),
        "category": dt.String(nullable=True),
        "similarity": dt.float64,
    }
)


class VectorStore:
    """
    Vector store backed by Parquet file.

    Uses DuckDB VSS extension for similarity search.
    Data lives in Parquet for portability and client-side access.
    """

    def __init__(self, parquet_path: Path):
        """
        Initialize vector store.

        Args:
            parquet_path: Path to Parquet file (e.g., output/rag/chunks.parquet)
        """
        self.parquet_path = parquet_path
        self.conn = duckdb.connect(":memory:")
        self._init_vss()
        self._backend = ibis.duckdb.connect()
        ibis.set_backend(self._backend)

    def _init_vss(self):
        """Initialize DuckDB VSS extension."""
        try:
            self.conn.execute("INSTALL vss")
            self.conn.execute("LOAD vss")
            logger.info("DuckDB VSS extension loaded")
        except Exception as e:
            logger.error(f"Failed to load VSS extension: {e}")
            raise

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
        if self.parquet_path.exists():
            # Read existing and append
            existing_df = ibis.read_parquet(self.parquet_path)
            existing_df, chunks_df = self._align_schemas(existing_df, chunks_df)
            combined_df = existing_df.union(chunks_df, distinct=False)
            existing_count = existing_df.count().execute()
            new_count = chunks_df.count().execute()
            logger.info(f"Appending {new_count} chunks to existing {existing_count} chunks")
        else:
            combined_df = chunks_df
            chunk_count = chunks_df.count().execute()
            logger.info(f"Creating new vector store with {chunk_count} chunks")

        # Write to Parquet
        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        combined_df.execute().to_parquet(self.parquet_path)

        logger.info(f"Vector store saved to {self.parquet_path}")

    def _align_schemas(self, existing_df: Table, new_df: Table) -> tuple[Table, Table]:  # noqa: PLR0912
        """Ensure both tables share the same schema before unioning."""

        existing_columns = set(existing_df.columns)
        new_columns = set(new_df.columns)

        # Backfill new document metadata columns for older stores (posts-only)
        if "document_type" not in existing_columns:
            logger.info("Backfilling document_type column on existing vector store")
            existing_df = existing_df.mutate(document_type=ibis.literal("post"))
            existing_columns.add("document_type")

        if "document_id" not in existing_columns:
            logger.info("Backfilling document_id column on existing vector store")
            document_id_expr = (
                existing_df.post_slug if "post_slug" in existing_columns else existing_df.chunk_id
            )
            existing_df = existing_df.mutate(document_id=document_id_expr)
            existing_columns.add("document_id")

        # Add nullable media metadata columns when missing
        for column_name in (
            "media_uuid",
            "media_type",
            "media_path",
            "original_filename",
            "message_date",
            "author_uuid",
        ):
            if column_name not in existing_columns and column_name in new_df.schema():
                dtype = new_df.schema()[column_name]
                existing_df = existing_df.mutate(**{column_name: ibis.null().cast(dtype)})
                existing_columns.add(column_name)

        # Ensure new rows still have legacy columns (e.g., authors)
        legacy_defaults = {}
        for column_name in existing_columns - new_columns:
            dtype = existing_df.schema()[column_name]
            legacy_defaults[column_name] = ibis.null().cast(dtype)

        if legacy_defaults:
            new_df = new_df.mutate(**legacy_defaults)
            new_columns.update(legacy_defaults)

        # Add any new columns that only exist on the new rows to the legacy data
        forward_defaults = {}
        for column_name in new_columns - existing_columns:
            dtype = new_df.schema()[column_name]
            forward_defaults[column_name] = ibis.null().cast(dtype)

        if forward_defaults:
            existing_df = existing_df.mutate(**forward_defaults)
            existing_columns.update(forward_defaults)

        # Align column order for deterministic unions
        ordered_columns = list(dict.fromkeys(list(existing_df.columns) + list(new_df.columns)))
        existing_df = existing_df.select(ordered_columns)
        new_df = new_df.select(ordered_columns)

        # Cast to canonical schema types when available
        existing_casts = {}
        new_casts = {}
        for column_name in ordered_columns:
            if column_name in VECTOR_STORE_SCHEMA:
                target_type = VECTOR_STORE_SCHEMA[column_name]
                if existing_df[column_name].type() != target_type:
                    existing_casts[column_name] = existing_df[column_name].cast(target_type)
                if new_df[column_name].type() != target_type:
                    new_casts[column_name] = new_df[column_name].cast(target_type)

        if existing_casts:
            existing_df = existing_df.mutate(**existing_casts)
        if new_casts:
            new_df = new_df.mutate(**new_casts)

        return existing_df, new_df

    def search(  # noqa: PLR0913
        self,
        query_vec: list[float],
        top_k: int = 5,
        min_similarity: float = 0.7,
        tag_filter: list[str] | None = None,
        date_after: str | None = None,
        document_type: str | None = None,
        media_types: list[str] | None = None,
    ) -> Table:
        """
        Search for similar chunks using cosine similarity.

        Args:
            query_vec: Query embedding vector
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity (0-1)
            tag_filter: Filter by tags (OR logic)
            date_after: Filter by date (ISO format YYYY-MM-DD)
            document_type: Filter by document type ("post" or "media")
            media_types: Filter by media type (e.g., ["image", "video"])

        Returns:
            Ibis Table with all stored columns plus similarity score
        """
        if not self.parquet_path.exists():
            logger.warning("Vector store does not exist yet")
            return ibis.memtable([], schema=SEARCH_RESULT_SCHEMA)

        embedding_dimensionality = len(query_vec)
        if embedding_dimensionality == 0:
            raise ValueError("Query embedding vector must not be empty")

        # Build SQL query - select all columns plus similarity
        query = f"""
            SELECT
                * EXCLUDE (embedding),
                array_cosine_similarity(
                    embedding::FLOAT[{embedding_dimensionality}],
                    ?::FLOAT[{embedding_dimensionality}]
                ) AS similarity
            FROM read_parquet('{self.parquet_path}')
            WHERE array_cosine_similarity(
                embedding::FLOAT[{embedding_dimensionality}],
                ?::FLOAT[{embedding_dimensionality}]
            ) >= {min_similarity}
        """

        # Add filters
        params = [query_vec, query_vec]  # Bind twice (similarity calc + WHERE)

        if document_type:
            query += f" AND document_type = '{document_type}'"

        if media_types:
            # Create SQL array literal
            media_list = "ARRAY[" + ", ".join(f"'{t}'" for t in media_types) + "]"
            query += f" AND media_type IN (SELECT unnest({media_list}))"

        if tag_filter:
            # Create SQL array literal
            tag_list = "ARRAY[" + ", ".join(f"'{t}'" for t in tag_filter) + "]"
            query += f" AND list_has_any(tags, {tag_list})"

        if date_after:
            query += f" AND (post_date > '{date_after}' OR message_date > '{date_after}')"

        query += f"""
            ORDER BY similarity DESC
            LIMIT {top_k}
        """

        try:
            # Execute query
            result_table = self.conn.execute(query, params).arrow()
            if result_table.num_rows == 0:
                return ibis.memtable([], schema=SEARCH_RESULT_SCHEMA)

            prepared_data = self._prepare_search_results(result_table)
            df = ibis.memtable(prepared_data, schema=SEARCH_RESULT_SCHEMA)

            row_count = df.count().execute()
            logger.info(f"Found {row_count} similar chunks (min_similarity={min_similarity})")

            return df

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return ibis.memtable([], schema=SEARCH_RESULT_SCHEMA)

    def _prepare_search_results(self, result_table) -> dict[str, list[Any]]:
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

        return data

    def get_all(self) -> Table:
        """
        Read entire vector store.

        Useful for analytics, exports, client-side usage.
        """
        if not self.parquet_path.exists():
            return ibis.memtable([], schema=VECTOR_STORE_SCHEMA)

        return ibis.read_parquet(self.parquet_path)

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
