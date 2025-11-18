-- Generated from IR_MESSAGE_SCHEMA in validation.py
-- DO NOT EDIT: This SQL is auto-generated

DROP TABLE IF EXISTS ir_messages;

CREATE TABLE ir_messages (
    event_id VARCHAR NOT NULL,
    tenant_id VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    thread_id VARCHAR NOT NULL,
    msg_id VARCHAR NOT NULL,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    author_raw VARCHAR NOT NULL,
    author_uuid VARCHAR NOT NULL,
    text VARCHAR,
    media_url VARCHAR,
    media_type VARCHAR,
    attrs JSON,
    pii_flags JSON,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by_run VARCHAR NOT NULL
,
    PRIMARY KEY (event_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ir_messages_ts ON ir_messages(ts);
CREATE INDEX IF NOT EXISTS idx_ir_messages_thread ON ir_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_ir_messages_author ON ir_messages(author_uuid);