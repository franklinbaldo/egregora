# Egregora: Architecture Roadmap & North-Star Vision

**Date**: 2025-01-08 (Updated)
**Status**: Active Development Plan
**Timeline**: 90 days (12 weeks)
**Philosophy**: Modular, testable, pluggable, multi-tenant-ready platform

---

## North-Star Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    EGREGORA PLATFORM LAYERS                       │
└──────────────────────────────────────────────────────────────────┘

0. TENANT BOUNDARY (multi-tenant ready)
   tenant_id flows through: IR → Privacy → Agents → Renderers

1. SOURCES → ADAPTERS → IR v1
   ┌─────────┐      ┌─────────┐      ┌─────────────┐
   │WhatsApp │──────│ Adapter │──────│   IR v1     │
   │  Slack  │      │Registry │      │ (versioned) │
   │ Discord │      │+ Plugins│      │ + Lineage   │
   └─────────┘      └─────────┘      └─────────────┘
        ↓                ↓                   ↓
   adapter_meta()  Entry Points      Content-Addressed
                                      Checkpoints

2. PRIVACY BOUNDARY (capability-based, before LLM)
   ┌──────────────────────────────────────────┐
   │   PRIVACY GATE (PrivacyPass capability)  │
   │   UUID5 (namespaced) + PII detection     │
   │   ← Mandatory token before ANY LLM →     │
   └──────────────────────────────────────────┘

3. PROCESSING PIPELINE (IR → chunks → enrich → index)
   ┌──────┐  ┌──────┐  ┌────────┐  ┌─────┐
   │Chunk │→ │Enrich│→ │Embed   │→ │Index│
   └──────┘  └──────┘  └────────┘  └─────┘
      ↓          ↓          ↓          ↓
   Content-  Content-  Content-  Content-
   Addressed Addressed Addressed Addressed
   + Runs    + Runs    + Runs    + Runs

4. AGENTS (orchestrators with injected deps)
   ┌────────┐  ┌────────┐
   │ Editor │  │Ranking │
   │ Agent  │  │ Agent  │
   └────────┘  └────────┘
       ↓           ↓
   Pure Tools   Audit Envelope
   + Deps Bag   (run_id, model, prompt_hash)

5. RENDERERS (terminal consumers)
   ┌────────┐  ┌──────┐
   │ MkDocs │  │ Hugo │
   └────────┘  └──────┘
       ↓           ↓
   Read-only Materialized Views

6. OBSERVABILITY (OpenTelemetry)
   ┌─────────────────────────────────────┐
   │  Traces + Logs by run_id            │
   │  egregora runs tail                 │
   │  Mean-time-to-explain < 5min        │
   └─────────────────────────────────────┘
```

---

## Core Data Contracts

### IR v1 Schema (Versioned & Locked)

**File**: `schema/ir_v1.sql` (lockfile)

```sql
CREATE TABLE ir_v1 (
  -- Identity
  event_id        UUID PRIMARY KEY,
  tenant_id       VARCHAR NOT NULL,
  source          VARCHAR NOT NULL,  -- 'whatsapp', 'slack', etc.

  -- Threading
  thread_id       UUID NOT NULL,
  msg_id          VARCHAR NOT NULL,

  -- Temporal
  ts              TIMESTAMP NOT NULL,

  -- Authors (privacy boundary)
  author_raw      VARCHAR NOT NULL,  -- Original name
  author_uuid     UUID NOT NULL,     -- Anonymized (UUID5)

  -- Content
  text            TEXT,
  media_url       VARCHAR,
  media_type      VARCHAR,

  -- Metadata
  attrs           JSON,
  pii_flags       JSON,

  -- Lineage
  created_at      TIMESTAMP DEFAULT now(),
  created_by_run  UUID REFERENCES runs(run_id)
);
```

**File**: `schema/ir_v1.json` (Ibis schema dump)

```json
{
  "event_id": "uuid",
  "tenant_id": "string",
  "source": "string",
  "thread_id": "uuid",
  "msg_id": "string",
  "ts": "timestamp",
  "author_raw": "string",
  "author_uuid": "uuid",
  "text": "string",
  "media_url": "string",
  "media_type": "string",
  "attrs": "json",
  "pii_flags": "json",
  "created_at": "timestamp",
  "created_by_run": "uuid"
}
```

**CI Check**: Fail if drift detected

```bash
# .github/workflows/ci.yml
- name: Check IR v1 schema drift
  run: |
    uv run python scripts/check_ir_schema.py
    # Compares current CONVERSATION_SCHEMA against schema/ir_v1.json
