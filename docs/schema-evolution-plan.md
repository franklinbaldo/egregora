# Schema Evolution Plan 🏗️

This document outlines the strategy for evolving the Egregora database schema. We follow the philosophy of **Structure Before Scale**, ensuring that invalid states are unrepresentable at the database level.

## Philosophy

1.  **Database as the Source of Truth**: The database should enforce data integrity, not just the application layer.
2.  **Append-Only Core**: Core tables should be append-only where possible to preserve history and simplify synchronization.
3.  **Strict Typing**: Use specific types (e.g., `UUID`, `TIMESTAMPTZ`, `JSON`) instead of generic text.
4.  **Constraints**: liberally use `NOT NULL`, `CHECK`, `UNIQUE`, and Foreign Keys.

## Current Schema State (V3)

The current schema (V3) is defined in `src/egregora/database/schemas.py`. It includes:

-   **Posts**: Blog posts with status workflow (`draft` -> `published`).
-   **Profiles**: User/Agent profiles.
-   **Media**: Metadata for binary assets.
-   **Journals**: Time-windowed session logs.
-   **Tasks**: Async background task tracking.
-   **Annotations**: Comments and notes on other entities.

### Enforced Constraints

-   `posts.status`: CHECK (`draft`, `published`, `archived`)
-   `tasks.status`: CHECK (`pending`, `processing`, `completed`, `failed`, `superseded`)
-   `tasks.task_type`: CHECK (`generate_banner`, `update_profile`, `enrich_media`)
-   `media.media_type`: CHECK (`image`, `video`, `audio`)
-   `annotations.parent_type`: CHECK (`message`, `post`, `annotation`)

## Roadmap & Planned Improvements

| Priority | Entity | Change | Rationale | Status |
| :--- | :--- | :--- | :--- | :--- |
| High | Journals | `CHECK (window_end >= window_start)` | Prevent invalid time ranges. | 📝 Planned |
| Medium | Profiles | `CHECK (length(title) > 0)` | Ensure profiles have a name. | ⏳ Pending |
| Medium | All | Foreign Keys | Enforce referential integrity (e.g., `posts.authors` -> `profiles.id`). | ⏳ Pending |
| Low | Media | `UNIQUE (phash)` | Prevent duplicate media (if strict dedup is desired). | ⏳ Pending |

## Migration Strategy

Since DuckDB has limited support for `ALTER TABLE` (specifically adding constraints), migrations often require a "Create-Copy-Swap" strategy:

1.  Create `new_table` with the desired schema and constraints.
2.  Copy data from `old_table` to `new_table`.
3.  Drop `old_table`.
4.  Rename `new_table` to `old_table`.

This is handled in `src/egregora/database/migrations.py`.
