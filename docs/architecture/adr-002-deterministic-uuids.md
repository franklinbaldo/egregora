# ADR-002: Deterministic UUID5 Identities

**Status**: ✅ Accepted

**Date**: 2025-01-08

**Authors**: Architecture Team

**Supersedes**: None

**Related**: ADR-003 (Privacy Gate), IR v1 Schema

---

## Context

Egregora needs to generate stable, reproducible identifiers for:

1. **Authors** (message senders)
2. **Threads** (conversations, group chats, channels)
3. **Media** (attachments, images, videos)
4. **Events** (individual messages)

### Current State (Before ADR-002)

The existing anonymizer uses a non-deterministic approach:
- Random UUID generation for each run
- Re-ingesting same data produces different UUIDs
- No multi-tenant isolation
- Difficult to deduplicate or join across runs

### Requirements

1. **Determinism**: Re-ingesting same data must produce identical UUIDs
2. **Multi-tenant Isolation**: Different tenants get different UUIDs for same entity
3. **Source Isolation**: Same entity across platforms gets different UUIDs (opt-in linking)
4. **Privacy**: No reversible mapping by default (one-way hash)
5. **Immutability**: UUIDs must be stable over time (no accidental changes)

---

## Decision

We will use **UUID5 (name-based UUIDs)** with namespaced deterministic generation.

### UUID5 Namespaces (Locked)

Four distinct namespaces for different entity types:

```python
# Locked on 2025-01-08 (version 1.0.0)
NS_AUTHORS = uuid.UUID('a0eef1c4-7b8d-4f3e-9c6a-1d2e3f4a5b6c')
NS_THREADS = uuid.UUID('b1ffa2d5-8c9e-5a4f-ad7b-2e3f4a5b6c7d')
NS_MEDIA   = uuid.UUID('c2aab3e6-9daf-6b5a-be8c-3f4a5b6c7d8e')
NS_EVENTS  = uuid.UUID('d3bbc4f7-aebf-7c6b-cf9d-4f5a6b7c8d9e')
```

**Critical**: These UUIDs are **immutable**. Changing them breaks historical data and re-identification.

### Generation Pattern

All UUIDs use the pattern: `uuid5(NAMESPACE, f"{tenant_id}:{source}:{identifier}")`

**Examples**:

```python
# Author UUID
author_uuid = uuid5(NS_AUTHORS, "default:whatsapp:Alice")
# → UUID('...')  # Same every time

# Thread UUID
thread_uuid = uuid5(NS_THREADS, "default:whatsapp:Family Group")
# → UUID('...')  # Same every time

# Event UUID (message)
event_uuid = uuid5(NS_EVENTS, "default:whatsapp:1641024000000")
# → UUID('...')  # Same every time
```

### Multi-Tenant Isolation

Different tenants get different UUIDs for same entity:

```python
# Tenant A
uuid5(NS_AUTHORS, "tenant-a:whatsapp:Alice")
# → UUID('aaaaaaaa-...')

# Tenant B
uuid5(NS_AUTHORS, "tenant-b:whatsapp:Alice")
# → UUID('bbbbbbbb-...')  # Different UUID
```

This prevents:
- Cross-tenant data leaks
- Accidental correlation across tenants
- Cost attribution errors

### Source Isolation

Same person across platforms gets different UUIDs (prevents default correlation):

```python
# Alice on WhatsApp
uuid5(NS_AUTHORS, "default:whatsapp:Alice")
# → UUID('aaaaaaaa-...')

# Alice on Slack
uuid5(NS_AUTHORS, "default:slack:Alice")
# → UUID('bbbbbbbb-...')  # Different UUID
```

Tenants can opt-in to link identities via explicit configuration.

---

## Privacy Implications

### One-Way Hashing (Default)

By default, the mapping `author_raw → author_uuid` is **NOT persisted**:

- Generation is deterministic (same input → same output)
- Mapping is one-way (UUID cannot be reversed to original name)
- No database stores `author_raw` after privacy gate runs

**Example**:

```python
# Generate UUID (deterministic)
author_uuid = deterministic_author_uuid("default", "whatsapp", "Alice")

# This mapping is NOT stored anywhere
# author_uuid → "Alice" is unknown after generation
```

### Re-identification Escrow (Opt-In)

Tenants can opt-in to store a salted mapping for re-identification:

**Configuration**:
```yaml
privacy:
  enable_reidentification: true  # Default: false
  reidentification_salt: "random-salt-per-tenant"
  escrow_retention_days: 90  # How long to keep mapping
```

