-- Runs v1 Schema: Pipeline Execution Tracking
-- Version: 1.0.0
-- Created: 2025-01-08
-- Status: LOCKED (changes require migration script + version bump)
--
-- This schema tracks pipeline execution metadata for:
-- 1. Lineage tracking (which data came from which run?)
-- 2. Observability (performance metrics, errors)
-- 3. Deterministic checkpointing (content-addressed resume)
-- 4. Multi-tenant cost attribution (tokens, LLM calls)
--
-- Critical Invariant: All IR rows MUST reference a valid run_id.
-- Breaking changes require a new version (runs_v2.sql) and migration path.

CREATE TABLE runs (
  -- ========================================================================
  -- Identity (PRIMARY KEY)
  -- ========================================================================
  run_id              UUID PRIMARY KEY,
    -- Unique identifier for this pipeline run
    -- Generated: uuid.uuid4() at pipeline start
    -- Used in: IR v1 (created_by_run), OpenTelemetry (trace_id)

  -- ========================================================================
  -- Pipeline Context
  -- ========================================================================
  stage               VARCHAR NOT NULL,
    -- Pipeline stage identifier
    -- Values: 'ingestion', 'privacy', 'enrichment', 'generation', 'publication'
    -- Used for: Stage-specific metrics, filtering

  tenant_id           VARCHAR,
    -- Tenant identifier for multi-tenant deployments
    -- Default: NULL for single-tenant setups
    -- Used in: Cost attribution, privacy isolation

  -- ========================================================================
  -- Temporal
  -- ========================================================================
  started_at          TIMESTAMP NOT NULL,
    -- When this run started (UTC)
    -- Used for: Performance analysis, debugging

  finished_at         TIMESTAMP,
    -- When this run finished (UTC)
    -- NULL if still running or failed
    -- Used for: Duration calculation

  -- ========================================================================
  -- Input Fingerprint (Content-Addressed Checkpointing)
  -- ========================================================================
  input_fingerprint   VARCHAR NOT NULL,
    -- SHA256 hash of input data (IR table)
    -- Same input → same fingerprint (deterministic)
    -- Used for: Skip stages if output already exists
    -- Format: "sha256:<hex>"
    -- See: src/egregora/pipeline/checkpoint.py

  -- ========================================================================
  -- Code Version (Reproducibility)
  -- ========================================================================
  code_ref            VARCHAR,
    -- Git commit SHA of Egregora code
    -- Example: "a1b2c3d4e5f6..."
    -- NULL if not running from git repo
    -- Used for: Debugging version-specific issues

  config_hash         VARCHAR,
    -- SHA256 hash of pipeline config (EgregoraConfig)
    -- Same config → same hash (deterministic)
    -- Used for: Detect config changes between runs
    -- Format: "sha256:<hex>"

  -- ========================================================================
  -- Metrics (Performance & Cost)
  -- ========================================================================
  rows_in             INTEGER,
    -- Number of input rows processed
    -- NULL if not applicable (e.g., ingestion stage)

  rows_out            INTEGER,
    -- Number of output rows produced
    -- NULL if stage doesn't output rows

  llm_calls           INTEGER DEFAULT 0,
    -- Number of LLM API calls made
    -- Used for: Cost tracking, rate limit monitoring

  tokens              INTEGER DEFAULT 0,
    -- Total tokens consumed (input + output)
    -- Used for: Cost estimation, quota management

  -- ========================================================================
  -- Status & Errors
  -- ========================================================================
  status              VARCHAR NOT NULL,
    -- Run status
    -- Values:
    --   'running'   - Currently executing
    --   'completed' - Finished successfully
    --   'failed'    - Terminated with error
    --   'degraded'  - Completed with warnings (partial success)
    -- Default: 'running' (set at start)

  error               TEXT,
    -- Error message if status = 'failed'
    -- NULL if successful
    -- Format: Full traceback for debugging

  -- ========================================================================
  -- Observability (OpenTelemetry Integration)
  -- ========================================================================
  trace_id            VARCHAR
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
CREATE INDEX idx_runs_started_at ON runs (started_at DESC);

-- Filter by stage
CREATE INDEX idx_runs_stage ON runs (stage, started_at DESC);

-- Filter by tenant (multi-tenant deployments)
-- Note: DuckDB doesn't support partial indexes (WHERE clause removed)
CREATE INDEX idx_runs_tenant ON runs (tenant_id, started_at DESC);

-- Filter by status (find failed runs)
CREATE INDEX idx_runs_status ON runs (status, started_at DESC);

-- Content-addressed lookup (checkpoint hits)
CREATE INDEX idx_runs_fingerprint ON runs (input_fingerprint, stage);

-- ============================================================================
-- Constraints
-- ============================================================================

-- Valid status values: 'running', 'completed', 'failed', 'degraded'
-- Enforced by application logic (DuckDB doesn't support CHECK constraints)

-- Finished runs must have finished_at
-- (Enforced by application logic, not DB constraint)

-- ============================================================================
-- Usage Examples
-- ============================================================================

-- Find all failed runs in the last week:
--   SELECT * FROM runs
--   WHERE status = 'failed'
--     AND started_at >= NOW() - INTERVAL '7 days'
--   ORDER BY started_at DESC;

-- Calculate average duration for a stage:
--   SELECT stage, AVG(finished_at - started_at) AS avg_duration
--   FROM runs
--   WHERE status = 'completed'
--   GROUP BY stage;

-- Find most expensive runs (by tokens):
--   SELECT run_id, stage, tokens, llm_calls
--   FROM runs
--   WHERE tokens > 0
--   ORDER BY tokens DESC
--   LIMIT 10;

-- Check for cache hits (same input_fingerprint):
--   SELECT input_fingerprint, COUNT(*) AS hit_count
--   FROM runs
--   WHERE stage = 'enrichment'
--   GROUP BY input_fingerprint
--   HAVING COUNT(*) > 1;

-- ============================================================================
-- Migration Notes
-- ============================================================================

-- Backward Compatibility:
--   Phase 1 (Week 1): Create runs table
--   Phase 2 (Week 1): Update IR v1 to reference created_by_run
--   Phase 3 (Week 2): All stages write to runs table
--   Phase 4 (Week 3): Enforce NOT NULL on IR.created_by_run

-- Foreign Key Constraint (added in Phase 4):
--   ALTER TABLE ir_v1
--     ADD CONSTRAINT fk_ir_v1_run
--     FOREIGN KEY (created_by_run) REFERENCES runs(run_id)
--     ON DELETE SET NULL;

-- ============================================================================
