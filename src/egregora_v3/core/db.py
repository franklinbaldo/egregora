import duckdb
from pathlib import Path

# DDL for all tables and the VSS index
# This will be executed by the 'init' command.
DB_DDL = """
CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    slug TEXT,
    text TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rag_vectors (
    chunk_id TEXT REFERENCES rag_chunks(chunk_id),
    embedding FLOAT[]
);

-- Placeholder for VSS index creation with tunable parameters.
-- The actual DIM, nlist, and nprobe will be substituted from config.
-- CREATE INDEX rag_vectors_idx ON rag_vectors(embedding) USING vss(metric='cosine', nlist=1000, nprobe=10);

CREATE TABLE IF NOT EXISTS rank_players (
    player_id TEXT PRIMARY KEY,
    name TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rank_matches (
    match_id TEXT PRIMARY KEY,
    player_a_id TEXT REFERENCES rank_players(player_id),
    player_b_id TEXT REFERENCES rank_players(player_id),
    winner_id TEXT, -- Can be NULL for a draw
    match_time TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rank_ratings (
    player_id TEXT REFERENCES rank_players(player_id),
    rating FLOAT,
    rated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (player_id, rated_at)
);
"""

def get_db_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Returns a connection to the DuckDB database."""
    return duckdb.connect(database=str(db_path), read_only=False)

def initialize_database(conn: duckdb.DuckDBPyConnection):
    """Executes the DDL to create all tables and indexes."""
    conn.execute(DB_DDL)
    # Here you could also load extensions like VSS if needed.
    # conn.execute("INSTALL vss;")
    # conn.execute("LOAD vss;")

def get_vss_index_ddl(dim: int, metric: str, nlist: int, nprobe: int) -> str:
    """Constructs the VSS index DDL with parameters from config."""
    return f"CREATE INDEX rag_vectors_idx ON rag_vectors(embedding) USING vss(metric='{metric}', nlist={nlist}, nprobe={nprobe});"
