# IR Schema

This directory contains historical schema artifacts for the Intermediate Representation (IR) used by Egregora's adapter system.

## Current State (2025-11-17)

**Canonical Schema**: The IR v1 schema is now defined **exclusively in Python** at:
```
src/egregora/database/validation.py:IR_MESSAGE_SCHEMA
```

This is the single source of truth. All adapters MUST produce tables conforming to this schema.

## Rationale for Simplification

Previously, the IR schema was maintained in three places:
1. `schema/ir_v1.sql` - SQL definition
2. `schema/ir_v1.json` - JSON lockfile
3. `src/egregora/database/validation.py` - Python/Ibis schema

This created maintenance burden: any schema change required updating 3 files + running validation scripts.

**Alpha mindset**: For a local-first tool, the Python schema (which the code actually uses) is sufficient. SQL and JSON lockfiles added complexity without clear benefits.

## Making Schema Changes

To modify the IR schema:

1. **Edit the Python schema**:
   ```python
   # src/egregora/database/validation.py
   IR_MESSAGE_SCHEMA = ibis.schema({
       "event_id": dt.string,
       "tenant_id": dt.string,
       # ... add/modify columns
   })
   ```

2. **Update adapters**: Ensure all source adapters conform to new schema

3. **Update tests**: Run `pytest tests/unit/test_ir_validation.py` to verify

4. **Consider versioning**: For breaking changes, consider creating `IR_MESSAGE_SCHEMA_V2`

## Historical Note

The IR schema was previously maintained in multiple formats (SQL, JSON, Python) which created unnecessary synchronization burden. As of 2025-11-17, all lockfiles have been removed in favor of the Python-only schema. This simplification embraces the alpha mindset: reduce complexity, one canonical source.

## Schema Overview (IR v1)

**15 columns**:
- **Identity**: `event_id` (unique message ID)
- **Multi-tenant**: `tenant_id`, `source`
- **Threading**: `thread_id`, `msg_id`
- **Temporal**: `ts` (message timestamp)
- **Authors** (PRIVACY BOUNDARY): `author_raw`, `author_uuid`
- **Content**: `text`, `media_url`, `media_type`
- **Metadata**: `attrs` (JSON), `pii_flags` (JSON)
- **Lineage**: `created_at`, `created_by_run`

See `src/egregora/database/validation.py` for the definitive schema definition.
