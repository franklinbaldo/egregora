# ADR-003: Privacy Gate Capability Token

**Status**: ✅ Accepted

**Date**: 2025-01-08

**Authors**: Architecture Team

**Supersedes**: None

**Related**: ADR-002 (Deterministic UUIDs), IR v1 Schema

---

## Context

Egregora's **privacy-first architecture** requires that all personally identifiable information (PII) is anonymized **before** any data reaches LLM APIs. The privacy gate is the critical boundary that enforces this invariant.

### Current State (Before ADR-003)

The existing privacy implementation has several gaps:

1. **No Enforcement**: Nothing prevents code from bypassing the privacy gate
2. **Global State**: Privacy config is implicit (environment variables, global flags)
3. **No Tenant Isolation**: Privacy config is not scoped to specific tenants
4. **Unclear Contract**: Hard to tell if a function expects anonymized or raw data
5. **Testing Challenges**: Difficult to test privacy violations (no explicit failure mode)

**Example of current risk**:

```python
# Nothing prevents this dangerous pattern
def dangerous_function(table: ibis.Table):
    # Did privacy gate run? Unknown!
    # Does table contain author_raw? Unknown!
    send_to_llm(table)  # 🚨 Potential PII leak
```

### Requirements

1. **Explicit Capability**: Functions requiring anonymized data must demand proof of privacy gate execution
2. **Immutable Tokens**: Capability tokens cannot be forged or modified
3. **Tenant Isolation**: Each privacy pass is scoped to a single tenant
4. **Dependency Injection**: No global state; tokens passed explicitly
5. **Type Safety**: Mypy/pyright can verify privacy contract violations
6. **Testability**: Property tests can validate enforcement

---

## Decision

We will use a **capability token pattern** with immutable `PrivacyPass` objects.

### PrivacyPass: Immutable Capability Token

```python
from typing import NamedTuple
from datetime import datetime

class PrivacyPass(NamedTuple):
    """Unforgeable proof that privacy gate has executed.

    This is a capability token: possession grants access to privacy-protected operations.
    Cannot be constructed except via PrivacyGate.run().
    """
    ir_version: str      # IR schema version (e.g., "1.0.0")
    run_id: str          # Pipeline run ID for lineage tracking
    tenant_id: str       # Tenant scope (multi-tenant isolation)
    timestamp: datetime  # When privacy gate executed
```

**Key properties**:

1. **Immutable**: `NamedTuple` is frozen after creation
2. **Unforgeable**: Only `PrivacyGate.run()` creates instances
3. **Tenant-scoped**: Each pass is valid for exactly one tenant
4. **Auditable**: Contains run_id and timestamp for lineage tracking

### Decorator-Based Enforcement

Functions that require anonymized data use `@require_privacy_pass`:

```python
from egregora.privacy.gate import require_privacy_pass, PrivacyPass

@require_privacy_pass
def send_to_llm(
    table: ibis.Table,
    prompt: str,
    *,
    privacy_pass: PrivacyPass,  # Required kwarg
) -> str:
    """Send anonymized data to LLM API.

    Args:
        table: MUST be anonymized (author_uuid, not author_raw)
        prompt: LLM prompt
        privacy_pass: Capability token proving privacy gate ran

    Raises:
        RuntimeError: If privacy_pass is missing or invalid
    """
    # Decorator verifies privacy_pass is valid PrivacyPass instance
    # Safe to send table to LLM API
    return client.generate_content(prompt, table)
```

**Enforcement**:

```python
# ❌ This fails at runtime (no privacy_pass)
send_to_llm(raw_table, "Summarize this")
# RuntimeError: Missing required privacy_pass parameter

# ❌ This fails (forged token)
send_to_llm(raw_table, "Summarize", privacy_pass="fake")
# RuntimeError: privacy_pass must be PrivacyPass instance

# ✅ This succeeds (valid token)
anonymized_table, privacy_pass = PrivacyGate.run(raw_table, config, run_id)
send_to_llm(anonymized_table, "Summarize", privacy_pass=privacy_pass)
```

### PrivacyGate: Token Issuer

Only `PrivacyGate.run()` can create `PrivacyPass` instances:

