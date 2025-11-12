# IR v1 Schema Migration Plan

## Overview

This document outlines the plan to migrate input adapters from the legacy `CONVERSATION_SCHEMA` to the new `IR_MESSAGE_SCHEMA` (IR v1). This migration is required to complete end-to-end testing with VCR recording.

**Status**: 🔴 BLOCKING - Pipeline fails at ingestion stage
**Priority**: P0 - Critical for all pipeline functionality
**Affected**: All input adapters (WhatsApp, Slack)

---

## Understanding tenant_id

### What is tenant_id?

**Definition**: `tenant_id` is the **data provenance identifier** that represents the source conversation/group, NOT the adapter type.

**For Egregora**:
- `tenant_id` = Group/conversation identifier (e.g., GroupSlug like `"family-chat"`)
- `source` = Adapter type (e.g., `"whatsapp"`, `"slack"`)

### Why tenant_id matters

1. **Privacy Isolation**: Each group gets isolated UUID namespaces
   ```python
   # Same author in different groups → different UUIDs
   uuid5(namespace("group-a", "whatsapp", "author"), "Alice")  # → UUID-A
   uuid5(namespace("group-b", "whatsapp", "author"), "Alice")  # → UUID-B
   ```

2. **Multi-Tenancy**: Process multiple groups in same database
   ```sql
   SELECT * FROM messages WHERE tenant_id = 'family-chat'
   ```

3. **Determinism**: Same (tenant_id, source, author_raw) → same UUID

### tenant_id in Practice

```python
# WhatsApp Example
tenant_id = group_slug  # "teste" from "Conversa do WhatsApp com Teste"
source = "whatsapp"
thread_id = uuid5(thread_namespace(tenant_id, source), group_slug)

# Slack Example
tenant_id = channel_slug  # "eng-team" from "#eng-team"
source = "slack"
thread_id = uuid5(thread_namespace(tenant_id, source), channel_id)
```

---

## Schema Comparison

### Legacy Schema (CONVERSATION_SCHEMA)

```python
{
    "timestamp": dt.Timestamp(timezone="UTC", scale=9),
    "date": dt.date,
    "author": dt.string,           # Already anonymized (post-privacy)
    "message": dt.string,
    "original_line": dt.string,
    "tagged_line": dt.string,
    "message_id": dt.String(nullable=True),
}
```

**Issues**:
- ❌ No tenant isolation
- ❌ No source tracking
- ❌ No threading support
- ❌ `author` already anonymized (privacy boundary unclear)
- ❌ No lineage tracking
- ❌ Column names too generic (`message` vs `text`)

### New Schema (IR_MESSAGE_SCHEMA)

```python
{
    # Identity
    "event_id": dt.UUID,                    # Unique message event

    # Multi-Tenant
    "tenant_id": dt.string,                 # Group/conversation ID
    "source": dt.string,                    # Adapter type (whatsapp/slack)

    # Threading
    "thread_id": dt.UUID,                   # Conversation/channel UUID
    "msg_id": dt.string,                    # Original message ID

    # Temporal
    "ts": dt.Timestamp(timezone="UTC"),     # Message timestamp

    # Authors (PRIVACY BOUNDARY)
    "author_raw": dt.string,                # Original author name (PII)
    "author_uuid": dt.UUID,                 # Deterministic UUID

    # Content
    "text": dt.String(nullable=True),       # Message text
    "media_url": dt.String(nullable=True),  # Media reference
    "media_type": dt.String(nullable=True), # image/video/audio/document

    # Metadata
    "attrs": dt.JSON(nullable=True),        # Original message metadata
    "pii_flags": dt.JSON(nullable=True),    # PII detection results

    # Lineage
    "created_at": dt.Timestamp(timezone="UTC"),  # When row was created
    "created_by_run": dt.UUID(nullable=True),    # Which pipeline run
}
```

