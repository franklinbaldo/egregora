# IR v1 Specification

**Version**: 1.0.0
**Created**: 2025-01-08
**Status**: LOCKED (changes require migration script + version bump)
**ADR**: ADR-001

---

## Overview

The **Intermediate Representation (IR) v1** is the canonical data contract that defines how conversation data flows through Egregora's pipeline. All source adapters (WhatsApp, Slack, Discord, etc.) MUST output tables conforming to this schema.

**Key Principle**: IR v1 is a **versioned lockfile**. Breaking changes require a new version (ir_v2.sql) and a migration path.

---

## Design Philosophy

### 1. Single Representation

IR v1 provides a unified schema for all messaging platforms:

```
WhatsApp Export  ──┐
Slack Export     ──┼──> IR v1 Table ──> Privacy Gate ──> Processing Pipeline
Discord Export   ──┘
```

This eliminates downstream code that needs to understand multiple formats.

### 2. Privacy Boundary

IR v1 contains **both** raw and anonymized identities:

- `author_raw`: Original author name (⚠️ **NEVER** sent to LLM APIs)
- `author_uuid`: Anonymized UUID5 identifier (✅ Safe for LLM processing)

The privacy gate is responsible for:
1. Generating `author_uuid` from `author_raw`
2. Detecting PII in `text` field
3. Populating `pii_flags` field
4. Issuing a `PrivacyPass` capability token

### 3. Deterministic Re-ingestion

All UUIDs are generated using **UUID5** (name-based) to ensure:

- Re-ingesting the same data produces **identical** `event_id` and `author_uuid`
- Deterministic deduplication across pipeline runs
- Stable joins across pipeline runs

### 4. Multi-Tenant Ready

The schema includes `tenant_id` for isolation:

- Default: `'default'` for single-tenant deployments
- UUID5 namespacing includes `tenant_id` to prevent cross-tenant re-identification
- Enables SaaS deployments with data isolation guarantees

---

## Schema Definition

### Table Structure

```sql
CREATE TABLE ir_v1 (
  -- Identity
  event_id        UUID PRIMARY KEY,

  -- Multi-Tenant Isolation
  tenant_id       VARCHAR NOT NULL DEFAULT 'default',
  source          VARCHAR NOT NULL,

  -- Threading
  thread_id       UUID NOT NULL,
  msg_id          VARCHAR NOT NULL,

  -- Temporal
  ts              TIMESTAMP NOT NULL,

  -- Authors (PRIVACY BOUNDARY)
  author_raw      VARCHAR NOT NULL,
  author_uuid     UUID NOT NULL,

  -- Content
  text            TEXT,
  media_url       VARCHAR,
  media_type      VARCHAR,

  -- Metadata
  attrs           JSON,
  pii_flags       JSON,

  -- Lineage
  created_at      TIMESTAMP DEFAULT now(),
  created_by_run  UUID
);
```

### Ibis Schema

For type-safe Ibis operations:

```python
import ibis.expr.datatypes as dt

IR_MESSAGE_SCHEMA = ibis.schema({
    # Identity
    "event_id": dt.UUID,

    # Multi-Tenant
    "tenant_id": dt.string,
    "source": dt.string,

    # Threading
    "thread_id": dt.UUID,
    "msg_id": dt.string,

    # Temporal
    "ts": dt.Timestamp(timezone="UTC"),

    # Authors
    "author_raw": dt.string,
    "author_uuid": dt.UUID,

    # Content
    "text": dt.String(nullable=True),
    "media_url": dt.String(nullable=True),
    "media_type": dt.String(nullable=True),

    # Metadata
    "attrs": dt.JSON(nullable=True),
    "pii_flags": dt.JSON(nullable=True),

    # Lineage
    "created_at": dt.Timestamp(timezone="UTC"),
    "created_by_run": dt.UUID(nullable=True),
})
```

---

## Field Specifications

### Identity Fields

#### `event_id` (UUID, PRIMARY KEY)

- **Purpose**: Unique identifier for each message/event
- **Generation**: `uuid5(NS_EVENTS, f"{source}:{msg_id}")`
- **Invariant**: Same source message → same `event_id` across re-ingests
- **Example**: `550e8400-e29b-41d4-a716-446655440000`

#### `tenant_id` (VARCHAR, NOT NULL)

- **Purpose**: Multi-tenant isolation boundary
- **Default**: `'default'` for single-tenant setups
- **Usage**: UUID5 namespacing, privacy isolation, cost tracking
- **Example**: `'acme-corp'`, `'user-12345'`

