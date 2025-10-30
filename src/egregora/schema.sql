-- Centralized DuckDB schema for egregora persistence layers.
-- Contains table and index definitions shared across stores.

-- Writer annotations captured via the CLI.
CREATE TABLE IF NOT EXISTS annotations (
    id BIGINT PRIMARY KEY,
    msg_id TEXT NOT NULL,
    author TEXT NOT NULL,
    commentary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    parent_annotation_id BIGINT,
    CONSTRAINT fk_annotations_parent
        FOREIGN KEY (parent_annotation_id)
        REFERENCES annotations (id)
);

CREATE INDEX IF NOT EXISTS idx_annotations_msg_id_created
    ON annotations (msg_id, created_at);

-- Metadata cached for materialised Parquet datasets powering the vector store.
CREATE TABLE IF NOT EXISTS rag_chunks_metadata (
    path TEXT PRIMARY KEY,
    mtime_ns BIGINT,
    size BIGINT,
    row_count BIGINT
);

-- Persistent settings for approximate nearest neighbour indices.
CREATE TABLE IF NOT EXISTS index_meta (
    index_name TEXT PRIMARY KEY,
    mode TEXT,
    row_count BIGINT,
    threshold BIGINT,
    nlist INTEGER,
    updated_at TIMESTAMPTZ
);

-- Ranking store judge registry.
CREATE TABLE IF NOT EXISTS elo_profiles (
    profile_id VARCHAR PRIMARY KEY,
    first_seen TIMESTAMP NOT NULL
);

-- Aggregated judge statistics tied to the registry.
CREATE TABLE IF NOT EXISTS elo_profile_stats (
    profile_id VARCHAR PRIMARY KEY,
    alias VARCHAR,
    bio VARCHAR,
    comparisons INTEGER NOT NULL DEFAULT 0 CHECK (comparisons >= 0),
    last_seen TIMESTAMP NOT NULL,
    CONSTRAINT fk_elo_profile_stats_profile
        FOREIGN KEY (profile_id)
        REFERENCES elo_profiles (profile_id)
);

CREATE INDEX IF NOT EXISTS idx_profile_stats_last_seen
    ON elo_profile_stats (last_seen);

CREATE INDEX IF NOT EXISTS idx_profile_stats_comparisons
    ON elo_profile_stats (comparisons);

-- ELO ratings for ranked posts.
CREATE TABLE IF NOT EXISTS elo_ratings (
    post_id VARCHAR PRIMARY KEY,
    elo_global DOUBLE NOT NULL DEFAULT 1500,
    games_played INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ratings_games
    ON elo_ratings (games_played);

CREATE INDEX IF NOT EXISTS idx_ratings_elo
    ON elo_ratings (elo_global);

-- Comparison history between posts with judge provenance.
CREATE TABLE IF NOT EXISTS elo_history (
    comparison_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    profile_id VARCHAR NOT NULL,
    post_a VARCHAR NOT NULL,
    post_b VARCHAR NOT NULL,
    winner VARCHAR NOT NULL CHECK (winner IN ('A', 'B')),
    comment_a VARCHAR NOT NULL,
    stars_a INTEGER NOT NULL CHECK (stars_a BETWEEN 1 AND 5),
    comment_b VARCHAR NOT NULL,
    stars_b INTEGER NOT NULL CHECK (stars_b BETWEEN 1 AND 5),
    CONSTRAINT fk_elo_history_profile
        FOREIGN KEY (profile_id)
        REFERENCES elo_profiles (profile_id),
    CONSTRAINT fk_elo_history_post_a
        FOREIGN KEY (post_a)
        REFERENCES elo_ratings (post_id),
    CONSTRAINT fk_elo_history_post_b
        FOREIGN KEY (post_b)
        REFERENCES elo_ratings (post_id)
);

CREATE INDEX IF NOT EXISTS idx_history_post_a
    ON elo_history (post_a);

CREATE INDEX IF NOT EXISTS idx_history_post_b
    ON elo_history (post_b);

CREATE INDEX IF NOT EXISTS idx_history_timestamp
    ON elo_history (timestamp);