```python
class PrivacyGate:
    """Privacy boundary enforcement.

    Critical Invariant:
        Only PrivacyGate.run() can create PrivacyPass tokens.
        Possession of a PrivacyPass proves:
        1. Input table conformed to IR schema
        2. PII was anonymized (author_raw → author_uuid)
        3. Tenant isolation was enforced
    """

    @staticmethod
    def run(
        table: ibis.Table,
        config: PrivacySettings,
        run_id: str,
    ) -> tuple[ibis.Table, PrivacyPass]:
        """Execute privacy gate and issue capability token.

        Args:
            table: Input table with author_raw (PII)
            config: Privacy configuration (tenant_id, policies)
            run_id: Pipeline run ID for lineage

        Returns:
            (anonymized_table, privacy_pass):
                - anonymized_table: author_uuid instead of author_raw
                - privacy_pass: Capability token for downstream functions

        Raises:
            ValueError: If table doesn't conform to IR schema
        """
        # 1. Validate IR schema
        validate_ir_schema(table)

        # 2. Anonymize authors (deterministic UUIDs)
        anonymized = anonymize_table(table, tenant_id=config.tenant_id)

        # 3. Detect PII (optional)
        if config.detect_pii:
            anonymized = detect_pii(anonymized)

        # 4. Issue capability token
        privacy_pass = PrivacyPass(
            ir_version="1.0.0",
            run_id=run_id,
            tenant_id=config.tenant_id,
            timestamp=datetime.now(timezone.utc),
        )

        return anonymized, privacy_pass
```

### PrivacySettings: Tenant-Scoped Policy

```python
@dataclass(frozen=True, slots=True)
class PrivacySettings:
    """Privacy policy configuration (immutable, tenant-scoped)."""

    tenant_id: str
    """Tenant identifier for multi-tenant isolation."""

    detect_pii: bool = True
    """Enable PII detection (phones, emails, addresses)."""

    allowed_media_domains: tuple[str, ...] = ()
    """Allowlist for media URLs (e.g., ('example.com',))."""

    enable_reidentification_escrow: bool = False
    """Store author_raw → author_uuid mapping for re-identification."""

    reidentification_retention_days: int = 90
    """How long to keep re-identification escrow (default: 90 days)."""
```

---

## Privacy Implications

### Capability-Based Security

The capability token pattern enforces privacy through **unforgeable proof**:

1. **No Global State**: Cannot bypass privacy gate via environment variables
2. **Explicit Dependencies**: Function signatures declare privacy requirements
3. **Audit Trail**: Every privacy_pass contains run_id and timestamp
4. **Type Safety**: Mypy can catch missing privacy_pass arguments

**Example**:

```python
# ✅ Compiler/type checker can verify this
def process_data(table: ibis.Table, privacy_pass: PrivacyPass) -> None:
    # Type checker knows privacy_pass is required
    pass

# ❌ Type checker catches missing privacy_pass
process_data(table)  # mypy error: Missing required keyword-only argument
```

### Re-identification Escrow

When `enable_reidentification_escrow=True`, the privacy gate stores a reversible mapping:

```sql
CREATE TABLE reidentification_escrow (
  tenant_id       VARCHAR NOT NULL,
  author_uuid     UUID NOT NULL,
  author_raw_hash VARCHAR NOT NULL,  -- HMAC(author_raw, tenant_salt)
  created_at      TIMESTAMP DEFAULT now(),
  expires_at      TIMESTAMP,
  created_by_run  UUID,
  PRIMARY KEY (tenant_id, author_uuid)
);
```

**Policy**:

- Mapping is **salted** (different salt per tenant)
- Access requires **tenant admin credentials**
- Subject to **retention policies** (default: 90 days)
- **Audit log** for all re-identification queries

**CLI**:

```bash
# Re-identify author (requires admin auth)
egregora privacy reidentify \
  --tenant=acme \
  --author-uuid=a1b2c3d4-... \
  --auth-token=$(get_admin_token)

# Output (if within retention window):
# author_raw: "Alice"
# created_at: 2025-01-08T12:00:00Z
# expires_at: 2025-04-08T12:00:00Z
```

---

## Consequences

### ✅ Positive

1. **Unforgeable Proof**:
   - Cannot bypass privacy gate (no global state to manipulate)
   - Cannot forge tokens (NamedTuple immutability)
   - Type checker verifies privacy contract

