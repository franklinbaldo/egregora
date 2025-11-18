# IR Schema Lockfiles

This directory contains **generated** lockfiles for the Intermediate Representation (IR) schema used by Egregora's adapter system.

## Single Source of Truth

**Python schema is the source of truth:**
`src/egregora/database/validation.py:IR_MESSAGE_SCHEMA`

All SQL and JSON lockfiles in this directory are **auto-generated** from the Python schema definition.

## Purpose

Schema lockfiles serve two purposes:

1. **Validation**: CI checks these lockfiles to detect unintended schema drift
2. **Documentation**: Human-readable SQL shows the expected table structure

## Files

### `ir_v1.sql`
Auto-generated DuckDB CREATE TABLE statement for IR v1.
**DO NOT EDIT MANUALLY** - regenerated from `IR_MESSAGE_SCHEMA`.

### `ir_v1.json`
Auto-generated JSON representation of the schema for CI validation.
**DO NOT EDIT MANUALLY** - regenerated from `IR_MESSAGE_SCHEMA`.

## Workflow

### Checking for Drift

Run the validation script to verify lockfiles match the Python schema:

```bash
python scripts/check_ir_schema.py
```

This compares `IR_MESSAGE_SCHEMA` against the generated lockfiles.

### Making Schema Changes

**All schema changes happen in Python code** - lockfiles are regenerated automatically.

1. **Consider breaking changes**: If this is a breaking change, increment to IR v2

2. **Update Python schema**: Modify `src/egregora/database/validation.py:IR_MESSAGE_SCHEMA`

3. **Update nullable columns**: If changing nullability, update `NULLABLE_COLUMNS` in `generate_ir_sql_ddl()`

4. **Regenerate lockfiles**:
   ```bash
   python scripts/regenerate_schema_lockfiles.py
   ```

5. **Verify no drift**:
   ```bash
   python scripts/check_ir_schema.py
   ```

6. **Update adapters**: Modify all input adapters to conform to new schema

7. **Update tests**: Ensure `tests/unit/test_ir_validation.py` covers new schema requirements

## CI Integration

The lockfile validation runs automatically in CI via `tests/unit/test_ir_schema_lockfile.py::test_check_ir_schema_script_passes`.

To add as a standalone CI check:

```yaml
# .github/workflows/ci.yml
- name: Validate IR Schema Lockfile
  run: python scripts/check_ir_schema.py
```

## Version History

- **v1.0.0** (2025-01-08): Initial IR v1 lockfile
  - 15 columns: event_id, tenant_id, source, thread_id, msg_id, ts, author_raw, author_uuid, text, media_url, media_type, attrs, pii_flags, created_at, created_by_run
  - Multi-tenancy support
  - Privacy boundary (author_raw → author_uuid)
  - Lineage tracking (created_by_run)
