# Egregora Brainstorm & Future Development

This document captures:
1. **Removed Features**: Features that were simplified away, with guidance for future reimplementation
2. **Ideas from Open PRs**: Valuable concepts from closed PRs worth preserving

---

# Part 1: Removed Features (Available for Reimplementation)

These features were removed to reduce complexity and maintenance burden. They represent good ideas that could be reimplemented when there's clear user demand and proper architectural foundation.

## 1. Privacy & PII Protection System

**Removed**: 2025-12-13 (Phase 3)
**Lines Removed**: ~600 lines
**Complexity**: High

### What It Was

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

### Why It Was Removed

- **Over-engineered for current use case**: Most users run locally and trust their own data
- **Maintenance burden**: Complex state management across multiple adapters
- **Unclear ROI**: No evidence of user demand for this level of privacy
- **Architecture confusion**: Privacy scattered across input adapters, agents, and prompts

### How to Reimplement Better

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

## 2. CLI Commands: `config` and `runs`

**Removed**: 2025-12-13 (Phase 3)
**Lines Removed**: ~400 lines
**Complexity**: Medium

### What It Was

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

### Why It Was Removed

- **Low usage**: Most users interact via `egregora write` and direct file editing
- **Redundant**: Config is a simple YAML file that users can edit directly
- **Database coupling**: Runs command required DuckDB queries that duplicated storage logic
- **Maintenance burden**: Two additional command surfaces to test and support

### How to Reimplement Better

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

## 3. Multiple Output Formats: Parquet/JSON Export

**Removed**: 2025-12-13 (Phase 3)
**Lines Removed**: ~200 lines
**Complexity**: Medium

### What It Was

Parquet adapter for exporting egregora data in columnar format:

- Posts, profiles, journals as Parquet tables
- Metadata preservation
- Analytics-friendly schema
- JSON export via Parquet conversion

### Why It Was Removed

- **Single use case**: MkDocs is the primary output format (blog generation)
- **Unclear user need**: No evidence users want Parquet export
- **Maintenance burden**: Another adapter to test and maintain
- **Wrong layer**: If analytics needed, query DuckDB directly (already Parquet-compatible)

### How to Reimplement Better

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
- Deleted code: `src/egregora/output_sinks/parquet/` (commit fa99223)
- DuckDB export docs: https://duckdb.org/docs/sql/statements/copy

---

## 4. Multiple Search Modes: Keyword & Hybrid Search

**Removed**: 2025-12-13 (FEATURES.md cleanup)
**Lines Removed**: Documentation only (code never implemented)
**Complexity**: High (if implemented)

### What It Was

Documented search modes in FEATURES.md:

1. **Semantic search** (implemented): Vector similarity via LanceDB
2. **Keyword search** (never implemented): Traditional full-text search
3. **Hybrid search** (never implemented): Combination of semantic + keyword

### Why It Was Removed

- **Only semantic search implemented**: Keyword/hybrid were aspirational
- **Unclear benefit**: Semantic search works well for conversation data
- **Complexity**: Hybrid search requires tuning weights, re-ranking, etc.

### How to Reimplement Better

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

## 5. Advanced Rate Limiting: Concurrent & Daily Limits

**Removed**: 2025-12-13 (FEATURES.md cleanup)
**Lines Removed**: Documentation only (code never fully implemented)
**Complexity**: Medium

### What It Was

Multi-tier rate limiting system:

1. **Per-second limits** (implemented): Prevent API throttling
2. **Concurrent request limits** (never implemented): Max parallel requests
3. **Daily quotas** (never implemented): Max requests per 24h

### Why It Was Removed

- **Only per-second implemented**: Others were planned but not built
- **Insufficient value**: Per-second limits solve the API throttling problem
- **Complexity**: Requires distributed state tracking for concurrent/daily limits

### How to Reimplement Better

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

## 6. Configuration Cascade: CLI Flags Override System

**Removed**: 2025-12-13 (FEATURES.md cleanup)
**Lines Removed**: Documentation only (code partially implemented)
**Complexity**: Low

### What It Was

Configuration priority system:

1. CLI flags (highest priority)
2. Environment variables
3. `config.yml` file (lowest priority)

### Why It Was Removed

- **Two-tier sufficient**: Env vars override YAML is enough
- **CLI flags rarely used**: Users prefer editing config.yml
- **Complexity**: Three-tier override adds mental overhead

### How to Reimplement Better

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

# Part 2: Ideas from Open PRs

Valuable ideas and concepts from PRs that were closed due to conflicts or scope issues, but whose underlying intentions are worth preserving for future development.

## 1. WhatsApp Parser Performance Optimization
**Source:** PR #1188 (Bolt: Add caching to WhatsApp parser)
**Priority:** Medium

### Idea
Add `functools.lru_cache` to frequently-called date/time parsing functions in WhatsApp adapter.

### Rationale
- WhatsApp chat logs contain thousands of messages with repeated date strings
- `dateutil.parser` is computationally expensive (uses heuristics to guess formats)
- Caching can reduce parsing operations from N (total messages) to D (unique days)

### Implementation Concept
```python
from functools import lru_cache

@lru_cache(maxsize=1024)
def _parse_message_date(date_str: str) -> date:
    return dateutil.parser.parse(date_str).date()

@lru_cache(maxsize=256)
def _parse_message_time(time_str: str) -> time:
    return dateutil.parser.parse(time_str).time()
```

Good performance win for large chat exports.

---

## 2. Unified Content Structure with Categories
**Source:** PR #1183 (Unify documents into single posts folder)
**Priority:** Low (Already implemented via unified output structure)