```

---

### Runs & Lineage Tables

**Runs Table** (operational metadata):

```sql
CREATE TABLE runs (
  run_id              UUID PRIMARY KEY,
  stage               VARCHAR NOT NULL,
  tenant_id           VARCHAR,
  started_at          TIMESTAMP NOT NULL,
  finished_at         TIMESTAMP,

  -- Input fingerprint
  input_fingerprint   VARCHAR NOT NULL,  -- SHA256 of input IR

  -- Code version
  code_ref            VARCHAR,           -- git commit SHA
  config_hash         VARCHAR,           -- SHA256 of config JSON

  -- Metrics
  rows_in             INTEGER,
  rows_out            INTEGER,
  llm_calls           INTEGER DEFAULT 0,
  tokens              INTEGER DEFAULT 0,

  -- Status
  status              VARCHAR NOT NULL,  -- 'running', 'completed', 'failed', 'degraded'
  error               TEXT,

  -- Trace
  trace_id            VARCHAR            -- OpenTelemetry trace ID
);
```

**Lineage Table** (DAG tracking):

```sql
CREATE TABLE lineage (
  child_run_id   UUID REFERENCES runs(run_id),
  parent_run_id  UUID REFERENCES runs(run_id),
  PRIMARY KEY (child_run_id, parent_run_id)
);
```

**CLI Usage**:
```bash
egregora runs tail             # Show last 10 runs
egregora runs show <run_id>    # Detailed run info
egregora runs lineage <run_id> # Show DAG
```

---

### UUID5 Namespaces (Deterministic, Immutable)

**File**: `src/egregora/privacy/constants.py`

```python
"""UUID5 namespaces for deterministic identity generation.

CRITICAL: These UUIDs are immutable. Changing them breaks re-identification
and multi-tenant joins. See ADR-002 for policy.
"""

import uuid

# Namespace for author identities
NS_AUTHORS = uuid.UUID('a0eef1c4-7b8d-4f3e-9c6a-1d2e3f4a5b6c')

# Namespace for thread identities
NS_THREADS = uuid.UUID('b1ffa2d5-8c9e-5a4f-ad7b-2e3f4a5b6c7d')

# Namespace for media identities
NS_MEDIA = uuid.UUID('c2aab3e6-9daf-6b5a-be8c-3f4a5b6c7d8e')

def deterministic_author_uuid(tenant_id: str, source: str, author_raw: str) -> uuid.UUID:
    """Generate deterministic author UUID.

    Args:
        tenant_id: Tenant identifier (for multi-tenant isolation)
        source: Source platform ('whatsapp', 'slack')
        author_raw: Original author name

    Returns:
        UUID5 hash (stable across re-ingests)
    """
    key = f"{tenant_id}:{source}:{author_raw}"
    return uuid.uuid5(NS_AUTHORS, key)

def deterministic_thread_uuid(tenant_id: str, source: str, thread_key: str) -> uuid.UUID:
    """Generate deterministic thread UUID."""
    key = f"{tenant_id}:{source}:{thread_key}"
    return uuid.uuid5(NS_THREADS, key)
```

**ADR**: `docs/architecture/adr-002-deterministic-uuids.md`

---

## Quick Wins (Do Immediately) ⚡

### QW-0: IR v1 Lockfile (30 min)
**Status**: [ ] Not Started

**Tasks**:
1. Create `schema/ir_v1.sql` with canonical IR schema
2. Create `schema/ir_v1.json` (Ibis schema dump)
3. Add CI check: `scripts/check_ir_schema.py`
4. Fail build on drift

**Files**:
- `schema/ir_v1.sql` (new)
- `schema/ir_v1.json` (new)
- `scripts/check_ir_schema.py` (new)
- `.github/workflows/ci.yml` (update)

**Success**: CI fails if CONVERSATION_SCHEMA != IR v1 lockfile

---

### QW-1: Fail Build on Pandas Import (5 min)
**Status**: [ ] Not Started

```bash
# Turn on pre-commit check in CI
# .github/workflows/ci.yml
- name: Check no pandas escape
  run: uv run python tests/linting/test_no_pandas_escape.py
```

**Success**: CI fails if `pd.` appears outside TYPE_CHECKING/compat/testing

---

### QW-2: Slack Adapter Fail-Fast (10 min)
**Status**: [ ] Not Started

**File**: `src/egregora/ingestion/slack_input.py`

```python
def parse_source(self, input_path: Path) -> ibis.Table:
    """Parse Slack export to IR table."""
    if input_path.exists() and self._has_data(input_path):
        raise NotImplementedError(
            "Slack adapter is a stub. Implement parsing logic "
            "or use WhatsApp adapter for now."
        )
    return self._empty_table()
```

**Success**: No silent empty results in CI/production

---

### QW-3: Privacy Gate as Capability Token (45 min)
**Status**: [ ] Not Started

**File**: `src/egregora/privacy/gate.py` (new)

```python
from typing import NamedTuple
from functools import wraps

class PrivacyPass(NamedTuple):
    """Capability token proving privacy gate ran."""
    ir_version: str      # "v1"
    run_id: str          # Run ID from runs table
    tenant_id: str       # Tenant isolation
    timestamp: datetime  # When gate ran

