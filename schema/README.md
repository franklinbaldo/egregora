# IR Schema Lockfiles

This directory contains canonical schema definitions for the Intermediate Representation (IR) used by Egregora's adapter system.

## Purpose

Schema lockfiles prevent accidental schema changes and ensure all adapters conform to the same contract. Any modification to the IR schema must be intentional and coordinated.

## Files

### `ir_v1.sql`
DuckDB CREATE TABLE statement for IR v1. This is the human-readable, authoritative schema definition.

### `ir_v1.json`
JSON representation of the Ibis schema for IR v1. Used by CI validation scripts to detect schema drift.

## Workflow

### Checking for Drift

Run the validation script to verify code schema matches lockfiles:

```bash
python scripts/check_ir_schema.py
```

This script compares `src/egregora/database/validation.py:IR_MESSAGE_SCHEMA` against `schema/ir_v1.json`.

### Making Schema Changes

If you need to modify the IR schema:

1. **Consider breaking changes**: If this is a breaking change, increment to `ir_v2.sql` / `ir_v2.json`

2. **Update code schema**: Modify `src/egregora/database/validation.py:IR_MESSAGE_SCHEMA`

3. **Update lockfiles**:
   ```bash
   # Update SQL schema
   vim schema/ir_v1.sql

   # Update JSON schema to match code
   python -c "
   import json
   from pathlib import Path
   import sys
   sys.path.insert(0, 'src')
   from egregora.database.validation import IR_MESSAGE_SCHEMA

   data = {
       'version': '1.1.0',  # Increment version
       'columns': {
           col: {
               'type': str(IR_MESSAGE_SCHEMA[col]).split('(')[0].upper(),
               'nullable': IR_MESSAGE_SCHEMA[col].nullable
           }
           for col in IR_MESSAGE_SCHEMA.names
       }
   }
   Path('schema/ir_v1.json').write_text(json.dumps(data, indent=2))
   "
   ```

4. **Verify no drift**:
   ```bash
   python scripts/check_ir_schema.py
   ```

5. **Update adapters**: Modify all source adapters to conform to new schema

6. **Update tests**: Ensure `tests/unit/test_ir_validation.py` covers new schema requirements

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