**Benefits**:
- ✅ Clear privacy boundary (`author_raw` = PII, `author_uuid` = safe)
- ✅ Tenant isolation for multi-group processing
- ✅ Source tracking for multi-platform support
- ✅ Threading support for conversations
- ✅ Lineage tracking for debugging
- ✅ Media support with type detection
- ✅ PII flags for audit trail

---

## Migration Strategy

### Phase 1: Column Mapping

Map legacy columns to IR v1:

| Legacy Column    | IR v1 Column       | Transformation |
|------------------|--------------------|-------------------------------------------------|
| `timestamp`      | `ts`               | Direct copy (same type) |
| `date`           | *(derived)*        | Extract from `ts`: `ts.date()` |
| `author`         | `author_raw`       | **REVERT**: Use raw name from export, not UUID |
| `author`         | `author_uuid`      | Generate via `deterministic_author_uuid()` |
| `message`        | `text`             | Direct copy |
| `original_line`  | `attrs['original_line']` | Move to metadata JSON |
| `tagged_line`    | `attrs['tagged_line']`   | Move to metadata JSON |
| `message_id`     | `msg_id`           | Direct copy |
| *(new)*          | `event_id`         | Generate via `deterministic_event_uuid()` |
| *(new)*          | `tenant_id`        | Use GroupSlug |
| *(new)*          | `source`           | Hard-code: `"whatsapp"` |
| *(new)*          | `thread_id`        | Generate via `deterministic_thread_uuid()` |
| *(new)*          | `media_url`        | Extract from message if present |
| *(new)*          | `media_type`       | Detect from file extension |
| *(new)*          | `pii_flags`        | Empty JSON `{}` (populated by privacy stage) |
| *(new)*          | `created_at`       | Current timestamp: `datetime.now(UTC)` |
| *(new)*          | `created_by_run`   | Pipeline run UUID (if available) |

### Phase 2: UUID Generation

Use deterministic UUID5 generation from `privacy/constants.py`:

```python
from egregora.privacy.constants import (
    NamespaceContext,
    deterministic_author_uuid,
    deterministic_event_uuid,
    deterministic_thread_uuid,
)

# Create namespace context
ctx = NamespaceContext(
    tenant_id=str(group_slug),  # "teste" from group name
    source="whatsapp"
)

# Generate UUIDs
author_uuid = deterministic_author_uuid(
    tenant_id=str(group_slug),
    source="whatsapp",
    author_raw=author_name  # Raw name from export
)

thread_id = deterministic_thread_uuid(
    tenant_id=str(group_slug),
    source="whatsapp",
    thread_key=str(group_slug)  # Use group slug as thread key
)

event_id = deterministic_event_uuid(
    tenant_id=str(group_slug),
    source="whatsapp",
    msg_id=message_id
)
```

### Phase 3: Adapter Updates

#### WhatsApp Adapter

**File**: `src/egregora/input_adapters/whatsapp.py`

**Current flow**:
```python
def parse(input_path: Path) -> Table:
    # 1. Parse chat file → raw messages
    # 2. Anonymize authors → UUIDs
    # 3. Return CONVERSATION_SCHEMA
```

**New flow**:
```python
def parse(input_path: Path) -> Table:
    # 1. Parse chat file → raw messages
    # 2. Keep raw author names (DON'T anonymize yet)
    # 3. Generate UUIDs (event_id, thread_id, author_uuid)
    # 4. Add tenant_id, source, metadata
    # 5. Return IR_MESSAGE_SCHEMA
```

**Key changes**:
- Remove early anonymization (privacy stage handles this)
- Add `tenant_id` = GroupSlug
- Add `source` = `"whatsapp"`
- Generate UUIDs using privacy helpers
- Move `original_line`/`tagged_line` to `attrs` JSON
- Extract media info from message text

#### Slack Adapter

**File**: `src/egregora/input_adapters/slack.py`

Similar changes as WhatsApp:
- `tenant_id` = channel slug (from channel name or ID)
- `source` = `"slack"`
- Map Slack message JSON to IR v1 columns
- Generate UUIDs using privacy helpers

