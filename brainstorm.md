# Egregora Brainstorm & Future Features

This document captures features and ideas that were removed during simplification or are planned for future implementation.

## Removed Features (Available for Future Reimplementation)

These features were removed to reduce complexity and maintenance burden. They represent good ideas that could be reimplemented when there's clear user demand and proper architectural foundation.

### Privacy & PII Protection System

**Removed**: 2025-12-13 (Phase 3)
**Lines Removed**: ~600 lines
**Complexity**: High

#### What It Was

A two-level privacy system combining structural anonymization with LLM-native PII prevention:

1. **Structural Privacy**:
   - Deterministic UUID mapping for authors (via uuid.uuid5)
   - Configurable author strategies: `uuid_mapping`, `pseudonym`, `none`
   - Mention privacy handling
   - WhatsApp media reference anonymization

2. **LLM-Native PII Prevention**:
   - Prompt injection for writer and enricher agents
   - Configurable scope: `all_pii`, `identifiers_only`, `none`
   - Real-time PII detection guidance in prompts
   - Privacy markers in generated content

#### Why It Was Removed

- **Over-engineered for current use case**: Most users run locally and trust their own data
- **Maintenance burden**: Complex state management across multiple adapters
- **Unclear ROI**: No evidence of user demand for this level of privacy
- **Architecture confusion**: Privacy scattered across input adapters, agents, and prompts

#### How to Reimplement Better

**When**: When there's demonstrated need for privacy (e.g., enterprise deployments, shared hosting)

