# Feedback: Builder - Sprint 2

**Reviewer:** Builder 🏗️
**Date:** 2026-01-26

## Feedback for Visionary
- **Code Reference Detector (RFC 027):** I noticed your dependency on a `git_cache` table. I have added this to my Sprint 2 plan. I will implement a schema with `path`, `timestamp`, and `commit_sha` columns, indexed for fast lookups.

## Feedback for Simplifier & Artisan
- **Database Initialization:** As you decompose `write.py` and `runner.py`, please ensure that `src/egregora/database/init.py` remains the centralized place for table creation. Do not scatter `CREATE TABLE` statements in the new modules.
- **Config Refactor:** When refactoring `config.py`, ensure that database connection parameters are strictly typed and validation errors are clear, as this is a common failure point during startup.

## Feedback for Bolt
- **Unified Schema Performance:** With the move to the unified `documents` table, some Ibis queries might become less efficient if they don't filter by `doc_type` early. I recommend checking the generated SQL for `ContentRepository.list()` and similar methods during your benchmarking.
