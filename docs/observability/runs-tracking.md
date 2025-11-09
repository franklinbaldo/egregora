# Pipeline Run Tracking

**Status**: Implemented (Priority D.1)
**Version**: 1.0.0
**Last Updated**: 2025-01-09

## Overview

Egregora tracks every pipeline execution in a **runs database** (`.egregora/runs.duckdb`) to provide observability, debugging, and performance monitoring. Each window processed becomes a tracked **run** with metadata, timing, and status.

**Key Features:**
- Automatic tracking of all pipeline windows
- CLI commands for viewing run history
- Error tracking with full stack traces
- Performance metrics (duration, rows processed)
- Content-addressed checkpointing (planned)

## Quick Start

```bash
# Process a WhatsApp export (runs automatically tracked)
egregora process export.zip --output=./my-blog

# View recent runs
egregora runs tail

# View detailed run info
egregora runs show <run_id>
```

## Database Schema

Each run is stored in `.egregora/runs.duckdb` with the following schema:

```sql
CREATE TABLE runs (
    run_id UUID PRIMARY KEY,              -- Unique run identifier
    tenant_id VARCHAR,                    -- Multi-tenant isolation (optional)
    stage VARCHAR NOT NULL,               -- Stage name (e.g., "window_0", "window_1")
    status VARCHAR NOT NULL,              -- 'running', 'completed', 'failed', 'degraded'
    error TEXT,                           -- Error message if status='failed'

    -- Fingerprinting (for checkpointing)
    input_fingerprint VARCHAR,            -- SHA256 of input data
    code_ref VARCHAR,                     -- Git commit SHA (auto-detected)
    config_hash VARCHAR,                  -- SHA256 of config

    -- Timing
    started_at TIMESTAMP NOT NULL,        -- When run started (UTC)
    finished_at TIMESTAMP,                -- When run finished (UTC)
    duration_seconds DOUBLE PRECISION,    -- Auto-calculated duration

    -- Metrics
    rows_in BIGINT,                       -- Number of input messages
    rows_out BIGINT,                      -- Number of output rows (future)
    llm_calls BIGINT,                     -- Number of LLM API calls (future)
    tokens BIGINT,                        -- Total tokens consumed (future)

    -- Observability
    trace_id VARCHAR                      -- OpenTelemetry trace ID (future)
);
```

**Indexes:**
- `idx_runs_started_at` - For recent runs queries
- `idx_runs_stage` - For filtering by stage
- `idx_runs_status` - For filtering by status
- `idx_runs_fingerprint` - For checkpointing lookups
- `idx_runs_tenant` - For multi-tenant isolation

## CLI Commands

### `egregora runs tail`

Show the last N runs in a formatted table.

**Usage:**
```bash
egregora runs tail              # Last 10 runs (default)
egregora runs tail --n 20       # Last 20 runs
egregora runs tail --n 5        # Last 5 runs
```

**Output:**
```
┏━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Run ID   ┃ Stage    ┃ Status    ┃ Started At         ┃ Rows In ┃ Rows Out ┃ Duration ┃
┡━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ a0eebc99 │ window_0 │ completed │ 2025-01-09 14:23:15│ 150     │ -        │ 12.45s   │
│ b1ffc88a │ window_1 │ completed │ 2025-01-09 14:23:28│ 200     │ -        │ 15.23s   │
│ c2ddd77b │ window_2 │ failed    │ 2025-01-09 14:23:45│ 180     │ -        │ 3.12s    │
└──────────┴──────────┴───────────┴────────────────────┴─────────┴──────────┴──────────┘
```

**Status Colors:**
- **Green** - `completed`
- **Red** - `failed`
- **Yellow** - `running`

### `egregora runs show <run_id>`

Show detailed information about a specific run.

**Usage:**
```bash
egregora runs show a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11  # Full UUID
egregora runs show a0eebc99                              # Prefix matching
```

**Output:**
```
╭──────────────────────────────────────────────────────╮
│              Run Details: window_2                    │
├──────────────────────────────────────────────────────┤
│ Run ID: a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11         │
│ Stage: window_2                                      │
│ Status: failed                                       │
│                                                      │
│ Timestamps:                                          │
│   Started:  2025-01-09 14:23:45+00:00               │
│   Finished: 2025-01-09 14:23:48+00:00               │
│   Duration: 3.12s                                    │
│                                                      │
│ Metrics:                                             │
│   Rows In:   180                                     │
│                                                      │
│ Fingerprints:                                        │
│   Code:   a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8...   │
│                                                      │
│ Error:                                               │
│   ValueError: Prompt exceeds model context limit    │
╰──────────────────────────────────────────────────────╯
```

## How It Works

### Window-Level Tracking

Every window processed by the pipeline is automatically tracked:

```python
# Automatic tracking in run_source_pipeline()
for window in windows_iterator:
    run_id = uuid.uuid4()
    started_at = datetime.now(UTC)

    # Record run start
    record_run(
        conn=runs_conn,
        run_id=run_id,
        stage=f"window_{window.window_index}",
        status="running",
        started_at=started_at,
        rows_in=window.size,
    )

    try:
        # Process window
        window_results = process_window_with_auto_split(window)

        # Record completion
        UPDATE runs SET status='completed', finished_at=?, duration_seconds=?

    except Exception as e:
        # Record failure
        UPDATE runs SET status='failed', error=?, finished_at=?, duration_seconds=?
```

**Status Transitions:**
1. `running` - Window processing started
2. `completed` - Window processed successfully
3. `failed` - Window processing failed (error recorded)

### Graceful Error Handling

Run tracking **never blocks pipeline execution**:

```python
try:
    record_run(...)  # Track run start
except Exception as e:
    logger.warning("Failed to record run start: %s", e)  # Log but continue

# Pipeline continues regardless of tracking failures
```

