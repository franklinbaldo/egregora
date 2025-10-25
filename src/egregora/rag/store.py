"""Vector store using DuckDB VSS and Parquet."""

import logging
from pathlib import Path

import duckdb
import polars as pl

logger = logging.getLogger(__name__)


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

    def _init_vss(self):
        """Initialize DuckDB VSS extension."""
        try:
            self.conn.execute("INSTALL vss")
            self.conn.execute("LOAD vss")
            logger.info("DuckDB VSS extension loaded")
        except Exception as e:
            logger.error(f"Failed to load VSS extension: {e}")
            raise

    def add(self, chunks_df: pl.DataFrame):
        """
        Add chunks to the vector store.

        Appends to existing Parquet file or creates new one.

        Args:
            chunks_df: DataFrame with columns:
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
                - embedding: list[float] (3072 dims)
                - tags: list[str]
                - category: str | None
        """
        if self.parquet_path.exists():
            # Read existing and append
            existing_df = pl.read_parquet(self.parquet_path)
            combined_df = pl.concat([existing_df, chunks_df])
            logger.info(f"Appending {len(chunks_df)} chunks to existing {len(existing_df)} chunks")
        else:
            combined_df = chunks_df
            logger.info(f"Creating new vector store with {len(chunks_df)} chunks")

        # Write to Parquet
        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        combined_df.write_parquet(self.parquet_path)

        logger.info(f"Vector store saved to {self.parquet_path}")

    def search(  # noqa: PLR0913
        self,
        query_vec: list[float],
        top_k: int = 5,
        min_similarity: float = 0.7,
        tag_filter: list[str] | None = None,
        date_after: str | None = None,
        document_type: str | None = None,
        media_types: list[str] | None = None,
    ) -> pl.DataFrame:
        """
        Search for similar chunks using cosine similarity.

        Args:
            query_vec: Query embedding vector (3072 dims)
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity (0-1)
            tag_filter: Filter by tags (OR logic)
            date_after: Filter by date (ISO format YYYY-MM-DD)
            document_type: Filter by document type ("post" or "media")
            media_types: Filter by media type (e.g., ["image", "video"])

        Returns:
            DataFrame with all stored columns plus similarity score
        """
        if not self.parquet_path.exists():
            logger.warning("Vector store does not exist yet")
            return pl.DataFrame()

        # Build SQL query - select all columns plus similarity
        query = f"""
            SELECT
                *,
                array_cosine_similarity(embedding::FLOAT[3072], ?::FLOAT[3072]) AS similarity
            FROM read_parquet('{self.parquet_path}')
            WHERE array_cosine_similarity(embedding::FLOAT[3072], ?::FLOAT[3072]) >= {min_similarity}
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
            result = self.conn.execute(query, params).arrow()
            df = pl.from_arrow(result)

            logger.info(f"Found {len(df)} similar chunks (min_similarity={min_similarity})")

            return df

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return pl.DataFrame()

    def get_all(self) -> pl.DataFrame:
        """
        Read entire vector store.

        Useful for analytics, exports, client-side usage.
        """
        if not self.parquet_path.exists():
            return pl.DataFrame()

        return pl.read_parquet(self.parquet_path)

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

        # Check if document_type column exists (for backward compatibility)
        has_doc_type = "document_type" in df.columns

        stats = {
            "total_chunks": len(df),
        }

        if has_doc_type:
            # New schema with document types
            post_df = df.filter(pl.col("document_type") == "post")
            media_df = df.filter(pl.col("document_type") == "media")

            stats["total_posts"] = post_df["post_slug"].n_unique() if len(post_df) > 0 else 0
            stats["total_media"] = media_df["media_uuid"].n_unique() if len(media_df) > 0 else 0

            # Media breakdown by type
            if len(media_df) > 0:
                media_types = media_df.group_by("media_type").agg(
                    pl.col("media_uuid").n_unique().alias("count")
                )
                stats["media_by_type"] = {
                    row["media_type"]: row["count"]
                    for row in media_types.iter_rows(named=True)
                    if row["media_type"]
                }

            # Date ranges
            if len(post_df) > 0:
                stats["post_date_range"] = (
                    post_df["post_date"].min(),
                    post_df["post_date"].max(),
                )
            if len(media_df) > 0:
                stats["media_date_range"] = (
                    media_df["message_date"].min(),
                    media_df["message_date"].max(),
                )

        else:
            # Old schema - all posts
            stats["total_posts"] = df["post_slug"].n_unique() if len(df) > 0 else 0
            stats["total_media"] = 0
            stats["media_by_type"] = {}
            if len(df) > 0:
                stats["post_date_range"] = (
                    df["post_date"].min(),
                    df["post_date"].max(),
                )

        return stats
