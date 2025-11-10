-- Lineage v1 Schema: Pipeline DAG Tracking
-- Version: 1.0.0
-- Created: 2025-01-08
-- Status: LOCKED (changes require migration script + version bump)
--
-- This schema tracks data lineage relationships between pipeline runs:
-- 1. Which runs depend on which other runs?
-- 2. Data provenance (trace IR rows back to source)
-- 3. Impact analysis (if run X fails, which downstream runs are affected?)
-- 4. Reproducibility (what inputs produced this output?)
--
-- Example DAG:
--   ingestion_run_1 → privacy_run_1 → enrichment_run_1 → generation_run_1
--                                  \→ enrichment_run_2 → generation_run_2
--
-- Lineage entries:
--   (privacy_run_1, ingestion_run_1)      # privacy depends on ingestion
--   (enrichment_run_1, privacy_run_1)     # enrichment depends on privacy
--   (enrichment_run_2, privacy_run_1)     # same privacy run, different enrichment
--   (generation_run_1, enrichment_run_1)  # generation depends on enrichment
--   (generation_run_2, enrichment_run_2)

CREATE TABLE lineage (
  -- ========================================================================
  -- Lineage Relationship (Composite PRIMARY KEY)
  -- ========================================================================
  child_run_id   UUID NOT NULL,
    -- Run ID of the downstream/dependent run
    -- Example: enrichment_run_1 (depends on privacy_run_1)
    -- REFERENCES runs(run_id)

  parent_run_id  UUID NOT NULL,
    -- Run ID of the upstream/dependency run
    -- Example: privacy_run_1 (produced input for enrichment_run_1)
    -- REFERENCES runs(run_id)

  PRIMARY KEY (child_run_id, parent_run_id),
    -- A child can have multiple parents (e.g., join two tables)
    -- A parent can have multiple children (e.g., privacy → multiple enrichments)

  -- ========================================================================
  -- Foreign Key Constraints
  -- ========================================================================
  -- Note: DuckDB doesn't support ON DELETE CASCADE
  -- Application must handle orphaned lineage edges manually
  FOREIGN KEY (child_run_id)  REFERENCES runs(run_id),
  FOREIGN KEY (parent_run_id) REFERENCES runs(run_id)
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Find all parents of a run (upstream dependencies)
CREATE INDEX idx_lineage_child ON lineage (child_run_id);

-- Find all children of a run (downstream dependents)
CREATE INDEX idx_lineage_parent ON lineage (parent_run_id);

-- ============================================================================
-- Usage Examples
-- ============================================================================

-- Find all upstream dependencies of a run (BFS traversal):
--   WITH RECURSIVE ancestors AS (
--     SELECT parent_run_id AS run_id, 1 AS depth
--     FROM lineage
--     WHERE child_run_id = 'target-run-id'
--
--     UNION ALL
--
--     SELECT l.parent_run_id, a.depth + 1
--     FROM lineage l
--     JOIN ancestors a ON l.child_run_id = a.run_id
--     WHERE a.depth < 10  -- Prevent infinite loops
--   )
--   SELECT r.*
--   FROM ancestors a
--   JOIN runs r ON a.run_id = r.run_id
--   ORDER BY a.depth;

-- Find all downstream dependents of a run (impact analysis):
--   WITH RECURSIVE descendants AS (
--     SELECT child_run_id AS run_id, 1 AS depth
--     FROM lineage
--     WHERE parent_run_id = 'source-run-id'
--
--     UNION ALL
--
--     SELECT l.child_run_id, d.depth + 1
--     FROM lineage l
--     JOIN descendants d ON l.parent_run_id = d.run_id
--     WHERE d.depth < 10  -- Prevent infinite loops
--   )
--   SELECT r.*
--   FROM descendants d
--   JOIN runs r ON d.run_id = r.run_id
--   ORDER BY d.depth;

-- Find runs with no parents (entry points):
--   SELECT r.*
--   FROM runs r
--   WHERE NOT EXISTS (
--     SELECT 1 FROM lineage WHERE child_run_id = r.run_id
--   );

-- Find runs with no children (leaf nodes):
--   SELECT r.*
--   FROM runs r
--   WHERE NOT EXISTS (
--     SELECT 1 FROM lineage WHERE parent_run_id = r.run_id
--   );

-- Detect cycles (should be empty in DAG):
--   WITH RECURSIVE cycle_check AS (
--     SELECT child_run_id, parent_run_id, ARRAY[child_run_id] AS path
--     FROM lineage
--
--     UNION ALL
--
--     SELECT l.child_run_id, l.parent_run_id, cc.path || l.child_run_id
--     FROM lineage l
--     JOIN cycle_check cc ON l.parent_run_id = cc.child_run_id
--     WHERE NOT (l.child_run_id = ANY(cc.path))  -- Detect cycle
--   )
--   SELECT * FROM cycle_check
--   WHERE child_run_id = ANY(path[2:]);  -- Found cycle

-- ============================================================================
-- Lineage Visualization (Mermaid Graph)
-- ============================================================================

-- Generate Mermaid diagram:
--   SELECT
--     'graph TD' AS header
--   UNION ALL
--   SELECT
--     '  ' || parent_run_id || '[' || p.stage || '] --> ' ||
--     child_run_id || '[' || c.stage || ']'
--   FROM lineage
--   JOIN runs p ON lineage.parent_run_id = p.run_id
--   JOIN runs c ON lineage.child_run_id = c.run_id
--   ORDER BY p.started_at;

-- Example output:
--   graph TD
--     run1[ingestion] --> run2[privacy]
--     run2[privacy] --> run3[enrichment]
--     run3[enrichment] --> run4[generation]

-- ============================================================================
-- CLI Integration
-- ============================================================================

-- egregora runs lineage <run_id>:
--   1. Find all ancestors and descendants
--   2. Render as tree or DAG
--   3. Highlight critical path (longest duration)
--   4. Show cache hits (runs skipped via checkpointing)

-- Example output:
--   Run: enrichment_run_1 (completed in 45s)
--
--   Ancestors:
--     ├─ privacy_run_1 (completed in 12s)
--     │  └─ ingestion_run_1 (completed in 8s)
--
--   Descendants:
--     ├─ generation_run_1 (completed in 120s)
--     └─ generation_run_2 (failed)
--
--   Total DAG duration: 185s
--   Cache hits: 0

-- ============================================================================
-- Migration Notes
-- ============================================================================

-- Backward Compatibility:
--   Phase 1 (Week 1): Create lineage table
--   Phase 2 (Week 1): Update pipeline to write lineage edges
--   Phase 3 (Week 2): All stages record lineage
--   Phase 4 (Week 3): Validate DAG has no cycles

-- Constraint Validation (CI check):
--   - No cycles (DAG property)
--   - All referenced run_ids exist in runs table (FK constraint)
--   - No self-loops (child_run_id != parent_run_id)

-- ============================================================================