def require_privacy_pass(func):
    """Decorator: Fail if privacy_pass not provided."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        privacy_pass = kwargs.get("privacy_pass")
        if not isinstance(privacy_pass, PrivacyPass):
            raise RuntimeError(
                f"{func.__name__} requires PrivacyPass capability. "
                "Run PrivacyGate.run() first and pass privacy_pass=... kwarg."
            )
        return func(*args, **kwargs)
    return wrapper

class PrivacyGate:
    """Privacy boundary enforced via capability token."""

    @staticmethod
    def run(table: ibis.Table, config: PrivacyConfig, run_id: str) -> tuple[ibis.Table, PrivacyPass]:
        """Anonymize + PII check. Returns table + capability token.

        Returns:
            (anonymized_table, privacy_pass)
        """
        logger.info("🔒 Privacy gate: Starting", run_id=run_id)

        # 1. Anonymize authors (UUID5)
        table = anonymize_authors(table, config.tenant_id)

        # 2. Detect & flag PII
        table = detect_pii(table, config.pii_patterns)

        # 3. Apply media allow/deny lists
        table = filter_media(table, config.media_allowlist)

        # 4. Create capability token
        privacy_pass = PrivacyPass(
            ir_version="v1",
            run_id=run_id,
            tenant_id=config.tenant_id,
            timestamp=datetime.now()
        )

        logger.info("✓ Privacy gate: Complete", run_id=run_id)
        return table, privacy_pass
```

**Usage**:
```python
# Pipeline runner
table, privacy_pass = PrivacyGate.run(table, config, run_id)

# LLM stage MUST receive privacy_pass
@require_privacy_pass
def enrich_media(table: ibis.Table, *, privacy_pass: PrivacyPass) -> ibis.Table:
    """Enriches media - requires privacy pass."""
    # LLM calls here are safe
    ...

# Call with token
enriched = enrich_media(table, privacy_pass=privacy_pass)
```

**Success**:
- [ ] Runtime error if LLM stage called without `privacy_pass=...`
- [ ] No global state (testable with DI)

---

### QW-4: Deterministic UUID5 Namespaces (20 min)
**Status**: [ ] Not Started

**Tasks**:
1. Create `src/egregora/privacy/constants.py` with frozen UUID5 namespaces
2. Add ADR: `docs/architecture/adr-002-deterministic-uuids.md`
3. Update anonymizer to use namespaced UUIDs

**Files**:
- `src/egregora/privacy/constants.py` (new)
- `docs/architecture/adr-002-deterministic-uuids.md` (new)
- `src/egregora/privacy/anonymizer.py` (update)

**Success**:
- [ ] Re-ingest same data → identical author_uuid
- [ ] Multi-tenant isolation via tenant_id prefix

---

### QW-5: Minimal OpenTelemetry Bootstrap (30 min)
**Status**: [ ] Not Started

**File**: `src/egregora/utils/telemetry.py`

```python
"""OpenTelemetry instrumentation (optional, off by default)."""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def configure_otel():
    """Configure OpenTelemetry if EGREGORA_OTEL=1."""
    if os.getenv("EGREGORA_OTEL") != "1":
        return None

    provider = TracerProvider()

    # Console exporter (default)
    console_exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # OTLP exporter (if endpoint configured)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(__name__)

# Usage in CLI
tracer = configure_otel()

if tracer:
    with tracer.start_as_current_span("pipeline.run", attributes={"run_id": run_id}):
        run_pipeline(...)
```

**CLI Usage**:
```bash
# Off by default
egregora pipeline run input.zip

# Enable with console output
EGREGORA_OTEL=1 egregora pipeline run input.zip

# Enable with OTLP export (Jaeger, Honeycomb, etc.)
EGREGORA_OTEL=1 OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
  egregora pipeline run input.zip
```

**Success**:
- [ ] Traces emitted to console when `EGREGORA_OTEL=1`
- [ ] Off by default (zero overhead)

---

## Week 1 Checklist (Copy/Paste to Issues)

**Goal**: Green-to-green foundation with IR v1, privacy capability, and lineage tracking.

### Tasks

- [ ] **QW-0**: Commit IR v1 lockfile (`schema/ir_v1.sql` + `schema/ir_v1.json`) + CI check
- [ ] **QW-1**: Turn on no-pandas CI enforcement
- [ ] **QW-2**: Slack adapter fail-fast (raise NotImplementedError)
- [ ] **QW-3**: PrivacyPass capability token + `@require_privacy_pass` decorator
- [ ] **QW-4**: UUID5 namespaces (`privacy/constants.py` + ADR-002)
- [ ] **QW-5**: OpenTelemetry bootstrap (opt-in via `EGREGORA_OTEL=1`)
- [ ] **Runs table**: Create `runs` + `lineage` tables in DuckDB
- [ ] **Golden test**: WhatsApp ZIP → IR v1 → privacy → chunks (no enrichment) → site skeleton
- [ ] **Docs**: Add `docs/architecture/ir-v1-spec.md`

### Acceptance Criteria

- [ ] CI fails on IR schema drift
- [ ] CI fails on pandas imports outside `compat/`
- [ ] `egregora runs tail` shows last 10 runs
- [ ] Property test: re-ingest → identical `event_id` and `author_uuid`
- [ ] WhatsApp golden test runs end-to-end (<5 min)

---

## Priority A: Platform Seams & Plugins (Weeks 1-2)

### A.1: Adapter Plugin System (2 days)
**Status**: [ ] Not Started

**Goal**: Third-party adapters via entry points + `adapter_meta()`

**Implementation**:

1. **Adapter Protocol** (`src/egregora/adapters/base.py`):
```python
from typing import Protocol, TypedDict

class AdapterMeta(TypedDict):
    """Metadata for adapter discovery."""
    name: str             # 'whatsapp', 'slack', etc.
    version: str          # Semantic version
    source: str           # Platform name
    doc_url: str          # Documentation URL
    ir_version: str       # IR version supported ('v1')

class SourceAdapter(Protocol):
    """Adapter contract for all sources."""

    def parse_source(self, input_path: Path) -> ibis.Table:
        """Parse source to IR v1 table."""
        ...

    def adapter_meta(self) -> AdapterMeta:
        """Return adapter metadata."""
        ...
```

2. **Plugin Loader** (`src/egregora/adapters/registry.py`):
```python
from importlib.metadata import entry_points

class AdapterRegistry:
    def __init__(self):
        self._adapters = {}
        self._load_builtin()
        self._load_plugins()

    def _load_plugins(self):
        """Load third-party adapters from entry points."""
        for ep in entry_points(group='egregora.adapters'):
            try:
                adapter_cls = ep.load()
                adapter = adapter_cls()
                meta = adapter.adapter_meta()

                # Validate IR version
                if meta['ir_version'] != 'v1':
                    logger.warning(f"Adapter {ep.name} requires IR {meta['ir_version']}, skipping")
                    continue

                self._adapters[ep.name] = adapter
                logger.info(f"Loaded adapter: {ep.name} v{meta['version']}")
            except Exception as e:
                logger.error(f"Failed to load adapter {ep.name}: {e}")
```

3. **CLI Command** (`egregora adapters list`):
```python
@app.command()
def list_adapters(as_table: bool = typer.Option(True)):
    """List available adapters."""
    registry = AdapterRegistry()
    adapters = [a.adapter_meta() for a in registry._adapters.values()]

    if as_table:
        # Print as rich table
        table = Table(title="Egregora Adapters")
        table.add_column("Name")
        table.add_column("Version")
        table.add_column("IR")
        table.add_column("Docs")

        for meta in adapters:
            table.add_row(
                meta['name'],
                meta['version'],
                meta['ir_version'],
                meta['doc_url']
            )
        console.print(table)
```

**Cookiecutter Template**: `cookiecutter-egregora-adapter`

```bash
cookiecutter gh:franklinbaldo/cookiecutter-egregora-adapter
# Generates skeleton: my_adapter/adapter.py, pyproject.toml, tests/
```

**Tests**:
- `tests/unit/test_adapter_registry.py` (plugin discovery)
- `tests/unit/test_adapter_meta.py` (metadata validation)

**Success**:
- [ ] Third-party adapter loads via entry point
- [ ] `egregora adapters list` shows all adapters
- [ ] Cookiecutter template documented

---

### A.2: Content-Addressed Checkpoints (2 days)
**Status**: [ ] Not Started

**Goal**: Fingerprint-based checkpoints (no custom markers)

**Implementation**:

```python
# src/egregora/pipeline/checkpoint.py
import hashlib
from pathlib import Path

def fingerprint_stage_input(
    table: ibis.Table,
    config: Config,
    code_ref: str
) -> str:
    """Generate SHA256 fingerprint for stage input.

    Args:
        table: Input IR table
        config: Stage configuration
        code_ref: Git commit SHA (from git rev-parse HEAD)

    Returns:
        SHA256 hex string (stable across runs)
    """
    # Project stable columns (exclude created_at, etc.)
    stable_cols = ["event_id", "tenant_id", "source", "text", "author_uuid"]
    projection = table.select(stable_cols).order_by("event_id")

    # Hash IR content
    ir_hash = hashlib.sha256(projection.to_parquet().read()).hexdigest()

    # Hash config
    config_str = json.dumps(config.dict(), sort_keys=True)
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()

    # Combine
    combined = f"{ir_hash}:{config_hash}:{code_ref}"
    return hashlib.sha256(combined.encode()).hexdigest()

def checkpoint_path(stage_name: str, fingerprint: str) -> Path:
    """Get checkpoint path for stage + fingerprint."""
    return Path(".egregora/checkpoints") / stage_name / f"{fingerprint}.parquet"

def load_checkpoint(stage_name: str, fingerprint: str) -> ibis.Table | None:
    """Load checkpoint if exists."""
    path = checkpoint_path(stage_name, fingerprint)
    if path.exists():
        logger.info(f"✓ Loading checkpoint: {stage_name} ({fingerprint[:8]})")
        return ibis.read_parquet(path)
    return None

def save_checkpoint(table: ibis.Table, stage_name: str, fingerprint: str):
    """Save checkpoint."""
    path = checkpoint_path(stage_name, fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path)
    logger.info(f"✓ Saved checkpoint: {stage_name} ({fingerprint[:8]})")
```

**CLI**:
```bash
# Run up to specific stage (materializes checkpoint)
egregora pipeline run --up-to=embed input.zip

# Cache management
egregora cache gc --keep-last=5    # Keep 5 most recent per stage
egregora cache gc --max-size=10GB  # Prune by total size
egregora cache clear --stage=enrich
```

**Tests**:
- `tests/unit/test_checkpoint_fingerprint.py` (determinism)
- `tests/unit/test_checkpoint_gc.py` (garbage collection)

**Success**:
- [ ] Same input → same fingerprint (deterministic)
- [ ] `--up-to=<stage>` materializes checkpoint
- [ ] `cache gc` prunes stale checkpoints

---

### A.3: IR Schema Validation (1 day)
**Status**: [ ] Not Started

**Goal**: Runtime validation at adapter boundary

**File**: `src/egregora/database/validation.py`

```python
from pydantic import BaseModel, Field, ValidationError

class IRv1Row(BaseModel):
    """Runtime validator for IR v1 rows."""
    event_id: uuid.UUID
    tenant_id: str = Field(min_length=1)
    source: str = Field(pattern=r'^[a-z]+$')
    thread_id: uuid.UUID
    msg_id: str
    ts: datetime
    author_raw: str
    author_uuid: uuid.UUID
    text: str | None = None
    media_url: str | None = None
    media_type: str | None = None
    attrs: dict | None = None
    pii_flags: dict | None = None

    class Config:
        frozen = True

def validate_ir_schema(table: ibis.Table) -> None:
    """Validate table schema matches IR v1 lockfile.

    Raises:
        SchemaError: If schema doesn't match IR v1
    """
    # 1. Compile-time check (Ibis schema)
    expected_schema = load_ir_v1_schema()  # From schema/ir_v1.json
    actual_schema = table.schema()

    if expected_schema != actual_schema:
        diff = schema_diff(expected_schema, actual_schema)
        raise SchemaError(f"IR v1 schema mismatch:\n{diff}")

    # 2. Runtime check (Pydantic validation on sample)
    sample = table.limit(100).execute()
    for idx, row in enumerate(sample.itertuples()):
        try:
            IRv1Row(**row._asdict())
        except ValidationError as e:
            raise SchemaError(f"IR v1 validation failed at row {idx}: {e}")

def adapter_output_validator(table: ibis.Table) -> ibis.Table:
    """Validate adapter output before pipeline.

    Usage:
        table = adapter.parse_source(input_path)
        table = adapter_output_validator(table)  # ← Enforce contract
    """
    validate_ir_schema(table)
    return table
```

**Tests**:
- `tests/unit/test_ir_validation.py`

**Success**:
- [ ] Invalid schema rejected with clear error
- [ ] Sample rows validated with Pydantic

---

## Priority B: Privacy as a Capability (Weeks 2-3)

### B.1: PrivacyPass + Re-identification Policy (2 days)
**Status**: [ ] Not Started

**Goal**: Capability-based privacy gate + re-id escrow documentation

**Implementation** (see QW-3 above)

**ADR**: `docs/architecture/adr-002-privacy-gate.md`

```markdown
# ADR-002: Privacy Gate as Capability Token

## Status
Accepted (2025-01-08)

## Context
We need to guarantee NO raw PII reaches LLM APIs. Previous approach used
global flag `_privacy_gate_run`, which:
- Made testing difficult (global state)
- Couldn't track which run performed anonymization
- No multi-tenant isolation

## Decision
Replace global flag with **capability token** (`PrivacyPass`):

```python
class PrivacyPass(NamedTuple):
    ir_version: str
    run_id: str
    tenant_id: str
    timestamp: datetime
```

Any function touching LLM APIs MUST accept `privacy_pass=...` kwarg
and validate with `@require_privacy_pass` decorator.

## Re-identification Escrow Policy
By default, Egregora performs **one-way anonymization** (UUID5 deterministic).
The mapping `author_raw → author_uuid` is NOT persisted.

**Optional**: Tenants may enable re-identification escrow:
- Salted mapping stored in separate encrypted table
- Requires explicit opt-in: `privacy.enable_reidentification=true`
- Mapping accessible only to tenant admin via CLI
- Subject to data retention policies

## Consequences
**Positive**:
- Testable (no global state)
- Auditable (tracks which run anonymized)
- Multi-tenant safe (tenant_id in token)

**Negative**:
- Every LLM function needs `privacy_pass=...` kwarg
- Slightly more verbose API
```

**Tests**:
- `tests/unit/test_privacy_pass.py` (capability validation)
- `tests/integration/test_privacy_enforcement.py` (end-to-end)

**Success**:
- [ ] All LLM stages decorated with `@require_privacy_pass`
- [ ] Property test: 0% LLM calls without PrivacyPass
- [ ] ADR documents re-id escrow policy

---

### B.2: Namespaced UUID5 + Multi-Tenant Isolation (1 day)
**Status**: [ ] Not Started

**Implementation** (see QW-4 above)

**Tests**:
```python
# tests/unit/test_deterministic_uuids.py
from hypothesis import given, strategies as st

@given(st.text(min_size=1), st.text(min_size=1))
def test_uuid5_determinism(tenant_id: str, author: str):
    """Same inputs always produce same UUID."""
    uuid1 = deterministic_author_uuid(tenant_id, "whatsapp", author)
    uuid2 = deterministic_author_uuid(tenant_id, "whatsapp", author)
    assert uuid1 == uuid2

def test_tenant_isolation():
    """Different tenants get different UUIDs for same author."""
    uuid_tenant_a = deterministic_author_uuid("tenant-a", "whatsapp", "Alice")
    uuid_tenant_b = deterministic_author_uuid("tenant-b", "whatsapp", "Alice")
    assert uuid_tenant_a != uuid_tenant_b

def test_re_ingest_stability(whatsapp_zip: Path):
    """Re-ingesting same data produces identical UUIDs."""
    table1 = parse_and_anonymize(whatsapp_zip, tenant_id="test")
    table2 = parse_and_anonymize(whatsapp_zip, tenant_id="test")

    # Hash first 1000 rows
    hash1 = hashlib.sha256(table1.select("event_id", "author_uuid").limit(1000).to_parquet()).hexdigest()
    hash2 = hashlib.sha256(table2.select("event_id", "author_uuid").limit(1000).to_parquet()).hexdigest()

    assert hash1 == hash2
```

**Success**:
- [ ] Determinism property test passes (1000+ inputs)
- [ ] Re-ingest test: identical UUIDs for same data

---

## Priority C: Data Layer Discipline (Weeks 3-4)

### C.1: View Registry + SQL Stage Views (2 days)
**Status**: [ ] Not Started

**Goal**: Centralized view registry + allow SQL when needed

**File**: `src/egregora/pipeline/views.py`

```python
"""Canonical view registry for pipeline stages.