2. **Tenant Isolation**:
   - Each PrivacyPass scoped to single tenant
   - Cross-tenant data leaks prevented by design
   - Multi-tenant deployments safe by default

3. **Testability**:
   - Property tests can verify enforcement
   - Mock privacy passes for unit tests
   - Clear failure modes (RuntimeError if missing)

4. **Auditability**:
   - Every LLM call has associated run_id
   - Lineage tracking: which privacy gate run produced this data?
   - Compliance reporting: "All LLM calls used anonymized data"

5. **Type Safety**:
   - Mypy/pyright catch missing privacy_pass
   - Function signatures self-document privacy requirements
   - Refactoring-safe (type errors if removing privacy_pass)

### ⚠️ Negative

1. **Boilerplate**:
   - Every privacy-protected function needs `privacy_pass` parameter
   - Decorator adds runtime overhead (negligible)
   - More verbose than global state approach

2. **Migration Cost**:
   - Must update all existing functions to accept privacy_pass
   - Breaking change (not backward compatible)
   - Requires comprehensive test updates

3. **Developer Experience**:
   - New contributors must learn capability token pattern
   - More complex than simple "privacy flag" approach
   - Requires discipline (easy to forget @require_privacy_pass)

---

## Migration Path

### Phase 1: Add PrivacyPass (No Breaking Changes)

**Week 1**:

```python
# Add PrivacyPass and PrivacySettings (new code)
# src/egregora/privacy/gate.py

# Do NOT modify existing functions yet
```

**Tests**:

```python
# tests/unit/test_privacy_pass.py
def test_privacy_pass_immutability():
    """PrivacyPass cannot be modified after creation."""
    pass_obj = PrivacyPass(ir_version="1.0.0", run_id="test", tenant_id="default", timestamp=now())

    with pytest.raises(AttributeError):
        pass_obj.tenant_id = "malicious"  # Fails (immutable)
```

### Phase 2: Update Core Pipeline (Breaking Change)

**Week 2**:

```python
# Update pipeline functions to require privacy_pass
@require_privacy_pass
def write_posts_with_pydantic_agent(
    prompt: str,
    config: EgregoraConfig,
    context: WriterAgentContext,
    *,
    privacy_pass: PrivacyPass,  # New required parameter
) -> list[Path]:
    # ...
```

**Callsites**:

```python
# Before (no privacy enforcement)
write_posts_with_pydantic_agent(prompt, config, context)

# After (explicit capability token)
anonymized_table, privacy_pass = PrivacyGate.run(table, privacy_config, run_id)
write_posts_with_pydantic_agent(prompt, config, context, privacy_pass=privacy_pass)
```

### Phase 3: Update Tests

**Week 2**:

```python
# Add privacy_pass fixture
@pytest.fixture
def privacy_pass() -> PrivacyPass:
    return PrivacyPass(
        ir_version="1.0.0",
        run_id="test-run",
        tenant_id="test-tenant",
        timestamp=datetime.now(timezone.utc),
    )

# Update test callsites
def test_writer_agent(privacy_pass):
    result = write_posts_with_pydantic_agent(
        prompt, config, context,
        privacy_pass=privacy_pass,  # Explicit token
    )
```

### Phase 4: Enable Type Checking

**Week 3**:

```yaml
# pyproject.toml
[tool.mypy]
strict = true
warn_unused_ignores = true

# Catch missing privacy_pass arguments
disallow_untyped_defs = true
```

### Phase 5: Cleanup

**Week 4**:

- Remove any global privacy flags
- Update documentation
- Celebrate capability-based security! 🎉

---

## Validation

### Property Tests

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1), st.text(min_size=1))
def test_privacy_pass_immutable_with_random_values(tenant_id: str, run_id: str):
    """PrivacyPass is immutable regardless of input."""
    pass_obj = PrivacyPass(
        ir_version="1.0.0",
        run_id=run_id,
        tenant_id=tenant_id,
        timestamp=datetime.now(timezone.utc),
    )

    # Cannot modify any field
    with pytest.raises(AttributeError):
        pass_obj.tenant_id = "malicious"

    with pytest.raises(AttributeError):
        pass_obj.run_id = "forged"