#### `source` (VARCHAR, NOT NULL)

- **Purpose**: Source platform identifier
- **Values**: `'whatsapp'`, `'slack'`, `'discord'`, etc.
- **Usage**: Adapter routing, UUID5 namespacing
- **Example**: `'whatsapp'`

---

### Threading Fields

#### `thread_id` (UUID, NOT NULL)

- **Purpose**: Thread/conversation identifier
- **Generation**: `uuid5(NS_THREADS, f"{tenant_id}:{source}:{thread_key}")`
- **Platform Mapping**:
  - **WhatsApp**: Group chat ID (derived from group name)
  - **Slack**: Channel ID or `thread_ts` for threaded replies
  - **Discord**: Channel ID or thread ID

#### `msg_id` (VARCHAR, NOT NULL)

- **Purpose**: Source-specific message identifier
- **Uniqueness**: Must be unique within `(tenant_id, source, thread_id)`
- **Platform Mapping**:
  - **WhatsApp**: Milliseconds since group creation
  - **Slack**: Message timestamp (`ts` field)
  - **Discord**: Message snowflake ID

---

### Temporal Fields

#### `ts` (TIMESTAMP, NOT NULL)

- **Purpose**: Message timestamp (UTC)
- **Timezone**: **Always UTC** (normalized during ingestion)
- **Usage**: Windowing, chronological ordering, time-series analysis
- **Example**: `2025-01-08 14:30:00+00:00`

---

### Author Fields (Privacy Boundary)

#### `author_raw` (VARCHAR, NOT NULL)

- **Purpose**: Original author name/identifier from source
- **⚠️ CRITICAL**: **NEVER** send to LLM APIs
- **Lifecycle**:
  1. Populated during ingestion
  2. Used for UUID5 generation and opt-out detection
  3. Cleared or dropped after privacy gate runs (optional)
- **Example**: `'Alice Smith'`, `'U012ABC3DEF'` (Slack user ID)

#### `author_uuid` (UUID, NOT NULL)

- **Purpose**: Anonymized author identifier
- **Generation**: `uuid5(NS_AUTHORS, f"{tenant_id}:{source}:{author_raw}")`
- **Stability**: Same author → same UUID across re-ingests
- **Safety**: ✅ Safe to send to LLM APIs after privacy gate
- **Example**: `'a0eef1c4-7b8d-4f3e-9c6a-1d2e3f4a5b6c'`

---

### Content Fields

#### `text` (TEXT, nullable)

