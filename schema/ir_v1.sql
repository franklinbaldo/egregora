-- IR v1 Canonical Schema
-- This is the authoritative schema definition for the Intermediate Representation (IR).
-- All source adapters MUST produce tables conforming to this schema.
--
-- DO NOT MODIFY WITHOUT:
-- 1. Updating schema/ir_v1.json
-- 2. Updating src/egregora/database/validation.py:IR_V1_SCHEMA
-- 3. Running scripts/check_ir_schema.py
-- 4. Updating all adapter implementations
-- 5. Incrementing IR version (ir_v2.sql)
--
-- Generated: 2025-01-08
-- Version: 1.0.0

CREATE TABLE ir_messages (
    -- Identity: Unique event identifier
    event_id UUID NOT NULL,

    -- Multi-Tenant: Namespace isolation for multiple data sources
    tenant_id VARCHAR NOT NULL,
    source VARCHAR NOT NULL,

    -- Threading: Conversation structure
    thread_id UUID NOT NULL,
    msg_id VARCHAR NOT NULL,

    -- Temporal: Message timestamp
    ts TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Authors: PRIVACY BOUNDARY
    -- author_raw: Original author name (anonymized before LLM processing)
    -- author_uuid: Deterministic UUID mapping for privacy
    author_raw VARCHAR NOT NULL,
    author_uuid UUID NOT NULL,

    -- Content: Message payload
    text VARCHAR,
    media_url VARCHAR,
    media_type VARCHAR,

    -- Metadata: Flexible extension point
    -- attrs: Source-specific attributes (JSON)
    -- pii_flags: PII detection results (JSON)
    attrs JSON,
    pii_flags JSON,

    -- Lineage: Pipeline tracking
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by_run UUID,

    -- Constraints
    PRIMARY KEY (event_id)
);

-- Index recommendations for common queries
CREATE INDEX idx_ir_messages_ts ON ir_messages(ts);
CREATE INDEX idx_ir_messages_author_uuid ON ir_messages(author_uuid);
CREATE INDEX idx_ir_messages_thread_id ON ir_messages(thread_id);
CREATE INDEX idx_ir_messages_tenant_id_source ON ir_messages(tenant_id, source);