def test_decorator_enforcement():
    """@require_privacy_pass rejects invalid tokens."""
    @require_privacy_pass
    def protected_func(*, privacy_pass: PrivacyPass) -> str:
        return "success"

    # ❌ Missing token
    with pytest.raises(RuntimeError, match="Missing required privacy_pass"):
        protected_func()

    # ❌ Forged token (wrong type)
    with pytest.raises(RuntimeError, match="must be PrivacyPass instance"):
        protected_func(privacy_pass="fake")

    # ✅ Valid token
    valid_pass = PrivacyPass("1.0.0", "test", "default", datetime.now(timezone.utc))
    assert protected_func(privacy_pass=valid_pass) == "success"

def test_privacy_gate_issues_valid_token():
    """PrivacyGate.run() creates valid PrivacyPass."""
    table = create_test_table()
    config = PrivacySettings(tenant_id="test")

    anonymized, privacy_pass = PrivacyGate.run(table, config, run_id="test-run")

    # Verify token properties
    assert isinstance(privacy_pass, PrivacyPass)
    assert privacy_pass.tenant_id == "test"
    assert privacy_pass.run_id == "test-run"
    assert privacy_pass.ir_version == "1.0.0"

def test_tenant_isolation():
    """Different tenants get different privacy passes."""
    table = create_test_table()

    config_a = PrivacySettings(tenant_id="tenant-a")
    config_b = PrivacySettings(tenant_id="tenant-b")

    _, pass_a = PrivacyGate.run(table, config_a, run_id="run-1")
    _, pass_b = PrivacyGate.run(table, config_b, run_id="run-1")

    assert pass_a.tenant_id != pass_b.tenant_id
    assert pass_a != pass_b  # Different tokens
```

### CI Checks

```yaml
# .github/workflows/ci.yml
- name: Validate privacy enforcement
  run: |
    # Run property tests
    uv run pytest tests/unit/test_privacy_pass.py -v

    # Type check privacy contracts
    uv run mypy src/egregora/privacy/ --strict

    # Verify no global privacy state
    ! grep -r "PRIVACY_ENABLED" src/  # Should not exist
```

---

## Security Considerations

### Token Forgery

**Threat**: Can an attacker forge a `PrivacyPass` to bypass privacy gate?

**Mitigations**:

1. **NamedTuple Immutability**:
   - Cannot modify fields after creation
   - Python enforces at runtime (AttributeError)

2. **Private Constructor**:
   - Only `PrivacyGate.run()` creates instances
   - No public `PrivacyPass()` constructor exposure

3. **Type Checking**:
   - Decorator verifies `isinstance(privacy_pass, PrivacyPass)`
   - Rejects strings, dicts, or other forgeries

**Residual Risk**:

- Malicious code could bypass decorator (remove `@require_privacy_pass`)
- **Mitigation**: Code review + CI linting (detect missing decorators)

### Tenant Isolation Bypass

**Threat**: Can a tenant use another tenant's privacy pass?

**Example**:

```python
# Tenant A's token
_, pass_a = PrivacyGate.run(table_a, PrivacySettings(tenant_id="tenant-a"), "run-1")

# Tenant B tries to use Tenant A's token
process_tenant_b_data(table_b, privacy_pass=pass_a)  # 🚨 Cross-tenant leak?
```

**Mitigations**:

1. **Explicit Validation** (recommended):
   ```python
   @require_privacy_pass
   def process_tenant_data(table: ibis.Table, *, privacy_pass: PrivacyPass) -> None:
       # Verify tenant_id matches table's tenant_id
       if privacy_pass.tenant_id != get_tenant_id(table):
           raise ValueError("Privacy pass tenant mismatch")
   ```

2. **Immutable Binding**:
   - PrivacyPass and table created together in `PrivacyGate.run()`
   - Hard to separate without refactoring

**Residual Risk**:

- Developer could manually mix tenants (low probability)
- **Mitigation**: Integration tests with multi-tenant data

### Re-identification Escrow Leaks

**Threat**: Unauthorized access to `reidentification_escrow` table.

**Mitigations**:

1. **Database Permissions**:
   ```sql
   -- Only privacy_admin role can read escrow
   GRANT SELECT ON reidentification_escrow TO privacy_admin;
   REVOKE SELECT ON reidentification_escrow FROM PUBLIC;
   ```

2. **Audit Logging**:
   ```sql
   CREATE TABLE escrow_access_log (
     access_id     UUID PRIMARY KEY,
     admin_user    VARCHAR NOT NULL,
     tenant_id     VARCHAR NOT NULL,
     author_uuid   UUID NOT NULL,
     accessed_at   TIMESTAMP DEFAULT now(),
     access_reason TEXT
   );
   ```

3. **Rate Limiting**:
   - Max 10 re-identification queries per tenant per day
   - Alert security team on excessive queries

4. **Encryption at Rest**:
   - `author_raw_hash` encrypted with tenant-specific key
   - Key stored in separate secrets manager

---

## Alternatives Considered

### Alternative 1: Global Privacy Flag

**Pattern**:

```python
# Global state
PRIVACY_GATE_RAN = False

