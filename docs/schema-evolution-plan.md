# Schema Evolution Plan

**Status**: Active
**Owner**: Builder
**Last Updated**: 2026-01-30

## Philosophy: Structure Before Scale

- **Invalid States Unrepresentable**: Use database constraints (NOT NULL, CHECK, FK) to enforce business rules.
- **Append-Only Core**: Core tables (`documents`, `messages`) are append-only. Updates are new versions.
- **Strict Typing**: Use specific types (UUID, TIMESTAMP WITH TIME ZONE) over generic strings.

## Current State: V3 "Pure" Architecture

The system is transitioning to a "Pure" architecture with a unified `documents` table and specialized support tables.

### Core Tables

1.  **`documents`** (Unified)
    -   Stores Posts, Profiles, Journals, and Media metadata.
    -   Discriminator: `doc_type` column.
    -   Schema: `UNIFIED_SCHEMA` (Union of all specialized schemas).

2.  **`messages`**
    -   Ingestion staging buffer.
    -   Tracks source lineage (`event_id`, `source`, `thread_id`).

3.  **`annotations`**
    -   Stores annotations on other documents.

4.  **`tasks`**
    -   Async background jobs.

### Specialized Support Tables

1.  **Git Context Layer** (Implemented Jan 2026)
    -   **`git_commits`**: Stores file modification history and stats.
    -   **`git_refs`**: Stores snapshot of git references (tags, branches).

2.  **Ranking System** (Implemented Jan 2026)
    -   **`elo_ratings`**: Current Elo ratings for items.
    -   **`comparison_history`**: Log of pairwise comparisons.

3.  **Caching** (Implemented Jan 2026)
    -   **`asset_cache`**: Caching layer for external resources (images, fonts).

## 2. Planned Improvements

### 2.1 Enforce `doc_type` Integrity in `documents`

**Problem**: The `documents` table is sparse/wide. Columns like `title` or `filename` are nullable because they don't apply to all types. However, a "Post" *must* have a title. Currently, the database allows a "Post" with NULL title.

**Solution**: Add conditional CHECK constraints to `documents` table. (Completed)

```sql
CHECK (
    (doc_type = 'post' AND title IS NOT NULL AND slug IS NOT NULL AND status IS NOT NULL) OR
    ...
)
```

### 2.2 Foreign Key Enforcement

-   `annotations.parent_id` should reference `documents.id`.
-   `tasks.run_id` (if re-introduced) should reference a run table.

### 2.3 Migration Strategy

-   Use "Create-Copy-Swap" for DuckDB table migrations.
-   Ensure migrations are idempotent.

## 3. Backlog & History

-   [x] Add constraints to `documents` table (Completed Jan 2026).
-   [x] Migrate `ContentRepository` to use `documents` table (Completed Jan 2026).
-   [x] Verify `media` table usage and consolidate (Completed Jan 2026).
-   [x] Add indexes to `documents` table (`doc_type`, `slug`, `created_at`, `status`) (Completed Jan 2026).
-   [x] Implement `Git Context` schemas (`git_commits`, `git_refs`) (Completed Jan 2026).
-   [x] Implement `Elo` ranking schemas (Completed Jan 2026).
-   [x] Implement `Asset Cache` schema (Completed Jan 2026).
-   [ ] Add index on `asset_cache.expires_at` for cleanup (Planned).
-   [ ] Enforce strict types in `messages` table (Planned).
