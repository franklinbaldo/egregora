# ADR-002: Deterministic UUID5 Identity Generation

**Status**: Accepted  
**Date**: 2025-01-08  
**Deciders**: Architecture Team  

## Context

Egregora needs to generate pseudonymous identities for authors while maintaining:
1. **Determinism**: Re-ingesting the same data must produce identical UUIDs
2. **Multi-tenancy**: Different tenants must get isolated identity namespaces
3. **Privacy**: Real names must never reach the LLM API
4. **Source separation**: Same person in different sources gets different UUIDs

### Problem

The original implementation used a single global namespace:
```python
NAMESPACE_AUTHOR = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
author_uuid = uuid.uuid5(NAMESPACE_AUTHOR, author_raw.lower())
```

This had limitations:
- No tenant isolation (tenant A sees tenant B's UUIDs)
- No source separation (WhatsApp Alice == Slack Alice)
- Hard to reason about namespace collisions

## Decision

We adopt **hierarchical UUID5 namespaces** with tenant and source scoping:

```
EGREGORA_NAMESPACE (root)
├── NAMESPACE_AUTHOR (authors)
│   ├── tenant:acme:source:whatsapp:author
│   ├── tenant:acme:source:slack:author
│   └── tenant:default:source:whatsapp:author
├── NAMESPACE_EVENT (events)
│   └── tenant:acme:source:whatsapp:event
└── NAMESPACE_THREAD (threads)
    └── tenant:acme:source:whatsapp:thread
```

### Implementation

```python
from egregora.privacy.uuid_namespaces import NamespaceContext, deterministic_author_uuid

# Generate tenant-scoped UUID
ctx = NamespaceContext(tenant_id="acme-corp", source="whatsapp")
author_uuid = deterministic_author_uuid("acme-corp", "whatsapp", "Alice")

# Properties:
# 1. Deterministic: Same inputs → same UUID
# 2. Isolated: Different tenant_id → different UUID
# 3. Source-aware: Different source → different UUID
```

### Frozen Namespaces

All base namespaces are **frozen constants** in `src/egregora/privacy/uuid_namespaces.py`:
- `EGREGORA_NAMESPACE`: Root namespace for all Egregora UUIDs
- `NAMESPACE_AUTHOR`: Base namespace for author identities
- `NAMESPACE_EVENT`: Base namespace for event identities  
- `NAMESPACE_THREAD`: Base namespace for thread identities

**⚠️ CRITICAL**: These UUIDs MUST NEVER change. Modifying them breaks deterministic identity mapping across all historical data.

## Consequences

### Positive

✅ **Tenant isolation**: `acme-corp/Alice` ≠ `default/Alice`  
✅ **Source separation**: `whatsapp/Alice` ≠ `slack/Alice`  
✅ **Determinism**: Re-ingest → identical UUIDs  
✅ **Privacy**: No PII in UUIDs (one-way hash)  
✅ **Auditability**: Can verify UUID generation from source data  

### Negative

⚠️ **Breaking change**: Existing anonymized data uses old namespace  
⚠️ **Migration needed**: Must re-anonymize to use new namespaces  
⚠️ **Namespace frozen**: Cannot change UUIDs without breaking existing data  

### Neutral

ℹ️ **Complexity**: Requires tenant_id + source parameters everywhere  
ℹ️ **Testing**: Property-based tests required to verify determinism  

## Migration Path

For existing deployments (if any):

1. **Backup**: Export all existing author_uuid mappings
2. **Re-ingest**: Run pipeline with new namespace functions
3. **Verify**: Property test confirms determinism
4. **Update**: Point all references to new UUIDs

Since Egregora is in alpha (Week 2), we accept the breaking change.

## Verification

Property-based tests ensure correctness:

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1), st.text(min_size=1), st.text(min_size=1))
def test_uuid5_determinism(tenant_id: str, source: str, author: str):
    """Same inputs always produce same UUID."""
    uuid1 = deterministic_author_uuid(tenant_id, source, author)
    uuid2 = deterministic_author_uuid(tenant_id, source, author)
    assert uuid1 == uuid2

def test_tenant_isolation():
    """Different tenants get different UUIDs for same author."""
    uuid_acme = deterministic_author_uuid("acme", "whatsapp", "Alice")
    uuid_default = deterministic_author_uuid("default", "whatsapp", "Alice")
    assert uuid_acme != uuid_default

def test_source_separation():
    """Different sources get different UUIDs for same author."""
    uuid_whatsapp = deterministic_author_uuid("default", "whatsapp", "Alice")
    uuid_slack = deterministic_author_uuid("default", "slack", "Alice")
    assert uuid_whatsapp != uuid_slack
```

## References

- **RFC 4122**: UUID Specification (UUID5 definition)
- **Privacy Architecture**: `docs/features/anonymization.md`
- **Implementation**: `src/egregora/privacy/uuid_namespaces.py`
- **Tests**: `tests/unit/test_deterministic_uuids.py`

## Alternatives Considered

### Alternative 1: Random UUIDs (UUID4)
**Rejected**: Not deterministic - re-ingesting produces different UUIDs

### Alternative 2: Hash-based (SHA256)
**Rejected**: Overkill for identity generation; UUID5 is standardized and sufficient

### Alternative 3: Global namespace without tenant scoping
**Rejected**: No multi-tenant isolation; privacy risk across tenants

## Decision Outcome

**Accepted** with the following commitments:
- Freeze namespace constants in `privacy/uuid_namespaces.py`
- Add property-based tests for determinism
- Document migration path for future namespace changes
- Include tenant_id + source in all adapter outputs