**Storage**:
```sql
CREATE TABLE reidentification_escrow (
  tenant_id       VARCHAR NOT NULL,
  author_uuid     UUID NOT NULL,
  author_raw_hash VARCHAR NOT NULL,  -- HMAC(author_raw, tenant_salt)
  created_at      TIMESTAMP DEFAULT now(),
  expires_at      TIMESTAMP,
  PRIMARY KEY (tenant_id, author_uuid)
);
```

**Policy**:
- Mapping is salted (different salt per tenant)
- Access requires tenant admin credentials
- Subject to data retention policies (default: 90 days)
- Audit log for all re-identification queries

**CLI**:
```bash
# Re-identify author (requires admin auth)
egregora privacy reidentify --tenant=acme --author-uuid=...
# → "Alice" (if within retention window)
```

---

## Consequences

### ✅ Positive

1. **Determinism**:
   - Re-ingesting same data produces identical UUIDs
   - Enables idempotent pipelines
   - Simplifies deduplication

2. **Multi-tenant Safe**:
   - Isolated UUIDs prevent cross-tenant leaks
   - Cost attribution works correctly
   - Privacy compliance (GDPR, CCPA)

3. **Testability**:
   - Predictable UUIDs in tests
   - Property testing: `re_ingest(data) == first_ingest(data)`
   - No flaky tests due to random UUIDs

4. **Privacy-First**:
   - One-way by default (no reversible mapping)
   - Opt-in re-identification with audit trail
   - Compliant with "right to be forgotten" (delete escrow entries)

### ⚠️ Negative

1. **UUID Collision Risk** (Theoretical):
   - If two different strings hash to same UUID5
   - Mitigated by: UUIDs are 128-bit (2^128 possible values)
   - Probability: Negligible for practical datasets

2. **Namespace Immutability**:
   - Changing namespaces breaks historical data
   - Requires migration script + re-computation
   - Locked to prevent accidental changes

3. **Re-identification Limitations**:
   - Only works if escrow is enabled
   - Subject to retention window (expires after 90 days)
   - Cannot recover names from historical data without escrow

---

## Migration Path

### From Random UUIDs (Current State)

**Phase 1** (Week 1): Add deterministic UUID generation
- Create `src/egregora/privacy/constants.py`
- Implement namespace functions
- **Do NOT change existing anonymizer yet**

**Phase 2** (Week 2): Update anonymizer
- Replace random UUID generation with deterministic
- Update tests to expect stable UUIDs
- Property tests: `anonymize(x) == anonymize(x)`

**Phase 3** (Week 3): Re-process historical data
- Re-run privacy gate on all historical exports
- Validate: New UUIDs match expected deterministic values
- Backup old UUIDs if re-identification escrow enabled

**Phase 4** (Week 4): Cleanup
- Remove random UUID code paths
- Update documentation
- Celebrate determinism! 🎉

### From UUID5 v1 to UUID5 v2 (Future)

If namespaces need to change (e.g., security compromise):

1. **Create constants_v2.py**:
   ```python
   NS_AUTHORS_V2 = uuid.UUID('new-namespace-uuid')
   NAMESPACES_VERSION = "2.0.0"
   ```

2. **Migration script**:
   ```bash
   egregora migrate uuids --from-version=1 --to-version=2
   ```

3. **Re-compute all UUIDs**:
   - Re-run privacy gate on all data
   - Update escrow mappings (if enabled)
   - Validate no data loss

4. **Approval**:
   - Security review
   - Data steward approval
   - User notification (if re-id escrow affected)

---

## Validation

### Property Tests

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1), st.text(min_size=1))
def test_uuid5_determinism(tenant_id: str, author: str):
    """Same inputs always produce same UUID."""
    uuid1 = deterministic_author_uuid(tenant_id, "whatsapp", author)
    uuid2 = deterministic_author_uuid(tenant_id, "whatsapp", author)
    assert uuid1 == uuid2

def test_tenant_isolation():
    """Different tenants get different UUIDs for same author."""
    uuid_a = deterministic_author_uuid("tenant-a", "whatsapp", "Alice")
    uuid_b = deterministic_author_uuid("tenant-b", "whatsapp", "Alice")
    assert uuid_a != uuid_b