**Better Approach**:
- Start with structural privacy only (UUIDs) as a configuration option
- Keep privacy transformation in input adapters only (don't leak into agents)
- Use middleware pattern instead of scattered privacy code
- Add LLM-based PII detection only if structural privacy proves insufficient
- Make it truly optional - zero privacy code runs if disabled

**References**:
- Deleted code: `src/egregora/privacy/` (commit fa99223)
- Configuration: See `PrivacySettings` in commit history
- Tests: `tests/unit/privacy/` and `tests/e2e/privacy/`

---

### CLI Commands: `config` and `runs`

**Removed**: 2025-12-13 (Phase 3)
**Lines Removed**: ~400 lines
**Complexity**: Medium

#### What It Was

Two CLI commands for managing Egregora:

1. **`egregora config`**:
   - View current configuration
   - Validate config files
   - Show config file location

2. **`egregora runs`**:
   - List all pipeline runs
   - Show run details
   - Query run history
   - Filter by date/status

#### Why It Was Removed

- **Low usage**: Most users interact via `egregora write` and direct file editing
- **Redundant**: Config is a simple YAML file that users can edit directly
- **Database coupling**: Runs command required DuckDB queries that duplicated storage logic
- **Maintenance burden**: Two additional command surfaces to test and support

#### How to Reimplement Better

**When**: When users request workflow management features (run tracking, comparison, rollback)

**Better Approach**:
- Don't reimplement `config` - YAML editing is sufficient
- Reimplement `runs` as part of a broader **workflow management system**:
  - `egregora history` - show recent runs
  - `egregora status <run-id>` - show run details
  - `egregora diff <run-id> <run-id>` - compare runs
  - `egregora rollback <run-id>` - restore to previous state
- Use unified storage interface instead of direct DuckDB queries
- Add run tagging, notes, and search

**References**:
- Deleted code: `src/egregora/cli/config.py`, `src/egregora/cli/runs.py` (commit fa99223)
- Preserved logic: `SimpleDuckDBStorage` in `src/egregora/database/utils.py` (used by `top` and `show` commands)

---

### Multiple Output Formats: Parquet/JSON Export

**Removed**: 2025-12-13 (Phase 3)
**Lines Removed**: ~200 lines
**Complexity**: Medium

#### What It Was

Parquet adapter for exporting egregora data in columnar format:

- Posts, profiles, journals as Parquet tables
- Metadata preservation
- Analytics-friendly schema
- JSON export via Parquet conversion

#### Why It Was Removed

- **Single use case**: MkDocs is the primary output format (blog generation)
- **Unclear user need**: No evidence users want Parquet export
- **Maintenance burden**: Another adapter to test and maintain
- **Wrong layer**: If analytics needed, query DuckDB directly (already Parquet-compatible)

#### How to Reimplement Better

**When**: When users request data export for analytics, archival, or migration

**Better Approach**:
- Don't create output adapters - **expose the DuckDB database directly**:
  - DuckDB natively exports to Parquet: `COPY (SELECT * FROM posts) TO 'posts.parquet'`
  - JSON export: `COPY (SELECT * FROM posts) TO 'posts.json'`
  - CSV: `COPY (SELECT * FROM posts) TO 'posts.csv'`
- Add `egregora export` command that wraps DuckDB export:
  ```bash
  egregora export posts --format parquet --output posts.parquet
  egregora export profiles --format json --output profiles.json
  ```
- Let users query DuckDB directly for custom exports:
  ```bash
  duckdb .egregora/egregora.db "SELECT * FROM posts WHERE date > '2024-01-01'"
  ```

**Why This Is Better**:
- Zero maintenance (DuckDB handles all formats)
- More flexible (users can query before export)
- Consistent schema (IR schema from DuckDB, not custom mapping)

**References**:
- Deleted code: `src/egregora/output_adapters/parquet/` (commit fa99223)
- DuckDB export docs: https://duckdb.org/docs/sql/statements/copy

---

### Multiple Search Modes: Keyword & Hybrid Search

**Removed**: 2025-12-13 (FEATURES.md cleanup)
**Lines Removed**: Documentation only (code never implemented)
**Complexity**: High (if implemented)

#### What It Was

Documented search modes in FEATURES.md:

1. **Semantic search** (implemented): Vector similarity via LanceDB
2. **Keyword search** (never implemented): Traditional full-text search
3. **Hybrid search** (never implemented): Combination of semantic + keyword

#### Why It Was Removed

- **Only semantic search implemented**: Keyword/hybrid were aspirational
- **Unclear benefit**: Semantic search works well for conversation data
- **Complexity**: Hybrid search requires tuning weights, re-ranking, etc.

#### How to Reimplement Better

**When**: When users report semantic search missing relevant results

**Better Approach**:
- **Phase 1**: Add keyword fallback when semantic search fails
  - Use DuckDB's full-text search (built-in FTS extension)
  - Only invoke if semantic search returns < N results

- **Phase 2**: Add hybrid search if needed
  - Use DuckDB FTS for keyword scoring
  - Use LanceDB for semantic scoring
  - Reciprocal Rank Fusion (RRF) for combining results
  - Single `hybrid_weight` parameter (0.0 = keyword only, 1.0 = semantic only)

**References**:
- DuckDB FTS: https://duckdb.org/docs/extensions/full_text_search
- RRF algorithm: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf

---

### Advanced Rate Limiting: Concurrent & Daily Limits

**Removed**: 2025-12-13 (FEATURES.md cleanup)
**Lines Removed**: Documentation only (code never fully implemented)
**Complexity**: Medium

#### What It Was

Multi-tier rate limiting system:

1. **Per-second limits** (implemented): Prevent API throttling
2. **Concurrent request limits** (never implemented): Max parallel requests
3. **Daily quotas** (never implemented): Max requests per 24h

#### Why It Was Removed

- **Only per-second implemented**: Others were planned but not built
- **Insufficient value**: Per-second limits solve the API throttling problem
- **Complexity**: Requires distributed state tracking for concurrent/daily limits

#### How to Reimplement Better

**When**: When users hit API quota limits or want cost control

**Better Approach**:
- **Don't add concurrent limits**: Per-second already prevents overwhelming APIs
- **Add daily quotas only if needed**:
  - Track in DuckDB: `rate_limits` table with (date, endpoint, count)
  - Check before API call: `SELECT sum(count) FROM rate_limits WHERE date = today()`
  - Fail fast if quota exceeded
  - Reset at midnight UTC
- **Add cost tracking instead**:
  - Track token usage per run
  - Estimate cost using model pricing
  - Alert when approaching budget
  - Show cost breakdown by model/agent

**References**:
- Current rate limiting: `src/egregora/rag/embedding_router.py` (per-second only)
- Gemini pricing: https://ai.google.dev/pricing

---

### Configuration Cascade: CLI Flags Override System

**Removed**: 2025-12-13 (FEATURES.md cleanup)
**Lines Removed**: Documentation only (code partially implemented)
**Complexity**: Low

#### What It Was

Configuration priority system:

1. CLI flags (highest priority)
2. Environment variables
3. `config.yml` file (lowest priority)

#### Why It Was Removed

- **Two-tier sufficient**: Env vars override YAML is enough
- **CLI flags rarely used**: Users prefer editing config.yml
- **Complexity**: Three-tier override adds mental overhead

#### How to Reimplement Better

**When**: When users request one-off config changes without editing files

**Better Approach**:
- Keep two-tier: env vars > YAML
- Add `--config-override` flag for one-off changes:
  ```bash
  egregora write --config-override rag.top_k=10
  egregora write --config-override models.writer=gemini-pro
  ```
- Use dotted path notation to modify nested config
- Don't persist overrides (one-time only)

---

## Future Feature Ideas

### Not Yet Implemented

Ideas that have never been implemented but could add value:

#### Incremental Processing

- **Problem**: `egregora write` reprocesses entire chat history
- **Solution**: Track processed messages, only process new ones
- **Complexity**: Medium (requires message deduplication, state tracking)
- **Value**: Faster rebuilds, better for large datasets

#### Multi-Source Support

- **Problem**: Only WhatsApp currently supported
- **Solution**: Adapters for Telegram, Slack, Discord, etc.
- **Complexity**: Medium per adapter (each has different export format)
- **Value**: Expand user base beyond WhatsApp users

#### Theme Customization

- **Problem**: MkDocs Material is hardcoded
- **Solution**: Theme system with pluggable templates
- **Complexity**: High (need template abstraction, variable system)
- **Value**: Users can match blog to personal brand

---

## How to Use This Document

### For Contributors

When removing features:
1. Document what was removed, why, and how to do it better
2. Link to relevant commits and code
3. Capture architectural lessons learned

### For Future Reimplementation

When considering reimplementing a feature:
1. Read this section first to understand why it was removed
2. Follow the "Better Approach" if provided
3. Verify user demand before building (avoid speculative features)
4. Update this doc if you learn something new

### For Users

This document shows the project's evolution and philosophy:
- **Removed features**: We prioritize simplicity over feature count
- **Better approaches**: We learn from past mistakes
- **Future ideas**: We're open to expansion when there's clear value
