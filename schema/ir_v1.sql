-- IR v1 Schema: Intermediate Representation for Egregora Pipeline
-- Version: 1.0.0
-- Created: 2025-01-08
-- Status: LOCKED (changes require migration script + version bump)
--
-- This schema represents the canonical data contract between:
-- 1. Source adapters (WhatsApp, Slack, etc.) → IR
-- 2. IR → Privacy gate
-- 3. Privacy gate → Processing pipeline
--
-- Critical Invariant: All adapters MUST output this schema.
-- Breaking changes require a new version (ir_v2.sql) and migration path.

CREATE TABLE ir_v1 (
  -- ========================================================================
  -- Identity (PRIMARY KEY)
  -- ========================================================================
  event_id        UUID PRIMARY KEY,
    -- Unique identifier for each message/event
    -- Generated deterministically: uuid5(NAMESPACE_EVENTS, f"{source}:{msg_id}")
    -- Ensures re-ingestion produces identical event_ids

  -- ========================================================================
  -- Multi-Tenant Isolation
  -- ========================================================================
  tenant_id       VARCHAR NOT NULL DEFAULT 'default',
    -- Tenant identifier for multi-tenant deployments
    -- Default: 'default' for single-tenant setups
    -- Used in: UUID5 namespacing, privacy isolation, cost tracking

  source          VARCHAR NOT NULL,
    -- Source platform identifier
    -- Values: 'whatsapp', 'slack', 'discord', etc.
    -- Used in: Adapter routing, UUID5 namespacing

  -- ========================================================================
  -- Threading & Conversation Structure
  -- ========================================================================
  thread_id       UUID NOT NULL,
    -- Thread/conversation identifier
    -- WhatsApp: Group chat ID
    -- Slack: Channel ID or thread_ts
    -- Generated: uuid5(NS_THREADS, f"{tenant_id}:{source}:{thread_key}")

  msg_id          VARCHAR NOT NULL,
    -- Source-specific message identifier
    -- WhatsApp: Milliseconds since group creation
    -- Slack: Message timestamp (ts)
    -- Must be unique within (tenant_id, source, thread_id)

  -- ========================================================================
  -- Temporal
  -- ========================================================================
  ts              TIMESTAMP NOT NULL,
    -- Message timestamp (UTC)
    -- WhatsApp: Parsed from message line
    -- Slack: message.ts converted to datetime
    -- Used for: Windowing, chronological ordering

  -- ========================================================================
  -- Authors (PRIVACY BOUNDARY)
  -- ========================================================================
  author_raw      VARCHAR NOT NULL,
    -- Original author name/identifier from source
    -- ⚠️ CRITICAL: Never send to LLM APIs
    -- Cleared after privacy gate runs
    -- Used only for: UUID5 generation, opt-out detection

  author_uuid     UUID NOT NULL,
    -- Anonymized author identifier (UUID5)
    -- Generated: uuid5(NS_AUTHORS, f"{tenant_id}:{source}:{author_raw}")
    -- Stable across re-ingests
    -- Safe to send to LLM APIs after privacy gate

  -- ========================================================================
  -- Content
  -- ========================================================================
  text            TEXT,
    -- Message text content
    -- WhatsApp: Full message text
    -- Slack: message.text (after unescaping)
    -- May be NULL for media-only messages

  media_url       VARCHAR,
    -- URL or path to media attachment
    -- WhatsApp: <attached: photo.jpg>
    -- Slack: file.url_private
    -- NULL if no media

  media_type      VARCHAR,
    -- Media MIME type or category
    -- Values: 'image/jpeg', 'video/mp4', 'audio', 'document', etc.
    -- NULL if no media

  -- ========================================================================
  -- Metadata (Extensibility)
  -- ========================================================================
  attrs           JSON,
    -- Source-specific metadata (flexible schema)
    -- WhatsApp: {original_line, tagged_line, date}
    -- Slack: {reactions, thread_replies_count, edited}
    -- Allows adapter-specific data without schema changes

  pii_flags       JSON,
    -- PII detection results from privacy gate
    -- Format: {phone: true, email: false, address: false}
    -- NULL before privacy gate runs
    -- Used for: Audit, filtering, re-identification escrow

  -- ========================================================================
  -- Lineage & Provenance
  -- ========================================================================
  created_at      TIMESTAMP DEFAULT now(),
    -- When this row was created (ingestion time)
    -- Used for: Debugging, cache invalidation

  created_by_run  UUID,
    -- Foreign key to runs.run_id (if runs table exists)
    -- Tracks which pipeline run created this row
    -- NULL for manually inserted data
    -- REFERENCES runs(run_id) ON DELETE SET NULL
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Primary access pattern: Query by thread + timestamp
CREATE INDEX idx_ir_v1_thread_ts ON ir_v1 (thread_id, ts);

-- Multi-tenant queries
CREATE INDEX idx_ir_v1_tenant ON ir_v1 (tenant_id, source);

-- Author-based queries (for profiling)
CREATE INDEX idx_ir_v1_author ON ir_v1 (author_uuid);

-- Lineage tracking
CREATE INDEX idx_ir_v1_run ON ir_v1 (created_by_run) WHERE created_by_run IS NOT NULL;

-- ============================================================================
-- Constraints
-- ============================================================================

-- Uniqueness: One event per (tenant, source, thread, msg)
CREATE UNIQUE INDEX idx_ir_v1_unique_msg ON ir_v1 (tenant_id, source, thread_id, msg_id);

-- ============================================================================
-- Migration Notes
-- ============================================================================
--
-- Current CONVERSATION_SCHEMA Mapping:
--   timestamp       → ts
--   date            → attrs['date']
--   author          → author_uuid (after privacy gate) / author_raw (before)
--   message         → text
--   original_line   → attrs['original_line']
--   tagged_line     → attrs['tagged_line']
--   message_id      → msg_id
--
-- New Fields (not in current schema):
--   event_id        → Generated: uuid5(NS_EVENTS, source + msg_id)
--   tenant_id       → Default: 'default'
--   source          → Default: 'whatsapp'
--   thread_id       → Generated from conversation context
--   author_raw      → Original author name (pre-anonymization)
--   media_url       → NULL (for now)
--   media_type      → NULL (for now)
--   pii_flags       → NULL (populated by privacy gate)
--   created_at      → now()
--   created_by_run  → NULL (populated when runs table exists)
--
-- Backward Compatibility Strategy:
--   Phase 1 (Week 1): Add IR v1 schema as target, keep CONVERSATION_SCHEMA
--   Phase 2 (Week 2): Adapters output IR v1, validate at boundary
--   Phase 3 (Week 3): Privacy gate expects IR v1 input
--   Phase 4 (Week 4): Deprecate CONVERSATION_SCHEMA
--
-- ============================================================================
