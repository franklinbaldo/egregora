"""Lightweight DuckDB-backed vector store used by v3 experiments."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import duckdb


class DuckDBVectorStore:
    """Persist embeddings in DuckDB and expose ANN-style queries."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, embedding_dim: int) -> None:
        self.conn = conn
        self.embedding_dim = embedding_dim

    def upsert(self, vectors: Sequence[tuple[str, Sequence[float]]]) -> None:
        """Insert or update the provided embeddings."""
        if not vectors:
            return

        self.conn.execute(
            f"""
            CREATE TEMP TABLE temp_vectors (
                chunk_id TEXT,
                embedding FLOAT[{self.embedding_dim}]
            )
            """
        )
        self.conn.executemany("INSERT INTO temp_vectors VALUES (?, ?)", vectors)
        self.conn.execute(
            """
            INSERT INTO rag_vectors (chunk_id, embedding)
            SELECT chunk_id, embedding
            FROM temp_vectors
            ON CONFLICT (chunk_id) DO UPDATE
            SET embedding = excluded.embedding
            """
        )
        self.conn.execute("DROP TABLE temp_vectors")
        self.conn.commit()

    def query(self, query_embedding: Iterable[float], k: int) -> list[tuple[str, float]]:
        """Return the `k` closest embeddings by cosine distance."""
        embedding = list(query_embedding)
        return self.conn.execute(
            f"""
            SELECT
                chunk_id,
                array_distance(
                    embedding,
                    CAST(? AS FLOAT[{self.embedding_dim}])
                ) AS distance
            FROM rag_vectors
            ORDER BY distance
            LIMIT ?
            """,
            [embedding, k],
        ).fetchall()
