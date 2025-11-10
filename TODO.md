# TODO: Priority D.1 - Runs Table + CLI

**Reference**: ARCHITECTURE_ROADMAP.md lines 1016-1168
**Status**: Not Started
**Estimated Effort**: 2 days
**Actual Start**: 2025-01-09

## Overview

Implement comprehensive run tracking for all pipeline stages with CLI commands for observability and debugging.

**Goal**: Every stage writes to `runs` table with execution metadata, enabling users to:
- View recent pipeline runs (`egregora runs tail`)
- Inspect detailed run information (`egregora runs show <run_id>`)
- Debug failures with context (fingerprints, errors, metrics)
- Track lineage (input → code → config → output)

## Roadmap Requirements (from ARCHITECTURE_ROADMAP.md:1016-1168)

### Core Implementation

**1. Run Tracking Function** (`src/egregora/pipeline/runner.py`)
- `run_stage_with_tracking()` wrapper for all stages
- Generate run_id (UUID)
- Compute input fingerprint (SHA256 of table + config + code)
- Check checkpoint before execution
- Record run status: "running" → "completed" | "failed"
- Track metrics: rows_in, rows_out, duration, llm_calls, tokens
- Save checkpoint on success

**2. Runs Table Schema**
```sql
CREATE TABLE runs (
    run_id UUID PRIMARY KEY,
    stage VARCHAR NOT NULL,
    status VARCHAR NOT NULL,  -- 'running', 'completed', 'failed'
    error TEXT,
    input_fingerprint VARCHAR NOT NULL,
    code_ref VARCHAR,  -- git commit SHA
    config_hash VARCHAR,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    rows_in INTEGER,
    rows_out INTEGER,
    duration_seconds FLOAT,
    llm_calls INTEGER,
    tokens INTEGER,
    trace_id VARCHAR  -- For OpenTelemetry integration (D.2)
);
```

**3. CLI Commands** (`src/egregora/cli.py`)

**`egregora runs tail [--n 10]`**:
- Show last N runs
- Display: run_id, stage, status, started_at, rows_in, rows_out
- Rich table formatting

**`egregora runs show <run_id>`**:
- Show detailed run info
- Display: all fields from runs table
- Panel formatting with sections

### Success Criteria (ARCHITECTURE_ROADMAP.md:1163-1167)

- [ ] Every stage writes to `runs` table
- [ ] `egregora runs tail` shows recent runs
- [ ] `egregora runs show <run_id>` shows details
- [ ] Mean-time-to-explain < 5 min using runs data

## Implementation Plan

### Phase 1: Database Schema & Utilities (30 min)

**Files to create:**
- [ ] `src/egregora/database/runs_schema.py`
  - Define RUNS_TABLE_SCHEMA
  - SQL DDL for runs table
  - Helper functions for schema creation

**Tasks:**
- [ ] Define Ibis schema for runs table
- [ ] Create SQL DDL
- [ ] Add schema to database/__init__.py exports
- [ ] Write schema creation tests

### Phase 2: Core Tracking Infrastructure (1 hour)

**Files to create/modify:**
- [ ] `src/egregora/pipeline/runner.py` (new or extend existing tracking.py)
  - `run_stage_with_tracking()` wrapper
  - `record_run()` insert/update function
  - `fingerprint_stage_input()` for content addressing
  - `get_git_commit()` for code_ref

**Tasks:**
- [ ] Implement run_stage_with_tracking() wrapper
- [ ] Implement record_run() with insert/update logic
- [ ] Implement fingerprint_stage_input() using hashlib
- [ ] Implement get_git_commit() using subprocess
- [ ] Integrate with existing checkpoint.py
- [ ] Handle checkpoint hits (status="completed", source="checkpoint")
- [ ] Handle stage failures (status="failed", error=str(e))

### Phase 3: CLI Commands (1 hour)

**Files to modify:**
- [ ] `src/egregora/cli.py`
  - Add `runs` command group
  - Add `tail` subcommand
  - Add `show` subcommand

**Tasks:**
- [ ] Create Typer group for runs commands
- [ ] Implement `egregora runs tail --n 10`
  - Query last N runs from runs table
  - Rich table formatting
  - Handle empty results
- [ ] Implement `egregora runs show <run_id>`
  - Query specific run by ID
  - Rich panel formatting
  - Handle not found
  - Display duration calculation
- [ ] Add --help text for all commands

### Phase 4: Integration with Existing Stages (2 hours)

**Files to modify:**
- [ ] Identify all pipeline stages that need tracking
- [ ] Wrap stage executions with run_stage_with_tracking()
- [ ] Pass run_id through context to child operations
- [ ] Update stage tests to handle runs table

**Stages to integrate:**
- [ ] Parse/Ingestion stage
- [ ] Privacy/Anonymization stage
- [ ] Enrichment stage
- [ ] Writing stage
- [ ] Ranking stage (if applicable)

### Phase 5: Testing (2 hours)

**Test files to create:**
- [ ] `tests/unit/test_runs_schema.py`
  - Schema validation
  - Table creation
  - Column types

- [ ] `tests/unit/test_runs_tracking.py`
  - run_stage_with_tracking() behavior
  - record_run() insert/update
  - fingerprint_stage_input() determinism
  - get_git_commit() functionality
  - Checkpoint integration
  - Error handling

- [ ] `tests/unit/test_runs_cli.py`
  - CLI command execution
  - Table formatting
  - Empty results handling
  - Run not found