If the runs database is corrupted or inaccessible, the pipeline continues normally with warning logs.

## Debugging with Runs

### Finding Failed Runs

```bash
# View recent runs to spot failures
egregora runs tail --n 20

# Look for red "failed" status
```

### Investigating Failures

```bash
# Get detailed error info
egregora runs show <run_id>

# Check the "Error" section for full stack trace
```

### Common Failure Patterns

**1. Prompt Too Large**
```
Error: PromptTooLargeError: Estimated 150k tokens > 100k limit
```
**Solution**: Reduce `--step-size` or increase `--max-prompt-tokens`

**2. LLM API Errors**
```
Error: google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded
```
**Solution**: Wait for quota reset or use `--batch-threshold` to reduce concurrency

**3. Media Enrichment Failures**
```
Error: FileNotFoundError: Media file not found in ZIP
```
**Solution**: Check ZIP file integrity, ensure media files exist

## Performance Monitoring

### Tracking Duration

```bash
# View recent runs with durations
egregora runs tail --n 50

# Look for anomalies (unusually slow runs)
```

**Typical durations:**
- Small windows (50 messages): 5-10s
- Medium windows (100 messages): 10-20s
- Large windows (200 messages): 20-40s

### Identifying Bottlenecks

Long durations usually indicate:
1. **Large context windows** - Too many messages per window
2. **Slow LLM API** - Network issues or rate limiting
3. **Heavy enrichment** - Many URLs/media to process

## Integration with Checkpointing

**Status**: Planned (Priority D.2)

Future integration will enable:

### Content-Addressed Checkpointing

```python
# Calculate fingerprint
input_fingerprint = sha256(table_data + config + code_ref)

# Check if already processed
existing_run = SELECT * FROM runs
    WHERE input_fingerprint = ?
    AND status = 'completed'

if existing_run:
    # Skip processing, load cached output
    return load_checkpoint(existing_run.run_id)
```

### Deterministic Resume

```bash
# Re-run pipeline - automatically skips completed windows
egregora process export.zip --output=./my-blog

# Only processes new/changed data (detected via fingerprints)
```

## Multi-Tenant Isolation

**Status**: Implemented but not yet used

The `tenant_id` column supports multi-tenant deployments:

```python
# Record run with tenant
record_run(
    conn=runs_conn,
    run_id=run_id,
    stage="window_0",
    tenant_id="acme-corp",  # Tenant identifier
    ...
)

# Query runs for specific tenant
SELECT * FROM runs WHERE tenant_id = 'acme-corp'
```

## Observability Integration (Future)

**Status**: Planned (Priority D.2)

### OpenTelemetry Tracing

The `trace_id` column is reserved for OpenTelemetry integration:

```python
# Link run to distributed trace
record_run(
    conn=runs_conn,
    run_id=run_id,
    trace_id=current_span.trace_id,  # Link to OTel trace
    ...
)
```

### Metrics Export

Future support for exporting metrics:
- Prometheus metrics endpoint
- StatsD integration
- Custom webhooks

## Database Maintenance

### Cleaning Old Runs

```sql
-- Delete runs older than 30 days
DELETE FROM runs WHERE started_at < NOW() - INTERVAL '30 days';
```

### Vacuuming Database

```bash
# Compact database after deletions
duckdb .egregora/runs.duckdb "VACUUM;"
```

### Backup

```bash
# Backup runs database
cp .egregora/runs.duckdb .egregora/runs.duckdb.backup

# Restore from backup
cp .egregora/runs.duckdb.backup .egregora/runs.duckdb
```

## FAQ

**Q: Where is the runs database stored?**
A: `.egregora/runs.duckdb` in your site root directory.

**Q: Can I disable run tracking?**
A: Not currently. Tracking is lightweight and non-blocking.

**Q: How much disk space do runs use?**
A: ~1-2 KB per run. 1000 runs = ~1-2 MB.

**Q: Can I query the database directly?**
A: Yes! Use DuckDB CLI:
```bash
duckdb .egregora/runs.duckdb
```

**Q: What happens if runs.duckdb is deleted?**
A: It's automatically recreated on next pipeline run. No data loss for future runs.

**Q: Can I export runs to CSV?**
A: Yes:
```bash
duckdb .egregora/runs.duckdb "COPY runs TO 'runs.csv' (HEADER, DELIMITER ',')"
```

## Troubleshooting

### Database Locked

**Error**: `database is locked`

**Cause**: Another process is writing to runs.duckdb

**Solution**: Wait for other process to finish, or close other connections

### Schema Mismatch

**Error**: `column "duration_seconds" does not exist`

**Cause**: Old runs.duckdb from before schema update

**Solution**: Delete and recreate:
```bash
rm .egregora/runs.duckdb
egregora process export.zip  # Recreates with new schema
```

### Permission Denied

**Error**: `Permission denied: .egregora/runs.duckdb`

**Cause**: File permissions issue

**Solution**: Fix permissions:
```bash
chmod 644 .egregora/runs.duckdb
```

## Related Documentation

- [Architecture Roadmap](../../ARCHITECTURE_ROADMAP.md) - Priority D.1 specification
- [Checkpointing](../pipeline/checkpointing.md) - Content-addressed caching
- [Pipeline Runner](../pipeline/runner.md) - Main pipeline execution
- [Testing](../testing/runs-tracking.md) - Run tracking tests

## Changelog

**2025-01-09 - v1.0.0** (Priority D.1)
- Initial implementation
- Window-level tracking in pipeline
- CLI commands: `egregora runs tail`, `egregora runs show`
- Schema with 16 columns + 5 indexes
- Automatic duration calculation
- Error tracking with full messages
- 28 comprehensive tests
