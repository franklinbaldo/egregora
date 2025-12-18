# Builder's Journal

## 2025-05-23 - Unify Data Model
**Obstacle:** The task is to "Migrate the DuckDB `documents` table to fully support the V3 `Entry` schema".
I need to check if the `UNIFIED_SCHEMA` in `src/egregora/database/ir_schema.py` matches `Entry` in `src/egregora_v3/core/types.py`.
It seems `UNIFIED_SCHEMA` already has `doc_type` and `extensions`.
However, the `doc_type` in `UNIFIED_SCHEMA` is `dt.String`, while `Entry` has `doc_type: DocumentType`.
`Entry` also has `extensions: dict[str, Any]` and `internal_metadata: dict[str, Any]`.
`UNIFIED_SCHEMA` has them as `dt.JSON`.

The task specifically asks to:
1. Add `doc_type` column (ENUM) to distinguish `message`, `post`, `profile`, `log`.
2. Add `extensions` column (JSON) for Atom extensions.
3. Create a migration script to alter existing tables.

Since `UNIFIED_SCHEMA` seems to be updated already (based on the `[x]` checkmark in TODO.md for the first subtask), the remaining work is likely to ensure the actual DuckDB table matches this schema if it was created with an older schema.

The "Create a migration script" part is key. I need to verify if the existing `documents` table (if any) is being migrated or if I need to write a migration.

Also, the TODO mentions "Add `doc_type` column (ENUM)". `UNIFIED_SCHEMA` uses `dt.String`. I should verify if I can/should use an ENUM type in DuckDB via Ibis, or if String is the intended implementation for the ENUM. Given DuckDB supports ENUMs, maybe I should try to use that if possible, but Ibis might abstract it. The task might effectively mean "ensure the column exists and stores these values".

My plan:
1.  Verify `UNIFIED_SCHEMA` correctness against `Entry` fields.
2.  Create a test that attempts to insert an `Entry` object into a table created with `UNIFIED_SCHEMA`.
3.  Implement/Check the migration logic. If `create_table_if_not_exists` doesn't handle schema evolution (it usually doesn't), I might need a migration function.

**Solution:**
I will create a test `tests/test_schema_migration.py` that simulates an old schema (without `doc_type` and `extensions`) and tries to migrate it to the new `UNIFIED_SCHEMA`.
This will reveal if I have a migration mechanism. If not, I will implement one.
