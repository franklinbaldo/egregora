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