- [ ] `tests/integration/test_end_to_end_tracking.py`
  - Full pipeline run with tracking
  - Multiple stages tracked
  - Runs visible via CLI

**Test coverage goals:**
- [ ] 100% coverage for runner.py
- [ ] 100% coverage for CLI commands
- [ ] Integration test with real pipeline execution

### Phase 6: Documentation (1 hour)

**Documentation to create:**
- [ ] `docs/observability/runs-tracking.md`
  - Overview of runs tracking
  - How to use CLI commands
  - Interpreting run data
  - Debugging with runs
  - Integration with checkpointing

**Documentation to update:**
- [ ] `CLAUDE.md` - Add runs tracking to Modern Patterns
- [ ] `README.md` - Add runs CLI to commands list
- [ ] Update ARCHITECTURE_ROADMAP.md status (D.1: Completed)

### Phase 7: PR Preparation (30 min)

**Files to create:**
- [ ] `PR_PRIORITY_D1.md`
  - Comprehensive PR description
  - Feature overview
  - Test results
  - CLI examples
  - Integration notes

## Technical Decisions

### Database

**StorageManager integration:**
- Use existing StorageManager for runs table access
- Create runs table on first access (lazy initialization)
- Runs stored in same DuckDB as pipeline data

**Schema design:**
- Simple flat table (no joins needed)
- UUID primary key for global uniqueness
- Nullable finished_at/error for running stages
- trace_id reserved for D.2 (OpenTelemetry)

### Fingerprinting Strategy

**Content addressing:**
```python
def fingerprint_stage_input(
    table: Table,
    config: Config,
    code_ref: str
) -> str:
    """Generate SHA256 fingerprint of stage inputs."""
    # 1. Table fingerprint (sample rows)
    sample = table.limit(1000).execute()
    table_hash = hashlib.sha256(sample.to_csv().encode()).hexdigest()

    # 2. Config fingerprint
    config_hash = hashlib.sha256(str(config).encode()).hexdigest()

    # 3. Combine with code_ref
    combined = f"{table_hash}:{config_hash}:{code_ref}"
    return f"sha256:{hashlib.sha256(combined.encode()).hexdigest()}"
```

### CLI Design

**Command structure:**
```bash
# List recent runs
egregora runs tail           # Default: last 10
egregora runs tail --n 20    # Last 20

# Show specific run
egregora runs show <run_id>

# Future extensions (not in D.1)
egregora runs list --stage enrichment
egregora runs list --status failed
egregora runs replay <run_id>  # Re-run with same inputs
```

**Output formatting:**
- Use Rich library for tables and panels
- Color-code status (green=completed, red=failed, yellow=running)
- Human-readable timestamps
- Duration in seconds with 2 decimal places

### Error Handling

**Graceful degradation:**
- If runs table doesn't exist, create it automatically
- If git not available, code_ref = "unknown"
- If fingerprint fails, use "unknown" + timestamp
- Log warnings but don't fail pipeline execution

## Dependencies

**Existing code to integrate:**
- `src/egregora/pipeline/checkpoint.py` - Content-addressed checkpointing
- `src/egregora/pipeline/tracking.py` - Existing run tracking (if any)
- `src/egregora/database/storage.py` - StorageManager
- `src/egregora/cli.py` - CLI framework

**New dependencies:**
- None (use existing Rich, Typer, hashlib, subprocess)

## Non-Goals (Deferred to D.2 or later)

- ❌ OpenTelemetry trace_id linkage (D.2)
- ❌ Distributed tracing spans (D.2)
- ❌ Run replay functionality (future)
- ❌ Run filtering/search (future)
- ❌ Run aggregation/statistics (future)
- ❌ Web UI for runs (future)

## Acceptance Criteria

**Must have:**
1. ✅ Runs table created in DuckDB
2. ✅ All stages write to runs table
3. ✅ `egregora runs tail` shows recent runs
4. ✅ `egregora runs show <run_id>` shows details
5. ✅ Checkpoint hits recorded in runs table
6. ✅ Failed runs recorded with error messages
7. ✅ Comprehensive tests (>90% coverage)
8. ✅ Documentation complete

**Nice to have:**
- ⭐ Color-coded status in CLI output
- ⭐ Duration auto-calculated and displayed
- ⭐ Run count summary in `egregora runs tail`
- ⭐ Copy-paste run_id from tail to show

## Timeline

- **Phase 1 (Schema)**: 30 min
- **Phase 2 (Tracking)**: 1 hour
- **Phase 3 (CLI)**: 1 hour
- **Phase 4 (Integration)**: 2 hours
- **Phase 5 (Testing)**: 2 hours
- **Phase 6 (Docs)**: 1 hour
- **Phase 7 (PR)**: 30 min

**Total**: ~8 hours (1 working day)

## Notes

- This implements only D.1 from the roadmap
- D.2 (OpenTelemetry integration) will build on this
- trace_id column reserved for D.2
- Run tracking is opt-in via wrapper (stages must use run_stage_with_tracking)
- Fingerprint strategy matches existing checkpoint.py approach
- All errors logged but don't fail pipeline (observability is non-critical)

## References

- **ARCHITECTURE_ROADMAP.md**: Lines 1016-1168 (Priority D.1)
- **Existing code**: `src/egregora/pipeline/checkpoint.py`
- **Existing code**: `src/egregora/pipeline/tracking.py`
- **Related PR**: PR_FOUNDATION.md (Quick Wins + Priority A)
- **Related PR**: PR_PRIORITY_C.md (C.1 + C.2 + C.3)
