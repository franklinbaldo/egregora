# Schema Evolution Plan

**Status**: Draft
**Owner**: Builder
**Last Updated**: 2026-01-26

## Philosophy: Structure Before Scale

- **Invalid States Unrepresentable**: Use database constraints (NOT NULL, CHECK, FK) to enforce business rules.
- **Append-Only Core**: Core tables (`documents`, `messages`) are append-only. Updates are new versions.
- **Strict Typing**: Use specific types (UUID, TIMESTAMP WITH TIME ZONE) over generic strings.

## Current State: V3 "Pure" Architecture

The system is transitioning to a "Pure" architecture with a unified `documents` table.

### Core Tables

1.  **`documents`** (Unified)
    -   Stores Posts, Profiles, Journals, and Media metadata.
    -   Discriminator: `doc_type` column.
    -   Schema: `UNIFIED_SCHEMA` (Union of all specialized schemas).

2.  **`media`** (Deprecated/Removed)
    -   Media metadata is now stored in `documents` with `doc_type='media'`.
    -   Legacy table removed in Jan 2026.

3.  **`annotations`**
    -   Stores annotations on other documents.
    -   Separate table.

4.  **`tasks`**
    -   Async background jobs.

5.  **`messages`**
    -   Ingestion staging buffer.

6.  **Git Context Layer**
    -   **`git_commits`**: Stores file modification history.
    -   **`git_refs`**: Stores snapshot of git references (tags, branches).

## 2. Planned Improvements

### 2.1 Enforce `doc_type` Integrity in `documents`

**Problem**: The `documents` table is sparse/wide. Columns like `title` or `filename` are nullable because they don't apply to all types. However, a "Post" *must* have a title. Currently, the database allows a "Post" with NULL title.

**Solution**: Add conditional CHECK constraints to `documents` table.

```sql
CHECK (
    (doc_type = 'post' AND title IS NOT NULL AND slug IS NOT NULL AND status IS NOT NULL) OR
    (doc_type = 'profile' AND title IS NOT NULL AND subject_uuid IS NOT NULL) OR
    (doc_type = 'journal' AND title IS NOT NULL AND window_start IS NOT NULL AND window_end IS NOT NULL) OR
    (doc_type = 'media' AND filename IS NOT NULL) OR
    (doc_type NOT IN ('post', 'profile', 'journal', 'media')) -- Fallback/Extensions
)
```

### 2.2 Foreign Key Enforcement

-   `annotations.parent_id` should reference `documents.id`.
-   `tasks.run_id` (if re-introduced) should reference a run table.

### 2.3 Migration Strategy

-   Use "Create-Copy-Swap" for DuckDB table migrations.
-   Ensure migrations are idempotent.

## 3. Backlog

-   [x] Add constraints to `documents` table (Completed Jan 2026).
-   [x] Migrate `ContentRepository` to use `documents` table (Completed Jan 2026).
-   [x] Verify `media` table usage and consolidate (Completed Jan 2026).
-   [x] Add indexes to `documents` table (`doc_type`, `slug`, `created_at`, `status`) (Completed Jan 2026).