Stages reference views by name, not file paths. This allows:
- SQL optimization when needed (performance)
- Centralized view definitions
- Easy testing (swap views for mocks)
"""

from typing import Callable
import ibis

ViewBuilder = Callable[[ibis.Table], ibis.Table]

class ViewRegistry:
    """Registry of canonical pipeline views."""

    def __init__(self):
        self._views: dict[str, ViewBuilder] = {}

    def register(self, name: str):
        """Decorator to register a view."""
        def decorator(func: ViewBuilder):
            self._views[name] = func
            return func
        return decorator

    def get(self, name: str) -> ViewBuilder:
        """Get view builder by name."""
        if name not in self._views:
            raise KeyError(f"View not found: {name}")
        return self._views[name]

# Global registry
views = ViewRegistry()

# Example: Ibis view
@views.register("chunks")
def chunks_view(ir: ibis.Table) -> ibis.Table:
    """Chunk conversations into windows."""
    return ir.mutate(
        chunk_idx=ibis.row_number().over(
            partition_by="thread_id",
            order_by="ts"
        )
    )

# Example: SQL view (for performance)
@views.register("chunks_optimized")
def chunks_sql(ir: ibis.Table) -> ibis.Table:
    """Optimized chunking with raw SQL."""
    return ir.sql("""
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY thread_id
                ORDER BY ts
            ) AS chunk_idx
        FROM ir
    """)

# Usage in pipeline
def chunking_stage(storage: StorageManager) -> ibis.Table:
    """Chunking stage using view registry."""
    ir = storage.read_table("ir_v1")
    chunks_builder = views.get("chunks")
    return chunks_builder(ir)
```

**Success**:
- [ ] All stages use view registry
- [ ] Can swap Ibis ↔ SQL views transparently
- [ ] Benchmark shows SQL view performance gain

---

### C.2: StorageManager + No Raw SQL (2 days)
**Status**: [ ] Not Started

**Goal**: Centralized DuckDB access via `StorageManager`

**File**: `src/egregora/database/storage.py`

```python
class StorageManager:
    """Centralized DuckDB connection + Ibis helpers."""

    def __init__(self, db_path: Path | None = None):
        self.conn = duckdb.connect(str(db_path) if db_path else ":memory:")
        self.ibis_conn = ibis.duckdb.connect(self.conn)

    def read_table(self, name: str) -> ibis.Table:
        """Read table as Ibis view."""
        return self.ibis_conn.table(name)

    def write_table(
        self,
        table: ibis.Table,
        name: str,
        mode: str = "replace",
        checkpoint: bool = True
    ):
        """Write Ibis table to DuckDB."""
        # Write to parquet (checkpoint)
        if checkpoint:
            parquet_path = Path(".egregora/data") / f"{name}.parquet"
            parquet_path.parent.mkdir(exist_ok=True)
            table.to_parquet(parquet_path)

            # Load into DuckDB from parquet
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {name} AS "
                f"SELECT * FROM read_parquet('{parquet_path}')"
            )
        else:
            # Direct write (no checkpoint)
            table.to_parquet(f"/tmp/{name}.parquet")
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {name} AS "
                f"SELECT * FROM read_parquet('/tmp/{name}.parquet')"
            )

    def execute_view(self, view_name: str, builder: ViewBuilder, input_table: str) -> ibis.Table:
        """Execute view and optionally materialize."""
        input_ir = self.read_table(input_table)
        result = builder(input_ir)
        self.write_table(result, view_name)
        return result

# Dependency injection
def enrich_stage(storage: StorageManager, config: Config, privacy_pass: PrivacyPass):
    """Enrichment stage with injected storage."""
    table = storage.read_table("conversations")
    enriched = enrich_media(table, config, privacy_pass=privacy_pass)
    storage.write_table(enriched, "conversations_enriched")
```

**Tests**:
- `tests/unit/test_storage_manager.py`

**Success**:
- [ ] All stages use `StorageManager` (no raw SQL)
- [ ] Checkpoints saved to `.egregora/data/`

---

## Priority D: Observability & Runs Tracking (Weeks 4-5)

### D.1: Runs Table + CLI (2 days)
**Status**: [ ] Not Started

**Goal**: Every stage writes to `runs` table

**Implementation**:

```python
# src/egregora/pipeline/runner.py
import uuid
from datetime import datetime

def run_stage_with_tracking(
    stage_name: str,
    stage_func: Callable,
    input_table: ibis.Table,
    config: Config,
    storage: StorageManager
) -> ibis.Table:
    """Run stage with automatic runs table tracking."""

    # Generate run ID
    run_id = str(uuid.uuid4())

    # Compute input fingerprint
    code_ref = get_git_commit()  # git rev-parse HEAD
    fingerprint = fingerprint_stage_input(input_table, config, code_ref)

    # Check checkpoint
    checkpoint = load_checkpoint(stage_name, fingerprint)
    if checkpoint:
        logger.info(f"✓ Using checkpoint for {stage_name}")
        record_run(storage, run_id, stage_name, "completed", "checkpoint", fingerprint)
        return checkpoint

    # Insert run (started)
    record_run(storage, run_id, stage_name, "running", None, fingerprint)

    try:
        # Execute stage
        start_time = datetime.now()
        result = stage_func(input_table, config, run_id=run_id)
        duration = (datetime.now() - start_time).total_seconds()

        # Update run (completed)
        record_run(
            storage, run_id, stage_name, "completed", None, fingerprint,
            rows_in=input_table.count().execute(),
            rows_out=result.count().execute(),
            duration=duration
        )

        # Save checkpoint
        save_checkpoint(result, stage_name, fingerprint)

        return result

    except Exception as e:
        # Update run (failed)
        record_run(storage, run_id, stage_name, "failed", str(e), fingerprint)
        raise

def record_run(
    storage: StorageManager,
    run_id: str,
    stage: str,
    status: str,
    error: str | None,
    fingerprint: str,
    **metrics
):
    """Insert/update run in runs table."""
    storage.conn.execute("""
        INSERT INTO runs (run_id, stage, status, error, input_fingerprint, ...)
        VALUES (?, ?, ?, ?, ?, ...)
        ON CONFLICT (run_id) DO UPDATE SET
            status = excluded.status,
            error = excluded.error,
            finished_at = now(),
            ...
    """, [run_id, stage, status, error, fingerprint, ...])
```

**CLI Commands**:

```python
# src/egregora/cli/runs.py
@app.command()
def tail(n: int = 10):
    """Show last N runs."""
    storage = StorageManager()
    runs = storage.conn.execute("""
        SELECT run_id, stage, status, started_at, rows_in, rows_out
        FROM runs
        ORDER BY started_at DESC
        LIMIT ?
    """, [n]).fetchall()

    table = Table(title=f"Last {n} Runs")
    table.add_column("Run ID")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Started")
    table.add_column("Rows In")
    table.add_column("Rows Out")

    for row in runs:
        table.add_row(*[str(x) for x in row])

    console.print(table)

@app.command()
def show(run_id: str):
    """Show detailed run info."""
    storage = StorageManager()
    run = storage.conn.execute("""
        SELECT * FROM runs WHERE run_id = ?
    """, [run_id]).fetchone()

    if not run:
        print(f"Run not found: {run_id}")
        return

    # Pretty print run details
    console.print(Panel(f"""
        Run ID: {run['run_id']}
        Stage: {run['stage']}
        Status: {run['status']}
        Started: {run['started_at']}
        Finished: {run['finished_at']}
        Duration: {run['finished_at'] - run['started_at']}

        Rows In: {run['rows_in']}
        Rows Out: {run['rows_out']}
        LLM Calls: {run['llm_calls']}
        Tokens: {run['tokens']}

        Input Fingerprint: {run['input_fingerprint']}
        Code Ref: {run['code_ref']}
        Config Hash: {run['config_hash']}

        Error: {run['error'] or 'None'}
    """, title="Run Details"))
```

**Success**:
- [ ] Every stage writes to `runs` table
- [ ] `egregora runs tail` shows recent runs
- [ ] `egregora runs show <run_id>` shows details
- [ ] Mean-time-to-explain < 5 min using runs data

---

### D.2: OpenTelemetry Integration (1 day)
**Status**: [ ] Not Started

**Implementation** (see QW-5 above)

**Enrichment**:
```python
# Add trace_id to runs table
with tracer.start_as_current_span("stage.enrich", attributes={"run_id": run_id}) as span:
    trace_id = span.get_span_context().trace_id

    # Record in runs
    record_run(storage, run_id, "enrich", "running", None, fingerprint, trace_id=hex(trace_id))

    # Execute stage
    result = enrich_media(table, config, privacy_pass=privacy_pass)
```

**Success**:
- [ ] Traces link to runs via `trace_id`
- [ ] `EGREGORA_OTEL=1` emits spans to console

---

## Priority E-J: Continue as in Original Roadmap

(Weeks 5-12 priorities remain unchanged from original roadmap, with additions from architectural deltas integrated)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Silent schema drift** | Medium | High | IR v1 lockfile + CI check + `doctor` command |
| **Privacy bypass** | Low | Critical | PrivacyPass capability + `@require_privacy_pass` + staged tests |
| **LLM cost spikes** | High | Medium | Per-run token budget + circuit breaker + cost summary in runs |
| **Adapter rot** (format changes) | Medium | Medium | Contract tests with public samples + version pinning in `adapter_meta` |
| **Checkpoint pile-up** | Medium | Low | Size-capped cache + `cache gc` command (LRU/age) |
| **Multi-tenant data leaks** | Low | Critical | `tenant_id` in IR + namespaced UUIDs + isolation tests |

---

## Success Metrics (Tightened)

### Safety
- [ ] **0% LLM calls without PrivacyPass** (enforced via `@require_privacy_pass`)
- [ ] **0% privacy gate bypasses** (capability token required)
- [ ] **100% adapter outputs validated** against IR v1 schema

### Determinism
- [ ] **Re-ingest → identical UUIDs** (hash match on 1000 rows)
- [ ] **Stable fingerprints** (same input → same fingerprint)

### Performance
- [ ] **Vectorized UDFs ≥10× speedup** (benchmarked)
- [ ] **<2s checkpoint decision** per stage

### Observability
- [ ] **100% runs have trace + runs row**
- [ ] **Mean-time-to-explain < 5 min** using `egregora runs tail`
- [ ] **Error budget: ≤1% degraded runs** (skipped enrichment)

### Developer Experience
- [ ] **<5 min to add new adapter** (cookiecutter template)
- [ ] **Golden-path tutorial < 5 min** (WhatsApp → site)
- [ ] **Clear error messages** (no raw stack traces)

---

## Living ADRs (Updated)

**ADR-001: Sources → Adapters → IR v1**
- Decision: Strict IR v1 schema contract + content-addressed checkpoints
- Additions: `tenant_id` required, `adapter_meta()` for plugins
- Status: Approved (Week 1)

**ADR-002: Privacy as Capability Token**
- Decision: PrivacyPass capability (not global flag) + namespaced UUID5
- Re-id escrow: Optional, tenant opt-in only
- Status: Approved (Week 2)

**ADR-003: Ibis-First + SQL Escape Hatch**
- Decision: Ban pandas except `compat/`, allow `@stage_view(sql=...)` for perf
- Rationale: Type safety + DuckDB integration + performance headroom
- Status: Approved (Week 3)

**ADR-004: Agents as Orchestrators + Deps Injection**
- Decision: Agents call pure tools, deps bag handles I/O + secrets
- Audit envelope: Every tool call carries `{run_id, model_id, prompt_hash, input_sha, output_sha}`
- Status: Approved (Week 5)

**ADR-005: Unified CLI + Runs Tracking**
- Decision: Stage-based subcommands + `runs`/`doctor`/`cache` commands
- All stages write to `runs` table
- Status: Approved (Week 11)

---

## Doctor Command (Diagnostic)

```bash
egregora doctor
```

**Checks**:
- [ ] Environment variables (`GOOGLE_API_KEY`, etc.)
- [ ] DuckDB version + VSS extension
- [ ] File permissions (`.egregora/` writable)
- [ ] Adapters discovered (count + versions)
- [ ] IR v1 schema lockfile present
- [ ] Git repo (for code_ref tracking)

**Output**:
```
✓ Environment: GOOGLE_API_KEY set
✓ DuckDB: 0.10.0 + VSS extension loaded
✓ Permissions: .egregora/ writable
✓ Adapters: 2 discovered (whatsapp v1.0.0, slack v0.1.0)
✓ IR Schema: v1 lockfile matches codebase
✓ Git: Repo detected (commit: a1b2c3d)

Next steps:
  1. Run: egregora ingest whatsapp-export.zip
  2. View: egregora runs tail
  3. Docs: https://docs.egregora.dev/quickstart
```

---

## Documentation Architecture

**`docs/architecture/`**:
- `ir-v1-spec.md` - Canonical IR v1 specification
- `privacy-flow.md` - Privacy gate + capability token
- `adapter-guide.md` - How to write adapters (with cookiecutter)
- `stages.md` - Pipeline stages reference
- `slos.md` - Service-level objectives (error budget, latency)

**Golden Path Tutorial**:
- Location: `docs/quickstart.md`
- Goal: WhatsApp ZIP → generated site in <5 minutes
- Includes: Sample ZIP, expected output, common errors

---

**Last Updated**: 2025-01-08
**Next Review**: End of Week 2 (after foundation + IR v1 lockfile)
**Status**: Ready for Week 1 execution 🚀
