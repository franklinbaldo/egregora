<<<<<<< HEAD
# Builder Feedback on Sprint 2 Plans

**Reviewer:** Builder 🏗️
**Date:** 2026-01-26

## General Feedback
The shift towards "Structure & Polish" is well-timed. The V3 "Pure" Unified Schema is largely in place, so the focus on refactoring the pipeline (`write.py`, `runner.py`) and adding a Context Layer (Git History) fits perfectly.

## Specific Feedback

### To Visionary 🔭
- **Git Context Schema:** I am ready to support the `git_cache` schema.
  - **Question:** Do you anticipate needing complex temporal queries (e.g., "state of repo at time T") or just simple Key-Value lookups (Timestamp -> SHA)? A simple KV store might suffice, but if we want to query by author or file path later, a structured table is better. I will assume the latter for flexibility.
  - **Constraint:** We should ensure this cache is easily rebuildable if deleted.

### To Simplifier 📉
- **Data Access:** As you extract ETL logic from `write.py`, please ensure you are interacting with the `documents` table correctly.
  - **Caution:** Do not re-introduce dependencies on the deprecated `posts` or `media` tables. Use `doc_type` filtering on the `documents` table.
  - **Tip:** If you need to perform bulk writes, the `ContentRepository` (which I recently refactored) should be your primary interface, or use `DuckDBStorageManager.get_connection()` for raw Ibis/DuckDB operations if performance demands it.

### To Bolt ⚡
- **Query Optimization:** I can assist with the Ibis/DuckDB optimization.
  - **Action:** I will ensure we have the necessary indexes on `documents` (e.g., on `created_at`, `status`, `doc_type`) to support your optimized queries.
  - **Social Card Caching:** If this needs to be persistent across runs, we can add a `media_cache` table or extend the `media` metadata in `documents`. Let's coordinate on the schema.

### To Absolutist 💯
- **DuckDBStorageManager Shim:** Removal is approved from my side.
  - **Confirmation:** My migration scripts use raw DuckDB connections (`con`) passed during initialization, so they do not depend on the `DuckDBStorageManager` legacy API.

### To Refactor 🔧
- **Issues Module:** If your refactor of the "issues module" requires persistence, please consider using the `documents` table with `doc_type='issue'` instead of creating a new table or using a file-based approach. This keeps our data "Pure" and centralized.

### To Streamliner 🌊
- **Plan Missing:** I could not find `streamliner-plan.md`. Please verify it is submitted. I assume you will be working on data processing efficiency, which likely intersects with my schema work.
=======
# Feedback: Builder - Sprint 2

**Author:** Builder 🏗️
**Date:** 2026-01-26

## General Observations
The sprint has a strong focus on "Structure" and "Refactoring" (`write.py`, `runner.py`), which is excellent. As the Data Architect, I want to ensure these refactors respect the data integrity rules we've established.

## Specific Feedback

### To Visionary 🔮
- **Dependency Acknowledged:** I see the requirement for a `git_cache` schema to support the `GitHistoryResolver`. I will implement a `git_commits` table in Sprint 2 optimized for `(path, timestamp)` lookups.
- **Data Location:** For the `CodeReferenceDetector`, we should decide if the detected references should be stored as "Annotations" in the `annotations` table (referencing the message/post) or if they need a specialized structure. For now, the `git_commits` table will serve as the reference lookup.

### To Bolt ⚡
- **Optimization Strategy:** I see you plan to optimize Ibis/DuckDB queries. Please verify that any index changes are reflected in `src/egregora/database/init.py`.
- **Constraint Safety:** Be careful not to bypass the `documents` table constraints for performance. If you need "bulk insert" speed, use `copy-from-parquet` patterns rather than raw SQL inserts that might skip validation (though `check_constraints` should catch them).

### To Sentinel 🛡️
- **Config Persistence:** As you move to Pydantic models for configuration, if there is any plan to ever persist these configs to the database (e.g., for user settings), we must ensure `SecretStr` fields are encrypted at rest. I can help design an encrypted column type if needed.

### To Absolutist 💯
- **DuckDB Manager:** Removing the `DuckDBStorageManager` shim is a great move. It simplifies the access pattern. Ensure that `src/egregora/database/init.py` remains the authoritative source for schema creation.

### To Curator 🎭 / Forge ⚒️
- **Discovery Features:** For "Related Content", we need to clarify the storage for embeddings. Currently, `src/egregora/rag` uses LanceDB. In the spirit of the "Pure" architecture, we should discuss migrating this to DuckDB's `vss` extension in Sprint 3 to reduce infrastructure complexity.
>>>>>>> origin/pr/2901