### Phase 4: Privacy Stage Updates

**File**: `src/egregora/privacy/gate.py`

The privacy stage currently expects `author` column. Update to:

1. Read `author_raw` (input with PII)
2. Validate `author_uuid` matches `author_raw`
3. Run PII detection on `text` + `author_raw`
4. Populate `pii_flags` JSON
5. *(DON'T change author_uuid - already deterministic)*

**New behavior**:
- Privacy stage validates UUIDs but doesn't generate them
- Adapters generate UUIDs (deterministic from raw data)
- Privacy stage focuses on PII detection + flagging

### Phase 5: Downstream Updates

Update any code that references legacy columns:

```bash
# Find all references to old columns
rg '"author"' --type py src/egregora/
rg '"message"' --type py src/egregora/
rg '"timestamp"' --type py src/egregora/
```

**Files likely affected**:
- `enrichment/` - Message text processing
- `agents/writer/` - Post generation
- `transformations/windowing.py` - Time-based windows
- `database/views.py` - View registry queries

**Search and replace**:
- `.author` → `.author_raw` or `.author_uuid` (context-dependent)
- `.message` → `.text`
- `.timestamp` → `.ts`

---

## Implementation Steps

### Step 1: Create UUID Helpers (if missing)

Check if these exist in `privacy/constants.py`:
- ✅ `deterministic_author_uuid(tenant_id, source, author_raw)`
- ❓ `deterministic_event_uuid(tenant_id, source, msg_id)` - may need to add
- ❓ `deterministic_thread_uuid(tenant_id, source, thread_key)` - may need to add

If missing, add them following the pattern of `deterministic_author_uuid()`.

### Step 2: Update WhatsApp Adapter

```python
# src/egregora/input_adapters/whatsapp.py

def parse(export: WhatsAppExport) -> Table:
    """Parse WhatsApp export to IR v1 schema."""

    # 1. Parse chat file (existing logic)
    raw_messages = parse_chat_file(export.chat_file)

    # 2. Extract metadata
    tenant_id = str(export.group_slug)
    source = "whatsapp"
    run_id = get_current_run_id()  # From context if available

    # 3. Create namespace context
    ctx = NamespaceContext(tenant_id=tenant_id, source=source)
    thread_id = deterministic_thread_uuid(tenant_id, source, tenant_id)

    # 4. Generate IR v1 columns
    ir_messages = []
    for msg in raw_messages:
        ir_messages.append({
            # Identity
            "event_id": deterministic_event_uuid(tenant_id, source, msg["message_id"]),

            # Multi-Tenant
            "tenant_id": tenant_id,
            "source": source,

            # Threading
            "thread_id": thread_id,
            "msg_id": msg["message_id"],

            # Temporal
            "ts": msg["timestamp"],

            # Authors (RAW - privacy stage will handle)
            "author_raw": msg["author"],  # Keep raw name
            "author_uuid": deterministic_author_uuid(tenant_id, source, msg["author"]),

            # Content
            "text": msg["message"],
            "media_url": extract_media_url(msg),  # Helper function
            "media_type": detect_media_type(msg),  # Helper function

            # Metadata
            "attrs": {
                "original_line": msg["original_line"],
                "tagged_line": msg["tagged_line"],
                "date": str(msg["date"]),  # Keep for reference
            },
            "pii_flags": {},  # Empty - privacy stage populates

            # Lineage
            "created_at": datetime.now(UTC),
            "created_by_run": run_id,
        })

    # 5. Convert to Ibis table
    return ibis.memtable(ir_messages, schema=IR_MESSAGE_SCHEMA)
```

### Step 3: Update Slack Adapter

Similar structure to WhatsApp adapter:
- Parse Slack export JSON
- Map to IR v1 columns
- Generate UUIDs

### Step 4: Update Privacy Stage

```python
# src/egregora/privacy/gate.py

def anonymize_authors(table: Table) -> Table:
    """Validate UUIDs and run PII detection (don't generate UUIDs)."""

    # Validate author_uuid matches author_raw
    for row in table.head(5).to_pandas().itertuples():
        expected_uuid = deterministic_author_uuid(
            row.tenant_id, row.source, row.author_raw
        )
        assert row.author_uuid == expected_uuid, "UUID mismatch!"

    # Run PII detection on text + author_raw
    pii_results = detect_pii_batch(table)

    # Update pii_flags column
    return table.mutate(pii_flags=pii_results)
```

### Step 5: Update Views and Transforms

Update `database/views.py`:

```python
# Old
@views.register("daily_summary")
def daily_summary(data: Table) -> Table:
    return data.group_by(data.date).aggregate(
        count=_.message.count(),  # ❌ Old column
        authors=_.author.unique()  # ❌ Old column
    )

# New
@views.register("daily_summary")
def daily_summary(data: Table) -> Table:
    return data.group_by(data.ts.date()).aggregate(
        count=_.text.count(),  # ✅ New column
        authors=_.author_uuid.unique()  # ✅ New column (or author_raw if needed)
    )
```

### Step 6: Update Tests

Update test assertions:

```python
# Old
assert "author" in schema.names
assert "message" in schema.names

# New
assert "author_raw" in schema.names
assert "author_uuid" in schema.names
assert "text" in schema.names
assert "tenant_id" in schema.names
assert "source" in schema.names
```

### Step 7: Run End-to-End Test with VCR

```bash
export GOOGLE_API_KEY="..."
uv run pytest tests/e2e/test_cli_write.py::TestWriteCommandWithAPI -v --vcr-record=once
```

This will:
- ✅ Parse WhatsApp export with IR v1 schema
- ✅ Validate schema compliance
- ✅ Run privacy stage (PII detection)
- ✅ Run enrichment (if enabled)
- ✅ Generate posts
- ✅ Record VCR cassettes for future replay

---

## Testing Strategy

### Unit Tests

```python
def test_whatsapp_adapter_ir_v1_schema():
    """Test WhatsApp adapter outputs IR v1 schema."""
    export = WhatsAppExport(...)
    table = parse_whatsapp(export)

    # Validate schema
    validate_ir_schema(table)

    # Check required columns
    assert "event_id" in table.columns
    assert "tenant_id" in table.columns
    assert "author_raw" in table.columns
    assert "author_uuid" in table.columns

    # Check tenant_id value
    assert table.tenant_id[0].execute() == str(export.group_slug)

    # Check UUID determinism
    row = table.head(1).to_pandas().iloc[0]
    expected_uuid = deterministic_author_uuid(
        row.tenant_id, row.source, row.author_raw
    )
    assert row.author_uuid == expected_uuid
```

### Integration Tests

```python
def test_ir_v1_end_to_end():
    """Test full pipeline with IR v1 schema."""
    # 1. Parse
    table = parse_whatsapp(test_export)
    validate_ir_schema(table)

    # 2. Privacy
    table = run_privacy_stage(table)
    assert all(table.pii_flags.execute())  # All rows have PII flags

    # 3. Enrichment (mocked)
    table = run_enrichment(table)

    # 4. Writer (mocked)
    posts = generate_posts(table)
    assert len(posts) > 0
```

---

## Migration Checklist

- [ ] **Step 1**: Add missing UUID helpers to `privacy/constants.py`
  - [ ] `deterministic_event_uuid()`
  - [ ] `deterministic_thread_uuid()`

- [ ] **Step 2**: Update WhatsApp adapter
  - [ ] Remove early anonymization
  - [ ] Add `tenant_id` = GroupSlug
  - [ ] Add `source` = "whatsapp"
  - [ ] Generate UUIDs
  - [ ] Move metadata to `attrs` JSON
  - [ ] Extract media info

- [ ] **Step 3**: Update Slack adapter
  - [ ] Same changes as WhatsApp

- [ ] **Step 4**: Update privacy stage
  - [ ] Validate UUIDs (don't generate)
  - [ ] Run PII detection
  - [ ] Populate `pii_flags`

- [ ] **Step 5**: Update views and transforms
  - [ ] Search for `.author` → `.author_raw` or `.author_uuid`
  - [ ] Search for `.message` → `.text`
  - [ ] Search for `.timestamp` → `.ts`

- [ ] **Step 6**: Update tests
  - [ ] Unit tests for adapters
  - [ ] Integration tests for pipeline
  - [ ] VCR cassette recording

- [ ] **Step 7**: Update documentation
  - [ ] CLAUDE.md: Document IR v1 schema
  - [ ] Architecture docs: Update schema diagrams
  - [ ] Privacy docs: Clarify PII boundary

---

## Rollout Plan

### Phase A: Foundation (Day 1)
- Add UUID helpers
- Update WhatsApp adapter
- Unit tests pass

### Phase B: Integration (Day 2)
- Update privacy stage
- Update views/transforms
- Integration tests pass

### Phase C: Validation (Day 3)
- Update remaining adapters (Slack)
- Run full end-to-end test
- Record VCR cassettes

### Phase D: Cleanup (Day 4)
- Remove CONVERSATION_SCHEMA (if no longer used)
- Update documentation
- Final review

---

## Risk Assessment

### High Risk
- 🔴 **Breaking change**: All adapters must be updated simultaneously
- 🔴 **Privacy regression**: Must preserve deterministic UUIDs
- 🔴 **Data loss**: Must preserve all original message content

### Medium Risk
- 🟡 **Test coverage**: Need comprehensive tests for UUID generation
- 🟡 **Performance**: UUID generation may slow down parsing
- 🟡 **Debugging**: More complex schema = harder to debug

### Low Risk
- 🟢 **Backwards compatibility**: Not required (alpha mindset)
- 🟢 **Migration path**: No existing databases to migrate

---

## Success Criteria

✅ **Schema Compliance**
- All adapters output valid IR v1 schema
- `validate_ir_schema()` passes for all adapters

✅ **UUID Determinism**
- Same input → same UUIDs across runs
- Different tenants → different UUIDs

✅ **Privacy Boundary**
- `author_raw` contains PII (raw names)
- `author_uuid` is safe (deterministic UUID)
- `pii_flags` populated by privacy stage

✅ **End-to-End Test**
- Full pipeline runs without errors
- VCR cassettes recorded successfully
- Output posts generated correctly

✅ **Test Coverage**
- Unit tests for each adapter
- Integration tests for privacy stage
- End-to-end tests with VCR

---

## Open Questions

1. **Run tracking**: How to get current `run_id` in adapters?
   - Option A: Pass as parameter to `parse()`
   - Option B: Use context variable
   - Option C: Leave as `None` for now

2. **Media extraction**: How to parse media URLs from WhatsApp message text?
   - Pattern: `<attached: 00001234-PHOTO-2025-01-01-12-34-56.jpg>`
   - Helper: `extract_media_url(message_text) -> str | None`

3. **Thread ID**: Use `group_slug` or generate new UUID?
   - Option A: `thread_id = uuid5(thread_ns, group_slug)` ✅ Recommended
   - Option B: `thread_id = UUID()` (random) ❌ Not deterministic

4. **Legacy support**: Keep CONVERSATION_SCHEMA for compatibility?
   - Option A: Remove (alpha mindset) ✅ Recommended
   - Option B: Keep as deprecated alias

---

## Next Steps

1. **Review this plan** with maintainers
2. **Clarify open questions** (especially run_id tracking)
3. **Create implementation PR** following checklist
4. **Run tests** to validate migration
5. **Record VCR cassettes** for future test replay

---

## References

- [IR v1 Schema Definition](../src/egregora/database/validation.py)
- [Privacy Constants](../src/egregora/privacy/constants.py)
- [WhatsApp Adapter](../src/egregora/input_adapters/whatsapp.py)
- [Slack Adapter](../src/egregora/input_adapters/slack.py)
- [CLAUDE.md](../../CLAUDE.md)
