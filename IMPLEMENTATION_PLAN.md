# MESSAGE_SCHEMA Redesign Implementation Plan (v2 - From Dev)

## Context
Starting fresh from `dev` branch (commit 2c151e7) to implement MESSAGE_SCHEMA redesign.
See: `docs/architecture/message-schema-redesign.md` for full design rationale.

## Current State (Dev Branch)

**MESSAGE_SCHEMA** (8 columns):
```python
{
    "timestamp": Timestamp(UTC, scale=9),
    "date": Date,
    "author": String,              # Anonymized
    "message": String,              # ← Main content column
    "original_line": String,        # WhatsApp-specific
    "tagged_line": String,          # WhatsApp-specific
    "message_id": String(nullable),
    "event_id": UUID(nullable),
}
```

**File Structure**:
- `input_adapters/whatsapp/adapter.py` (not whatsapp.py)
- `input_adapters/whatsapp/parser.py`
- `input_adapters/base.py`

## Target State (MESSAGE_SCHEMA - Minimal 7 columns)

```python
MESSAGE_SCHEMA = ibis.schema({
    # Identity
    "message_id": dt.string,              # UUID5 deterministic

    # Source (two-level hierarchy)
    "provider_type": dt.string,           # "whatsapp", "slack", etc.
    "provider_instance": dt.string,       # Group name, channel, etc.

    # Temporal
    "timestamp": dt.Timestamp(timezone="UTC", scale=9),

    # Authorship (privacy boundary)
    "author": dt.string,                  # Anonymized 8-char hex

    # Content
    "content": dt.string,                 # ← Renamed from "message"

    # Metadata (escape hatch)
    "metadata": dt.JSON(nullable=True),   # Provider-specific data
})
```

## Implementation Phases

### Phase 1: Schema Definition (30 min)
**File**: `src/egregora/database/ir_schema.py`

1. Add NEW_MESSAGE_SCHEMA (keep old MESSAGE_SCHEMA for compatibility)
2. Add validation function `validate_new_message_schema(table)`
3. Add privacy validation function in `src/egregora/privacy/validation.py`
4. Keep both schemas side-by-side during transition

**Success Criteria**:
- ✅ NEW_MESSAGE_SCHEMA defined as `ibis.schema`
- ✅ Validation functions work
- ✅ Old MESSAGE_SCHEMA still exists (no breaking changes yet)

### Phase 2: WhatsApp Adapter (1.5 hours)
**File**: `src/egregora/input_adapters/whatsapp/adapter.py`

1. Update `parse()` to produce NEW_MESSAGE_SCHEMA
2. Implement vectorized transformation (Pandas → Ibis)
3. Add two-level source: provider_type="whatsapp", provider_instance=group_name
4. Rename `message` → `content` column
5. Move WhatsApp-specific fields to metadata JSON
6. Immediate anonymization (author_raw never leaves adapter)

**Success Criteria**:
- ✅ Adapter produces NEW_MESSAGE_SCHEMA tables
- ✅ Passes `validate_new_message_schema()`
- ✅ Passes `validate_privacy()` (no author_raw)
- ✅ Vectorized processing (Pandas transformations)

### Phase 3: Enrichment & Transformations (1 hour)
**Files**:
- `src/egregora/enrichment/media.py`
- `src/egregora/enrichment/simple_runner.py`
- `src/egregora/transformations/media.py`
- `src/egregora/transformations/windowing.py`

1. Update all `.message` column references → `.content`
2. Use Ibis UDFs (not pandas .apply())
3. Maximize Ibis usage (pandas only at boundaries)

**Success Criteria**:
- ✅ All enrichment functions work with `.content` column
- ✅ Ibis-first architecture (UDFs, not pandas)
- ✅ No for loops over Series (use .apply() or UDFs)

### Phase 4: Pipeline Validation (30 min)
**File**: `src/egregora/orchestration/write_pipeline.py`

1. Update `_parse_and_validate_source()` to use `validate_new_message_schema()`
2. Add privacy validation after parsing
3. Log provider_type and provider_instance

**Success Criteria**:
- ✅ Pipeline validates NEW_MESSAGE_SCHEMA
- ✅ Privacy validation enforced
- ✅ Proper error messages

### Phase 5: Backward Compatibility Layer (30 min)
**File**: `src/egregora/privacy/anonymizer.py`

1. Update `anonymize_table()` to handle both schemas
2. Check for `content` column first, fall back to `message`
3. Add comments explaining transition

**Success Criteria**:
- ✅ Works with both old and new schemas
- ✅ No breaking changes to existing code

### Phase 6: Testing (1 hour)
1. Run full test suite: `uv run pytest tests/`
2. Fix import errors
3. Fix schema validation errors
4. Update tests to use NEW_MESSAGE_SCHEMA

**Success Criteria**:
- ✅ All tests pass
- ✅ No import errors
- ✅ No schema validation failures

### Phase 7: Cutover (30 min)
1. Rename `MESSAGE_SCHEMA` → `OLD_MESSAGE_SCHEMA`
2. Rename `NEW_MESSAGE_SCHEMA` → `MESSAGE_SCHEMA`
3. Update all imports
4. Remove old schema references

**Success Criteria**:
- ✅ Single MESSAGE_SCHEMA (the new one)
- ✅ Old schema deprecated/removed
- ✅ All tests still pass

### Phase 8: Cleanup (30 min)
1. Remove `original_line`, `tagged_line`, `event_id` from old code
2. Update CLAUDE.md with MESSAGE_SCHEMA details
3. Final test run
4. Commit and push

## Total Estimated Time: ~6 hours

## Key Principles
1. **Incremental**: Each phase is independently testable
2. **Backward compatible**: Keep both schemas until cutover
3. **Ibis-first**: Minimize pandas usage
4. **Privacy-first**: author_raw never persisted
5. **Vectorized**: No Python for loops over data
