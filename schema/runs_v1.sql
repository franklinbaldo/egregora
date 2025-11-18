-- Runs v1 Schema: Pipeline Execution Tracking
-- Version: 2.0.0 (Simplified - 2025-11-17)
-- Status: ACTIVE (synchronized with src/egregora/database/ir_schema.py)
--
-- IMPORTANT: This file is now synchronized with the canonical Python schema.
-- Single source of truth: src/egregora/database/ir_schema.py:RUNS_TABLE_DDL
-- Any changes should be made in Python first, then mirrored here.
--
-- This schema tracks pipeline execution metadata for:
-- 1. Simple lineage tracking (parent_run_id column)
-- 2. Observability (performance metrics, errors)
-- 3. Multi-tenant cost attribution (tokens, LLM calls)
--
-- CHANGES from v1.0.0:
-- - REMOVED: input_fingerprint column (fingerprinting removed)
-- - REMOVED: Separate lineage table (simplified to parent_run_id column)
-- - ADDED: parent_run_id UUID for simple lineage
-- - ADDED: duration_seconds DOUBLE PRECISION for timing
-- - ADDED: attrs JSON for extensibility

CREATE TABLE IF NOT EXISTS runs (
    -- ========================================================================
    -- Identity (PRIMARY KEY)
    -- ========================================================================
    run_id UUID PRIMARY KEY,
      -- Unique identifier for this pipeline run
      -- Generated: uuid.uuid4() at pipeline start
      -- Used in: IR v1 (created_by_run), OpenTelemetry (trace_id)

    -- ========================================================================
    -- Multi-tenant Isolation
    -- ========================================================================
    tenant_id VARCHAR,
      -- Tenant identifier for multi-tenant deployments
      -- Default: NULL for single-tenant setups
      -- Used in: Cost attribution, privacy isolation

    -- ========================================================================
    -- Pipeline Context
    -- ========================================================================
    stage VARCHAR NOT NULL,
      -- Pipeline stage identifier
      -- Values: 'write', 'read', 'edit', or custom stage names
      -- Used for: Stage-specific metrics, filtering

    -- ========================================================================
    -- Status & Errors
    -- ========================================================================
    status VARCHAR NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'degraded')),
      -- Run status
      -- Values:
      --   'running'   - Currently executing
      --   'completed' - Finished successfully
      --   'failed'    - Terminated with error
      --   'degraded'  - Completed with warnings (partial success)
      -- Default: 'running' (set at start)

    error TEXT,
      -- Error message if status = 'failed'
      -- NULL if successful
      -- Format: Full traceback for debugging

    -- ========================================================================
    -- Lineage (Simplified Single-Parent Model)
    -- ========================================================================
    parent_run_id UUID,
      -- Parent run ID for simple lineage tracking
      -- NULL for root runs (no parent)
      -- Used for: Building lineage DAG, tracking run dependencies
      -- Example: enrichment run references ingestion run as parent

    -- ========================================================================
    -- Code Version (Reproducibility)
    -- ========================================================================
    code_ref VARCHAR,
      -- Git commit SHA of Egregora code
      -- Example: "a1b2c3d4e5f6..."
      -- NULL if not running from git repo
      -- Used for: Debugging version-specific issues

    config_hash VARCHAR,
      -- SHA256 hash of pipeline config (EgregoraConfig)
      -- Same config → same hash (deterministic)
      -- Used for: Detect config changes between runs
      -- Format: "sha256:<hex>"

    -- ========================================================================
    -- Temporal
    -- ========================================================================
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
      -- When this run started (UTC)
      -- Used for: Performance analysis, debugging

    finished_at TIMESTAMP WITH TIME ZONE,
      -- When this run finished (UTC)
      -- NULL if still running or failed
      -- Used for: Duration calculation

    -- ========================================================================
    -- Metrics (Performance & Cost)
    -- ========================================================================
    rows_in BIGINT,
      -- Number of input rows processed
      -- NULL if not applicable (e.g., ingestion stage)

    rows_out BIGINT,
      -- Number of output rows produced
      -- NULL if stage doesn't output rows

    duration_seconds DOUBLE PRECISION,
      -- Total duration in seconds (finished_at - started_at)
      -- NULL if still running
      -- Used for: Performance monitoring, timeout detection

    llm_calls BIGINT,
      -- Number of LLM API calls made
      -- Used for: Cost tracking, rate limit monitoring

    tokens BIGINT,
      -- Total tokens consumed (input + output)
      -- Used for: Cost estimation, quota management

    -- ========================================================================
    -- Extensibility
    -- ========================================================================
    attrs JSON,
      -- Stage-specific metadata (flexible extension point)
      -- Examples:
      --   {"num_windows": 10, "total_posts": 42}
      --   {"avg_post_length": 1234, "media_count": 5}
      -- Used for: Custom metrics without schema changes

    -- ========================================================================
    -- Observability (OpenTelemetry Integration)
    -- ========================================================================
    trace_id VARCHAR
      -- OpenTelemetry trace ID
      -- Used for: Correlating logs, traces, metrics
      -- Format: Hex string (e.g., "1234567890abcdef")
      -- NULL if OpenTelemetry not enabled
      -- See: src/egregora/utils/telemetry.py
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Primary access pattern: Query recent runs
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC);

-- Filter by stage
CREATE INDEX IF NOT EXISTS idx_runs_stage ON runs(stage);

-- Filter by status (find failed runs)
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

-- Filter by tenant (multi-tenant deployments)
CREATE INDEX IF NOT EXISTS idx_runs_tenant ON runs(tenant_id);

-- Lineage traversal (find children of a run)
CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id);

-- ============================================================================
-- Usage Examples
-- ============================================================================

-- Find all failed runs in the last week:
--   SELECT * FROM runs
--   WHERE status = 'failed'
--     AND started_at >= NOW() - INTERVAL '7 days'
--   ORDER BY started_at DESC;

-- Calculate average duration for a stage:
--   SELECT stage, AVG(duration_seconds) AS avg_duration_seconds
--   FROM runs
--   WHERE status = 'completed'
--   GROUP BY stage;

-- Find most expensive runs (by tokens):
--   SELECT run_id, stage, tokens, llm_calls
--   FROM runs
--   WHERE tokens > 0
--   ORDER BY tokens DESC
--   LIMIT 10;

-- Build lineage chain (recursive query):
--   WITH RECURSIVE lineage AS (
--     SELECT run_id, parent_run_id, stage, 0 AS depth
--     FROM runs
--     WHERE run_id = '<target-run-id>'
--     UNION ALL
--     SELECT r.run_id, r.parent_run_id, r.stage, l.depth + 1
--     FROM runs r
--     JOIN lineage l ON r.run_id = l.parent_run_id
--   )
--   SELECT * FROM lineage ORDER BY depth;

-- ============================================================================
-- Migration Notes
-- ============================================================================

-- From v1.0.0 to v2.0.0 (2025-11-17):
--   - input_fingerprint column removed (fingerprinting simplified)
--   - Separate lineage table removed (use parent_run_id instead)
--   - Added duration_seconds for explicit timing
--   - Added parent_run_id for simple lineage
--   - Added attrs JSON for extensibility
--
-- Existing databases: Run ALTER TABLE to add new columns
--   ALTER TABLE runs ADD COLUMN parent_run_id UUID;
--   ALTER TABLE runs ADD COLUMN duration_seconds DOUBLE PRECISION;
--   ALTER TABLE runs ADD COLUMN attrs JSON;
--   -- Note: input_fingerprint can be left in place (ignored by new code)

-- ============================================================================
