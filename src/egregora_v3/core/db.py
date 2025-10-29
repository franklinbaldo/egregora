import duckdb
from pathlib import Path

def get_db_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Returns a connection to the DuckDB database."""
    return duckdb.connect(database=str(db_path), read_only=False)

def initialize_database(conn: duckdb.DuckDBPyConnection, embedding_dim: int):
    """Executes the DDL to create all tables and indexes."""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS rag_chunks (
            chunk_id TEXT PRIMARY KEY,
            slug TEXT,
            text TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS rag_vectors (
            chunk_id TEXT PRIMARY KEY REFERENCES rag_chunks(chunk_id),
            embedding FLOAT[{embedding_dim}]
        );
    """)
    conn.commit()

def create_vss_index(conn: duckdb.DuckDBPyConnection, metric: str):
    """Creates the VSS index on the rag_vectors table."""
    conn.execute("INSTALL vss;")
    conn.execute("LOAD vss;")
    conn.execute("SET hnsw_enable_experimental_persistence = true;")

    index_query = f"""
        CREATE INDEX IF NOT EXISTS rag_vectors_idx
        ON rag_vectors USING HNSW (embedding)
        WITH (metric = '{metric}');
    """
    conn.execute(index_query)
    conn.commit()