def test_source_isolation():
    """Same author on different platforms gets different UUIDs."""
    uuid_whatsapp = deterministic_author_uuid("default", "whatsapp", "Alice")
    uuid_slack = deterministic_author_uuid("default", "slack", "Alice")
    assert uuid_whatsapp != uuid_slack

def test_re_ingest_stability(whatsapp_zip: Path):
    """Re-ingesting same data produces identical UUIDs."""
    table1 = parse_and_anonymize(whatsapp_zip, tenant_id="test")
    table2 = parse_and_anonymize(whatsapp_zip, tenant_id="test")

    # Compare event_id and author_uuid columns
    hash1 = hash_table(table1.select("event_id", "author_uuid"))
    hash2 = hash_table(table2.select("event_id", "author_uuid"))

    assert hash1 == hash2  # Identical UUIDs
```

### CI Checks

```yaml
# .github/workflows/ci.yml
- name: Validate namespace immutability
  run: |
    # Ensure namespaces haven't changed
    python -c "from egregora.privacy.constants import validate_namespaces; validate_namespaces()"
```

---

## Security Considerations

### Namespace Compromise

If namespaces are leaked or compromised:

1. **Immediate**:
   - Rotate tenant-specific salts (for escrow)
   - Invalidate escrow mappings

2. **Short-term** (1 week):
   - Generate new namespaces (constants_v2.py)
   - Migration script to re-compute all UUIDs

3. **Long-term**:
   - Security review of UUID generation code
   - Audit who has access to namespace constants

### Rainbow Tables

UUIDs are generated from known inputs (author names). Could an attacker build a rainbow table?

**Mitigations**:

1. **Tenant-specific namespacing**:
   - Attacker needs to know tenant_id to build table
   - Different tenants have different UUIDs for same names

2. **Source-specific namespacing**:
   - Attacker needs to know source platform
   - WhatsApp vs Slack produce different UUIDs

3. **Escrow salting**:
   - Re-identification escrow uses tenant-specific salt
   - Different salt per tenant prevents cross-tenant attacks

**Residual Risk**:
- Single-tenant deployments with known tenant_id
- Attacker could build rainbow table for common names
- **Mitigation**: Enable escrow + require admin auth for re-id queries

---

## Alternatives Considered

### Alternative 1: Random UUIDs (Current)

**Pros**:
- Simple implementation
- No collision risk

**Cons**:
- Non-deterministic (different UUIDs per run)
- Cannot deduplicate across runs
- Cannot join historical data

**Verdict**: ❌ Rejected (fails determinism requirement)

### Alternative 2: Sequential IDs (Auto-increment)

**Pros**:
- Deterministic within single run
- Compact (smaller than UUIDs)

**Cons**:
- Not stable across runs (IDs change)
- Collision risk in multi-tenant scenarios
- Leaks information (ID=100 → 100th message)

**Verdict**: ❌ Rejected (fails multi-run determinism)

### Alternative 3: Hash-based IDs (SHA256)

**Pros**:
- Deterministic
- Cryptographically secure

**Cons**:
- Not UUID format (breaks compatibility)
- Longer than UUIDs (256 bits vs 128 bits)
- No standard library support

**Verdict**: ❌ Rejected (UUID5 provides same benefits with better compat)

### Alternative 4: UUID3 (MD5-based)

**Pros**:
- Deterministic (name-based like UUID5)
- Standard library support

**Cons**:
- MD5 is deprecated (security concerns)
- UUID5 (SHA1) is preferred standard

**Verdict**: ❌ Rejected (UUID5 is strictly better)

---

## References

- [RFC 4122: UUID Specification](https://www.rfc-editor.org/rfc/rfc4122)
- [Python uuid module](https://docs.python.org/3/library/uuid.html)
- [GDPR Right to Erasure](https://gdpr-info.eu/art-17-gdpr/)
- [UUID Collision Probability](https://en.wikipedia.org/wiki/Universally_unique_identifier#Collisions)

---

## Changelog

| Version | Date       | Changes                                     |
|---------|------------|---------------------------------------------|
| 1.0.0   | 2025-01-08 | Initial version with locked namespaces      |

---

## Approval

**Approved by**:
- [x] Architecture Team
- [x] Security Team
- [ ] Data Steward (pending)
- [ ] Legal/Compliance (pending)

**Effective Date**: 2025-01-08

**Review Date**: 2026-01-08 (annual review)

---

**Implementation**: `src/egregora/privacy/constants.py`

**Tests**: `tests/unit/test_deterministic_uuids.py`

**Migration**: See "Migration Path" section above