### Idea
Put all document types (posts, profiles, journal, enrichment) in a single `posts/` folder and differentiate using MkDocs Material's category feature.

### Rationale
- Simpler file structure - one folder for all content
- Leverages MkDocs Material's built-in category navigation
- Reduces path handling complexity

### Current State
Already partially implemented in unified output structure (all content goes to posts/).

---

## 3. Agent Read Status Tracking
**Source:** PR #1169 (Unified Entries Table and Agent Read Status)
**Priority:** High - Essential for v3 multi-agent architecture

### Idea
Track which agents have read which entries, enabling multi-agent workflows where agents only process new content.

### Rationale
- Prevents reprocessing of already-handled content
- Enables agent "memory" across runs
- Supports incremental processing

### Implementation Concept
```sql
CREATE TABLE agent_read_status (
    agent_id VARCHAR,
    entry_id VARCHAR,
    read_at TIMESTAMP,
    PRIMARY KEY (agent_id, entry_id)
);
```

### Additional Idea: Feed ID
Add `feed_id` to Entry model to group entries by source (e.g., "whatsapp-export-1", "twitter-archive-2").

---

## 4. Demo Generation Automation
**Source:** PRs #1163, #1166, #1162
**Priority:** Medium

### Idea
Automated script to regenerate demo blog content via CLI, integrated into CI for validation.

### Rationale
- Ensures demo site always works with current codebase
- Catches regressions in blog generation pipeline
- Provides template for new users

### Implementation Concept
```python
# dev_tools/generate_demo.py
def generate_demo():
    # 1. Validate API key upfront (fail-fast)
    # 2. Create temp directory
    # 3. Run egregora init + write
    # 4. Verify output structure
    # 5. Optionally build and serve
```

Good for CI/CD and onboarding.

---

## 5. Upfront API Key Validation
**Source:** PR #1162 (Gemini API key validation)
**Priority:** High - Simple improvement with significant UX benefit

### Idea
Validate Gemini API key at startup before running expensive operations.

### Rationale
- Fail fast with clear error message
- Avoid deep pipeline failures with cryptic errors
- Better UX for new users

### Implementation Concept
```python
def validate_gemini_key(api_key: str) -> None:
    """Validate API key with lightweight count_tokens call."""
    try:
        client = genai.GenerativeModel('gemini-1.5-flash')
        client.count_tokens("test")
    except Exception as e:
        raise ValueError(f"Invalid Gemini API key: {e}")
```

---

## 6. Enhanced Embedding Error Reporting
**Source:** PR #1162
**Priority:** High - Critical for debugging API issues

### Idea
Capture and bubble up detailed API error text when embedding requests fail.

### Current Problem
Embedding failures show generic HTTP errors without the actual API response.

### Implementation Concept
```python
try:
    response = client.embed(...)
except httpx.HTTPStatusError as e:
    # Parse and include response body in error
    error_detail = e.response.text or e.response.json()
    raise EmbeddingError(f"Embedding failed: {error_detail}") from e
```

---

## 7. Blog as Homepage Default
**Source:** PR #1163
**Priority:** Low - User preference, can be configured

### Idea
Set the generated blog feed as the homepage instead of a static landing page.

### Rationale
- Users want to see content immediately
- Blog feed is the primary value of the generated site
- Static landing pages often feel empty

---

## 8. Relative URL Generation
**Source:** PR #1168
**Priority:** Low - Already addressed in current implementation

### Idea
Enforce relative URL generation for all internal links to improve portability.

### Current State
Already implemented in URL conventions.

---

# Part 3: Future Feature Ideas

Ideas that have never been implemented but could add value:

## Incremental Processing

- **Problem**: `egregora write` reprocesses entire chat history
- **Solution**: Track processed messages, only process new ones
- **Complexity**: Medium (requires message deduplication, state tracking)
- **Value**: Faster rebuilds, better for large datasets

## Multi-Source Support

- **Problem**: Only WhatsApp currently supported
- **Solution**: Adapters for Telegram, Slack, Discord, etc.
- **Complexity**: Medium per adapter (each has different export format)
- **Value**: Expand user base beyond WhatsApp users

## Theme Customization

- **Problem**: MkDocs Material is hardcoded
- **Solution**: Theme system with pluggable templates
- **Complexity**: High (need template abstraction, variable system)
- **Value**: Users can match blog to personal brand

---

# Summary: Implementation Priorities

## High Priority (Should implement soon)
1. **API key validation** - Simple, high UX impact
2. **Enhanced embedding errors** - Critical for debugging
3. **Agent read status** - Essential for v3

## Medium Priority (Good to have)
4. **Parser caching** - Performance win
5. **Demo generation** - CI/CD improvement

## Low Priority (Consider later)
6. **Unified content structure** - Already addressed
7. **Blog as homepage** - User preference
8. **Relative URLs** - Already addressed

---

# How to Use This Document

## For Contributors

When removing features:
1. Document what was removed, why, and how to do it better
2. Link to relevant commits and code
3. Capture architectural lessons learned

## For Future Reimplementation

When considering reimplementing a feature:
1. Read this section first to understand why it was removed
2. Follow the "Better Approach" if provided
3. Verify user demand before building (avoid speculative features)
4. Update this doc if you learn something new

## For Users

This document shows the project's evolution and philosophy:
- **Removed features**: We prioritize simplicity over feature count
- **Better approaches**: We learn from past mistakes
- **Future ideas**: We're open to expansion when there's clear value

---

*Last Updated: 2025-12-14*
*Part 1 (Removed Features): Generated from Phase 3 simplification*
*Part 2 (Open PRs): Generated 2025-12-11 from PR review session*
