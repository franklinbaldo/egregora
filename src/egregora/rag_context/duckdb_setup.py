"""DuckDB setup for in-memory vector search."""

from __future__ import annotations

from pathlib import Path

import duckdb
import ibis
from typing import Callable
import polars as pl

def setup_duckdb(parquet_path: str | Path) -> duckdb.DuckDBPyConnection:
    """
    Sets up an in-memory DuckDB database with the VSS extension,
    loads data from a Parquet file, and creates an HNSW index.

    Args:
        parquet_path: The path to the embeddings Parquet file.

    Returns:
        A connection to the configured in-memory DuckDB database.
    """
    con = duckdb.connect(':memory:')
    con.execute("INSTALL vss;")
    con.execute("LOAD vss;")
    con.execute(f"CREATE TABLE posts AS SELECT * FROM '{parquet_path}';")
    con.execute("CREATE INDEX posts_vec_idx ON posts USING HNSW(vector) WITH (metric='cosine');")
    return con


def create_ibis_search_function(
    con: duckdb.DuckDBPyConnection,
) -> Callable[[list[float], int], pl.DataFrame]:
    """
    Creates a function that performs a similarity search on the DuckDB table.

    Args:
        con: A connection to the DuckDB database.

    Returns:
        A function that takes a query vector and a limit `k` and returns a
        Polars DataFrame with the search results.
    """
    ibis_con = ibis.duckdb.connect(con)
    posts = ibis_con.table("posts")

    def search_similar(query_vector: list[float], k: int) -> pl.DataFrame:
        """Performs a similarity search."""
        # Using a raw SQL fallback as planned
        query = f"""
        SELECT *
        FROM posts
        ORDER BY vector_cosine_distance(vector, {query_vector})
        LIMIT {k}
        """
        return con.execute(query).pl()

    return search_similar
