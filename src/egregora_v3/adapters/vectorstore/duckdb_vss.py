from typing import List, Tuple
import duckdb

class DuckDBVectorStore:
    """
    A vector store implementation using DuckDB with the VSS extension.
    """
    def __init__(self, conn: duckdb.DuckDBPyConnection, embedding_dim: int):
        self.conn = conn
        self.embedding_dim = embedding_dim

    def upsert(self, vectors: List[Tuple[str, List[float]]]):
        """
        Upserts a list of (chunk_id, embedding) tuples into the database.
        """
        if not vectors:
            return

        # Use a temporary table for efficient bulk insertion
        self.conn.execute(f"CREATE TEMP TABLE temp_vectors (chunk_id TEXT, embedding FLOAT[{self.embedding_dim}]);")
        self.conn.executemany("INSERT INTO temp_vectors VALUES (?, ?)", vectors)

        # Merge into the main rag_vectors table
        self.conn.execute("""
            INSERT INTO rag_vectors (chunk_id, embedding)
            SELECT chunk_id, embedding FROM temp_vectors
            ON CONFLICT (chunk_id) DO UPDATE SET embedding = excluded.embedding;
        """)

        self.conn.execute("DROP TABLE temp_vectors;")
        self.conn.commit()

    def query(self, query_embedding: List[float], k: int) -> List[Tuple[str, float]]:
        """
        Queries the vector store for the top k nearest neighbors using the HNSW index.
        """
        # The query uses the ORDER BY ... LIMIT pattern to leverage the HNSW index
        query = f"""
            SELECT chunk_id, array_distance(embedding, CAST(? AS FLOAT[{self.embedding_dim}])) as distance
            FROM rag_vectors
            ORDER BY distance
            LIMIT ?;
        """

        return self.conn.execute(query, [query_embedding, k]).fetchall()
