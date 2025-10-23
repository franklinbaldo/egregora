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
                - post_slug: str
                - post_title: str
                - post_date: date
                - chunk_index: int
                - content: str
                - embedding: list[float] (3072 dims)
                - tags: list[str]
                - authors: list[str]
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

    def search(
        self,
        query_vec: list[float],
        top_k: int = 5,
        min_similarity: float = 0.7,
        tag_filter: list[str] | None = None,
        date_after: str | None = None,
    ) -> pl.DataFrame:
        """
        Search for similar chunks using cosine similarity.

        Args:
            query_vec: Query embedding vector (3072 dims)
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity (0-1)
            tag_filter: Filter by tags (OR logic)
            date_after: Filter by date (ISO format YYYY-MM-DD)

        Returns:
            DataFrame with columns: chunk_id, post_slug, post_title, post_date,
                                   content, tags, authors, category, similarity
        """
        if not self.parquet_path.exists():
            logger.warning("Vector store does not exist yet")
            return pl.DataFrame()

        # Build SQL query
        query = f"""
            SELECT
                chunk_id,
                post_slug,
                post_title,
                post_date,
                chunk_index,
                content,
                tags,
                authors,
                category,
                array_cosine_similarity(embedding, ?::FLOAT[3072]) AS similarity
            FROM read_parquet('{self.parquet_path}')
            WHERE array_cosine_similarity(embedding, ?::FLOAT[3072]) >= {min_similarity}
        """

        # Add filters
        params = [query_vec, query_vec]  # Bind twice (similarity calc + WHERE)

        if tag_filter:
            # Create SQL array literal
            tag_list = "ARRAY[" + ", ".join(f"'{t}'" for t in tag_filter) + "]"
            query += f" AND list_has_any(tags, {tag_list})"

        if date_after:
            query += f" AND post_date > '{date_after}'"

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
            return {"total_chunks": 0, "total_posts": 0}

        df = self.get_all()

        return {
            "total_chunks": len(df),
            "total_posts": df["post_slug"].n_unique(),
            "date_range": (
                df["post_date"].min(),
                df["post_date"].max(),
            ) if len(df) > 0 else (None, None),
            "total_tags": df["tags"].explode().n_unique() if len(df) > 0 else 0,
        }