- **Purpose**: Message text content
- **Nullability**: May be NULL for media-only messages
- **Platform Mapping**:
  - **WhatsApp**: Full message text
  - **Slack**: `message.text` (after unescaping @mentions, #channels)
  - **Discord**: `message.content`

#### `media_url` (VARCHAR, nullable)

- **Purpose**: URL or path to media attachment
- **Format**:
  - **Local files**: Relative path (e.g., `'media/photo.jpg'`)
  - **Remote files**: URL (e.g., `'https://files.slack.com/...'`)
- **Nullability**: NULL if no media attached
- **Platform Mapping**:
  - **WhatsApp**: Extracted filename from `<attached: photo.jpg>`
  - **Slack**: `file.url_private`

#### `media_type` (VARCHAR, nullable)

- **Purpose**: Media MIME type or category
- **Values**: `'image/jpeg'`, `'video/mp4'`, `'audio/mpeg'`, `'application/pdf'`, etc.
- **Nullability**: NULL if no media attached

---

### Metadata Fields

#### `attrs` (JSON, nullable)

- **Purpose**: Source-specific metadata (extensible schema)
- **Rationale**: Allows adapter-specific data without schema changes
- **Platform Examples**:
  - **WhatsApp**: `{original_line, tagged_line, date}`
  - **Slack**: `{reactions: [{name: "thumbsup", count: 3}], edited: true}`
  - **Discord**: `{embeds: [...], reactions: [...]}`

#### `pii_flags` (JSON, nullable)

- **Purpose**: PII detection results from privacy gate
- **Format**: `{phone: true, email: false, address: false}`
- **Lifecycle**:
  - NULL before privacy gate runs
  - Populated by privacy gate's PII detector
- **Usage**: Audit, filtering, re-identification escrow

---

### Lineage Fields

#### `created_at` (TIMESTAMP, DEFAULT now())

- **Purpose**: When this row was created (ingestion time)
- **Usage**: Debugging, cache invalidation, audit trails
- **Example**: `2025-01-08 14:35:22+00:00`

#### `created_by_run` (UUID, nullable)

- **Purpose**: Foreign key to `runs.run_id`
- **Tracks**: Which pipeline run created this row
- **Nullability**: NULL for manually inserted data
- **References**: `runs(run_id) ON DELETE SET NULL`

---

## Indexes

Performance-critical indexes for common query patterns:

```sql
-- Primary access: Query by thread + chronological order
CREATE INDEX idx_ir_v1_thread_ts ON ir_v1 (thread_id, ts);

-- Multi-tenant: Filter by tenant + source
CREATE INDEX idx_ir_v1_tenant ON ir_v1 (tenant_id, source);

-- Author queries: Profile generation, attribution
CREATE INDEX idx_ir_v1_author ON ir_v1 (author_uuid);

-- Lineage: Backtrack to originating run
CREATE INDEX idx_ir_v1_run ON ir_v1 (created_by_run) WHERE created_by_run IS NOT NULL;
```

---

## Constraints

### Uniqueness Constraint

```sql
-- One event per (tenant, source, thread, message)
CREATE UNIQUE INDEX idx_ir_v1_unique_msg
  ON ir_v1 (tenant_id, source, thread_id, msg_id);
```

**Rationale**: Prevents duplicate ingestion within the same tenant/source/thread.

---

## UUID5 Namespaces

All UUIDs are generated using deterministic UUID5 to ensure stability across re-ingests.

### Namespace Constants

```python
# src/egregora/privacy/uuid_namespaces.py

import uuid

# Namespace for event identities
NS_EVENTS = uuid.UUID('d3aac4f7-a0be-5b6a-bf9d-4f5a6b7c8d9e')

# Namespace for author identities
NS_AUTHORS = uuid.UUID('a0eef1c4-7b8d-4f3e-9c6a-1d2e3f4a5b6c')

# Namespace for thread identities
NS_THREADS = uuid.UUID('b1ffa2d5-8c9e-5a4f-ad7b-2e3f4a5b6c7d')

# Namespace for media identities
NS_MEDIA = uuid.UUID('c2aab3e6-9daf-6b5a-be8c-3f4a5b6c7d8e')
```

**⚠️ CRITICAL**: These UUIDs are **immutable**. Changing them breaks re-identification and multi-tenant joins. See ADR-002 for policy.

### Generation Functions

```python
def deterministic_event_uuid(source: str, msg_id: str) -> uuid.UUID:
    """Generate deterministic event UUID."""
    key = f"{source}:{msg_id}"
    return uuid.uuid5(NS_EVENTS, key)

def deterministic_author_uuid(author_raw: str, *, namespace: uuid.UUID = NS_AUTHORS) -> uuid.UUID:
    """Generate deterministic author UUID within a namespace."""
    return uuid.uuid5(namespace, author_raw.strip().lower())

def deterministic_thread_uuid(tenant_id: str, source: str, thread_key: str) -> uuid.UUID:
    """Generate deterministic thread UUID."""
    key = f"{tenant_id}:{source}:{thread_key}"
    return uuid.uuid5(NS_THREADS, key)
```

Adapters **must** call `deterministic_author_uuid()` while parsing source data so
that the IR table already contains anonymized identities. Passing a custom
`namespace` derived from tenant or source metadata keeps pseudonyms isolated
when required:

```python
tenant_namespace = uuid.uuid5(NS_AUTHORS, f"tenant:{tenant_id}:source:{source}")
author_uuid = deterministic_author_uuid(author_raw, namespace=tenant_namespace)
```

The core validation layer assumes the adapter already performed this step and
will not back-fill missing pseudonyms.

---

## Adapter Implementation Guide

### Contract

All source adapters MUST implement:

```python
from typing import Protocol
import ibis

class InputAdapter(Protocol):
    def parse_source(self, input_path: Path) -> ibis.Table:
        """Parse source to IR v1 table.

        Returns:
            Ibis table conforming to IR_MESSAGE_SCHEMA
        """
        ...

    def get_adapter_metadata(self) -> AdapterMeta:
        """Return adapter metadata."""
        ...
```

### Validation

All adapter outputs are validated at the pipeline boundary:

```python
from egregora.database.validation import validate_ir_schema

# In pipeline runner
table = adapter.parse_source(input_path)
validate_ir_schema(table)  # Raises SchemaError if invalid
```

### Example: WhatsApp Adapter

```python
from egregora.sources.whatsapp.parser import parse_source
from egregora.sources.whatsapp.models import WhatsAppExport

export = WhatsAppExport(
    zip_path=Path("export.zip"),
    chat_file="chat.txt",
    group_name="Family Chat",
    group_slug="family-chat",
    export_date=datetime.now(UTC).date(),
    media_files=[]
)

# Parse to IR v1
table = parse_source(export)

# Validate schema
assert set(table.columns) == set(IR_MESSAGE_SCHEMA.keys())
```

---

## Migration from CONVERSATION_SCHEMA

Egregora's current `CONVERSATION_SCHEMA` (Week 1 implementation) is a transitional schema. Migration to IR v1 will happen in phases:

### Field Mapping

| CONVERSATION_SCHEMA | IR v1 | Notes |
|---------------------|-------|-------|
| `timestamp` | `ts` | Renamed for brevity |
| `date` | `attrs['date']` | Moved to metadata |
| `author` | `author_uuid` (after privacy) / `author_raw` (before) | Split into raw + anonymized |
| `message` | `text` | Renamed for clarity |
| `original_line` | `attrs['original_line']` | Moved to metadata |
| `tagged_line` | `attrs['tagged_line']` | Moved to metadata |
| `message_id` | `msg_id` | Renamed for consistency |
| *(new)* | `event_id` | Generated via UUID5 |
| *(new)* | `tenant_id` | Default: `'default'` |
| *(new)* | `source` | Default: `'whatsapp'` |
| *(new)* | `thread_id` | Generated from conversation context |
| *(new)* | `media_url` | NULL (for now) |
| *(new)* | `media_type` | NULL (for now) |
| *(new)* | `pii_flags` | NULL (populated by privacy gate) |
| *(new)* | `created_at` | `now()` |
| *(new)* | `created_by_run` | NULL (populated when runs table exists) |

### Migration Phases

**Phase 1 (Week 1)**: ✅ COMPLETE
- Add IR v1 schema as target in `schema/ir_v1.sql`
- Keep CONVERSATION_SCHEMA for backward compatibility
- CI checks for schema drift

**Phase 2 (Week 2)**:
- Adapters output IR v1
- Validate at adapter boundary with `validate_ir_schema()`
- Privacy gate accepts IR v1 input

**Phase 3 (Week 3)**:
- All pipeline stages consume IR v1
- CONVERSATION_SCHEMA deprecated (emit warnings)

**Phase 4 (Week 4)**:
- Remove CONVERSATION_SCHEMA entirely
- Update all tests to use IR v1

---

## Validation & Enforcement

### CI Schema Drift Check

```bash
# .github/workflows/ci.yml
- name: Check IR v1 schema drift
  run: |
    uv run python scripts/check_ir_schema.py
    # Compares CONVERSATION_SCHEMA against schema/ir_v1.json
    # Fails if drift detected
```

### Runtime Validation

```python
from egregora.database.validation import validate_ir_schema

# At adapter boundary
table = adapter.parse_source(input_path)
validate_ir_schema(table)  # Raises SchemaError if invalid

# In privacy gate
def anonymize_table(table: ibis.Table) -> ibis.Table:
    validate_ir_schema(table)  # Ensure IR v1 input
    # ... anonymization logic
    validate_ir_schema(anonymized_table)  # Ensure IR v1 output
    return anonymized_table
```

---

## Related Documentation

- **ADR-002**: Deterministic UUIDs (`docs/architecture/adr-002-deterministic-uuids.md`)
- **ADR-003**: Privacy Gate Capability Token (`docs/architecture/adr-003-privacy-gate-capability-token.md`)
- **Schema Lockfile**: `schema/ir_v1.sql`
- **CI Enforcement**: `scripts/check_ir_schema.py`
- **Adapter Guide**: `docs/architecture/adapter-guide.md` (coming in Week 2)

---

## Changelog

### v1.0.0 (2025-01-08)

- Initial IR v1 specification
- Defines canonical schema for all source adapters
- Establishes UUID5 namespaces for deterministic re-ingestion
- Documents privacy boundary (`author_raw` vs `author_uuid`)
- Adds multi-tenant isolation via `tenant_id`

---

**Last Updated**: 2025-01-08
**Status**: LOCKED (breaking changes require v2.0.0)
