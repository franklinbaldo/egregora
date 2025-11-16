-- IR Messages Schema (IR v1)
-- Main table for all conversation messages in the pipeline
-- This table is created at pipeline initialization and used throughout

-- CLEAN BREAK: Drop old table if it exists (schema migration)
DROP TABLE IF EXISTS ir_messages;

CREATE TABLE ir_messages (
    -- Event identity
    -- NOTE: UUID stored as VARCHAR to avoid Ibis/PyArrow conversion issues
    event_id VARCHAR NOT NULL,

    -- Tenant/source metadata
    tenant_id VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    thread_id VARCHAR NOT NULL,

    -- Message identity
    msg_id VARCHAR NOT NULL,
    ts TIMESTAMP NOT NULL,

    -- Author information
    author_raw VARCHAR NOT NULL,
    author_uuid VARCHAR NOT NULL,

    -- Content
    text VARCHAR,

    -- Media references
    media_url VARCHAR,
    media_type VARCHAR,

    -- Metadata and flags
    attrs JSON,
    pii_flags JSON,

    -- Tracking
    created_at TIMESTAMP NOT NULL,
    created_by_run VARCHAR,

    -- Constraints
    PRIMARY KEY (event_id)
);

-- Index for timestamp-based queries (windowing)
CREATE INDEX IF NOT EXISTS idx_ir_messages_ts ON ir_messages(ts);

-- Index for thread-based queries
CREATE INDEX IF NOT EXISTS idx_ir_messages_thread ON ir_messages(thread_id);

-- Index for author-based queries
CREATE INDEX IF NOT EXISTS idx_ir_messages_author ON ir_messages(author_uuid);