def run_privacy_gate(table):
    global PRIVACY_GATE_RAN
    PRIVACY_GATE_RAN = True
    return anonymize(table)

def send_to_llm(table):
    if not PRIVACY_GATE_RAN:
        raise RuntimeError("Privacy gate not run")
    # ...
```

**Pros**:
- Simple implementation
- No parameter passing

**Cons**:
- Not thread-safe (multiple tenants share global state)
- Easy to bypass (just set `PRIVACY_GATE_RAN = True`)
- No tenant isolation
- Difficult to test (global mutable state)

**Verdict**: ❌ Rejected (fails tenant isolation + security requirements)

### Alternative 2: Context Manager

**Pattern**:

```python
with PrivacyGate(config) as privacy_context:
    anonymized_table = privacy_context.anonymize(table)
    send_to_llm(anonymized_table)  # Allowed inside context

# Outside context
send_to_llm(table)  # Raises error
```

**Pros**:
- Pythonic pattern
- Clear scope (inside/outside context)
- No parameter passing

**Cons**:
- Thread-local state (still global-ish)
- Cannot pass anonymized data outside context
- Difficult to compose (nested contexts?)

**Verdict**: ❌ Rejected (too restrictive for pipeline architecture)

### Alternative 3: Type-Tagged Data

**Pattern**:

```python
class AnonymizedTable:
    """Newtype wrapper for anonymized Ibis tables."""
    def __init__(self, table: ibis.Table):
        self._table = table

def send_to_llm(table: AnonymizedTable):
    # Type checker enforces AnonymizedTable
    pass
```

**Pros**:
- Type-safe (mypy can verify)
- No runtime overhead (after construction)
- Composable (pass AnonymizedTable anywhere)

**Cons**:
- No runtime enforcement (casts bypass type system)
- No tenant isolation metadata
- No audit trail (no run_id, timestamp)

**Verdict**: ❌ Rejected (insufficient metadata for compliance)

### Alternative 4: Capability Token (CHOSEN)

**Pattern**: See "Decision" section above.

**Pros**:
- Unforgeable (immutable NamedTuple)
- Tenant-scoped (explicit tenant_id)
- Auditable (run_id, timestamp)
- Type-safe (mypy verifiable)
- Testable (property tests)

**Cons**:
- More verbose (extra parameter)
- Migration cost (update all callsites)

**Verdict**: ✅ Accepted (best balance of security, usability, testability)

---

## References

- [Capability-based Security](https://en.wikipedia.org/wiki/Capability-based_security)
- [Object-capability Model](http://erights.org/elib/capability/ode/ode-capabilities.html)
- [Python NamedTuple Immutability](https://docs.python.org/3/library/typing.html#typing.NamedTuple)
- [GDPR Article 25: Data Protection by Design](https://gdpr-info.eu/art-25-gdpr/)
- [OWASP: Secure Design Principles](https://owasp.org/www-project-secure-design-principles/)

---

## Changelog

| Version | Date       | Changes                                     |
|---------|------------|---------------------------------------------|
| 1.0.0   | 2025-01-08 | Initial version with PrivacyPass capability token |

---

## Approval

**Approved by**:
- [x] Architecture Team
- [x] Security Team
- [ ] Privacy Officer (pending)
- [ ] Legal/Compliance (pending)

**Effective Date**: 2025-01-08

**Review Date**: 2026-01-08 (annual review)

---

**Implementation**: `src/egregora/privacy/gate.py`

**Tests**: `tests/unit/test_privacy_pass.py`

**Migration**: See "Migration Path" section above
