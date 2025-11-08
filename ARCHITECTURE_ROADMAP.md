# Egregora: Architecture Roadmap & North-Star Vision

**Date**: 2025-01-08
**Status**: Active Development Plan
**Timeline**: 90 days (12 weeks)
**Philosophy**: Modular, testable, pluggable platform

---

## North-Star Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    EGREGORA PLATFORM LAYERS                       │
└──────────────────────────────────────────────────────────────────┘

1. SOURCES → ADAPTERS → IR
   ┌─────────┐      ┌─────────┐      ┌─────────┐
   │WhatsApp │──────│ Adapter │──────│   IR    │
   │  Slack  │      │Registry │      │ Schema  │
   │ Discord │      └─────────┘      └─────────┘
   └─────────┘            ↓                ↓
                   Schema Contract   Validation

2. PRIVACY BOUNDARY (before LLM)
   ┌─────────────────────────────────────┐
   │      PRIVACY GATE (mandatory)        │
   │  UUID5 pseudonymization + PII check  │
   │  ← Must run before ANY LLM call →    │
   └─────────────────────────────────────┘

3. PROCESSING PIPELINE (IR → chunks → enrich → index)
   ┌──────┐  ┌──────┐  ┌────────┐  ┌─────┐
   │Chunk │→ │Enrich│→ │Embed   │→ │Index│
   └──────┘  └──────┘  └────────┘  └─────┘
      ↓          ↓          ↓          ↓
   Checkpoint Checkpoint Checkpoint Checkpoint

4. AGENTS (orchestrators, not workers)
   ┌────────┐  ┌────────┐
   │ Editor │  │Ranking │
   │ Agent  │  │ Agent  │
   └────────┘  └────────┘
       ↓           ↓
   Pure Tools   Scoring Service

5. RENDERERS (terminal consumers)
   ┌────────┐  ┌──────┐
   │ MkDocs │  │ Hugo │
   └────────┘  └──────┘
       ↓           ↓
   Read-only Materialized Views
```

---

## Quick Wins (Do Immediately) ⚡

### QW-1: Fail Build on Pandas Import (5 min)
**Status**: [ ] Not Started

```bash
# Already have the check - turn it on in CI
# Update .github/workflows/ci.yml or pre-commit config
uv run python tests/linting/test_no_pandas_escape.py
```

**Success**: CI fails if `pd.` appears outside TYPE_CHECKING/compat/testing

---

### QW-2: Slack Adapter Fail-Fast (10 min)
**Status**: [ ] Not Started

**File**: `src/egregora/ingestion/slack_input.py`

```python
def parse_source(self, input_path: Path) -> ibis.Table:
    """Parse Slack export to IR table."""
    # Current: Returns empty table silently
    # New: Raise NotImplementedError if data exists

    if input_path.exists() and self._has_data(input_path):
        raise NotImplementedError(
            "Slack adapter is a stub. Implement parsing logic "
            "or use WhatsApp adapter for now."
        )
    return self._empty_table()
```

**Success**: No silent empty results in CI/production

---

### QW-3: Privacy Gate Decorator (30 min)
**Status**: [ ] Not Started

**File**: `src/egregora/privacy/gate.py` (new)

```python
from functools import wraps

_privacy_gate_run = False

def require_privacy_gate(func):
    """Decorator: Fail if privacy gate didn't run before LLM calls."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _privacy_gate_run:
            raise RuntimeError(
                f"{func.__name__} requires privacy gate. "
                "Call PrivacyGate.run(table) first."
            )
        return func(*args, **kwargs)
    return wrapper

class PrivacyGate:
    @staticmethod
    def run(table: ibis.Table) -> ibis.Table:
        """Anonymize + PII check. Sets global flag."""
        global _privacy_gate_run
        # Existing logic: anonymize_author, detect_pii
        result = anonymize_table(table)
        _privacy_gate_run = True
        return result
```

**Usage**:
```python
@require_privacy_gate
def enrich_media(table: ibis.Table) -> ibis.Table:
    """Enriches media - requires privacy gate."""
    # LLM calls here are safe
```

**Success**: Runtime error if LLM stage skips privacy

---

## Priority A: Platform Seams & Plugins (Weeks 1-2)

### A.1: Adapter Plugin System (2 days)
**Status**: [ ] Not Started

**Goal**: Allow third-party adapters via entry points

**Implementation**:

1. **Define protocol** (`src/egregora/adapters/base.py`):
```python
from typing import Protocol
import ibis

class SourceAdapter(Protocol):
    """Adapter contract for all sources."""

    def parse_source(self, input_path: Path) -> ibis.Table:
        """Parse source to IR table."""
        ...

    def validate_output(self, table: ibis.Table) -> bool:
        """Validate IR schema contract."""
        ...
```

2. **Plugin loader** (`src/egregora/adapters/registry.py`):
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
            adapter_cls = ep.load()
            self._adapters[ep.name] = adapter_cls()
```

3. **Schema validation** (`src/egregora/database/validation.py`):
```python
def validate_ir_schema(table: ibis.Table) -> None:
    """Assert table matches CONVERSATION_SCHEMA."""
    expected = set(CONVERSATION_SCHEMA.keys())
    actual = set(table.schema().names)

    if expected != actual:
        raise SchemaError(
            f"IR schema mismatch. Expected: {expected}, Got: {actual}"
        )
```

**Files**:
- `src/egregora/adapters/base.py` (new)
- `src/egregora/adapters/registry.py` (update)
- `src/egregora/database/validation.py` (new)

**Tests**:
- `tests/unit/test_adapter_registry.py` (plugin discovery)
- `tests/unit/test_ir_schema_validation.py` (schema contract)

**Success**:
- [ ] Third-party adapter loads via entry point
- [ ] Schema validation catches mismatches
- [ ] Example plugin in docs

---

### A.2: Strict IR Schema Contract (1 day)
**Status**: [ ] Not Started

**Goal**: Compile-time + runtime validation

**Implementation**:

```python
# src/egregora/database/schema.py
from pydantic import BaseModel, Field

class ConversationRow(BaseModel):
    """Runtime validator for IR rows."""
    timestamp: datetime
    author: str
    message: str
    original_line: str
    tagged_line: str | None = None
    message_id: str

    class Config:
        frozen = True

# At adapter boundary
def adapter_output_validator(table: ibis.Table) -> ibis.Table:
    """Validate adapter output before pipeline."""
    validate_ir_schema(table)  # Compile-time (Ibis schema)

    # Runtime sample validation (Pydantic)
    sample = table.limit(100).execute()
    for row in sample.itertuples():
        ConversationRow(**row._asdict())

    return table
```

**Tests**:
- `tests/unit/test_schema_contract.py`

**Success**:
- [ ] Invalid schema rejected at adapter boundary
- [ ] Clear error messages for violations

---

## Priority B: Privacy as a Gate (Weeks 2-3)

### B.1: Mandatory Privacy Pass (2 days)
**Status**: [ ] Not Started

**Goal**: Privacy gate runs before ANY LLM call

**Implementation**:

1. **Privacy gate stage** (`src/egregora/privacy/gate.py`):
```python
class PrivacyGate:
    """Mandatory privacy boundary before LLM processing."""

    @staticmethod
    def run(table: ibis.Table, config: PrivacyConfig) -> ibis.Table:
        """Anonymize authors + detect PII + apply filters."""
        logger.info("🔒 Privacy gate: Starting")

        # 1. Anonymize authors (UUID5)
        table = anonymize_authors(table)

        # 2. Detect & flag PII
        table = detect_pii(table, config.pii_patterns)

        # 3. Apply media allow/deny lists
        table = filter_media(table, config.media_allowlist)

        # 4. Set global flag
        global _privacy_gate_run
        _privacy_gate_run = True

        logger.info("✓ Privacy gate: Complete")
        return table
```

2. **Decorator for LLM stages** (see QW-3 above)

3. **Pipeline enforcement** (`src/egregora/pipeline/runner.py`):
```python
def run_pipeline(source_path: Path, config: Config):
    """Run full pipeline with privacy gate enforcement."""

    # 1. Parse source
    table = adapter.parse_source(source_path)

    # 2. PRIVACY GATE (mandatory)
    table = PrivacyGate.run(table, config.privacy)

    # 3. Processing (LLM-safe)
    table = enrich_media(table)  # Decorated with @require_privacy_gate
    table = embed_chunks(table)

    # ...
```

**Tests**:
- `tests/unit/test_privacy_gate.py` (gate logic)
- `tests/integration/test_privacy_enforcement.py` (decorator)

**Success**:
- [ ] Pipeline fails if privacy gate skipped
- [ ] All LLM stages decorated with `@require_privacy_gate`
- [ ] Property test: no real names survive gate

---

### B.2: Privacy Config Extension (1 day)
**Status**: [ ] Not Started

**Goal**: Media allow/deny lists

**Implementation**:

```python
# src/egregora/config/schema.py
@dataclass(frozen=True)
class PrivacyConfig:
    """Privacy gate configuration."""
    anonymize_authors: bool = True
    pii_patterns: list[str] = field(default_factory=list)
    media_allowlist: list[str] | None = None  # URL patterns
    media_denylist: list[str] | None = None
```

**Tests**:
- `tests/unit/test_privacy_config.py`

**Success**:
- [ ] Media filtered by URL patterns
- [ ] Config validates at load time

---

## Priority C: Data Layer Discipline (Weeks 3-4)

### C.1: Centralize DuckDB Access (2 days)
**Status**: [ ] Not Started

**Goal**: One storage abstraction for all stages

**Implementation**:

```python
# src/egregora/database/connection.py
class StorageManager:
    """Centralized DuckDB connection + Ibis helpers."""

    def __init__(self, db_path: Path | None = None):
        self.conn = duckdb.connect(str(db_path) if db_path else ":memory:")
        self.ibis_conn = ibis.duckdb.connect(self.conn)

    def read_table(self, name: str) -> ibis.Table:
        """Read table as Ibis view."""
        return self.ibis_conn.table(name)

    def write_table(self, table: ibis.Table, name: str, mode: str = "replace"):
        """Write Ibis table to DuckDB."""
        table.to_parquet(f"{name}.parquet")
        self.conn.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM '{name}.parquet'")

    def execute_query(self, expr: ibis.Expr) -> ibis.Table:
        """Execute Ibis expression."""
        return expr.execute()

# Pipeline stages receive StorageManager
def enrich_stage(storage: StorageManager, config: Config):
    """Enrichment stage using centralized storage."""
    table = storage.read_table("conversations")
    enriched = enrich_media(table, config)
    storage.write_table(enriched, "conversations_enriched")
```

**Tests**:
- `tests/unit/test_storage_manager.py`

**Success**:
- [ ] All stages use `StorageManager`
- [ ] No raw SQL in pipeline code

---

### C.2: Sanctioned Pandas Escape Hatch (1 day)
**Status**: [ ] Not Started

**Goal**: One official module for pandas conversions

**Implementation**:

```python
# src/egregora/compat/pandas_bridge.py
"""Sanctioned escape hatch for Ibis → pandas conversions.

WARNING: This is the ONLY module allowed to import pandas.
All other modules must use Ibis tables.
"""

import pandas as pd
import ibis

def to_pandas(table: ibis.Table) -> pd.DataFrame:
    """Convert Ibis table to pandas (use sparingly)."""
    logger.warning("Converting Ibis → pandas (escape hatch)")
    return table.execute()

def from_pandas(df: pd.DataFrame) -> ibis.Table:
    """Convert pandas to Ibis table."""
    logger.warning("Converting pandas → Ibis (escape hatch)")
    return ibis.memtable(df)
```

**Pre-commit**:
```python
# tests/linting/test_no_pandas_escape.py
ALLOWED_PANDAS = [
    "egregora/compat/pandas_bridge.py",
    "TYPE_CHECKING",
    "tests/",
]
```

**Success**:
- [ ] CI fails on pandas imports outside `compat/`
- [ ] Clear error message points to bridge module

---

## Priority D: Idempotency & Checkpoints (Weeks 4-5)

### D.1: Standard Checkpoint Trait (3 days)
**Status**: [ ] Not Started

**Goal**: Formalize checkpoint pattern across all stages

**Implementation**:

```python
# src/egregora/pipeline/stage.py
from abc import ABC, abstractmethod
import hashlib

class Stage(ABC):
    """Base class for pipeline stages with checkpointing."""

    @abstractmethod
    def run(self, table: ibis.Table, config: Config) -> ibis.Table:
        """Execute stage logic."""
        ...

    def fingerprint(self, table: ibis.Table, config: Config) -> str:
        """Generate stable fingerprint for input."""
        row_count = table.count().execute()
        config_hash = hashlib.sha256(str(config).encode()).hexdigest()
        return f"{self.__class__.__name__}_{row_count}_{config_hash[:8]}"

    def is_complete(self, output_path: Path) -> bool:
        """Check if stage already completed."""
        marker = output_path / f".{self.__class__.__name__}.complete"
        return marker.exists()

    def mark_complete(self, output_path: Path, fingerprint: str):
        """Mark stage complete with fingerprint."""
        marker = output_path / f".{self.__class__.__name__}.complete"
        marker.write_text(fingerprint)

# Example usage
class EnrichmentStage(Stage):
    def run(self, table: ibis.Table, config: Config) -> ibis.Table:
        fp = self.fingerprint(table, config)

        if self.is_complete(config.output_dir):
            logger.info(f"✓ Enrichment already complete (fp={fp})")
            return load_from_checkpoint(config.output_dir)

        # Do work
        enriched = enrich_media(table, config)

        # Save checkpoint
        save_checkpoint(enriched, config.output_dir)
        self.mark_complete(config.output_dir, fp)

        return enriched
```

**Tests**:
- `tests/unit/test_stage_checkpoints.py`

**Success**:
- [ ] All stages inherit from `Stage`
- [ ] Fingerprints are stable across runs
- [ ] Resuming skips completed stages

---

## Priority E: Agent Boundary Hygiene (Weeks 5-6)

### E.1: Editor Agent Refactor (2 days)
**Status**: [ ] Not Started

**Goal**: Editor orchestrates, doesn't do file I/O

**Current Issues**:
- Editor agent reads/writes files directly
- Tool calls mix orchestration with side effects

**Solution**:

```python
# src/egregora/agents/editor/tools.py
from egregora.agents.editor.deps import EditorDeps

def query_rag(query: str, deps: EditorDeps) -> str:
    """Query RAG store (pure function)."""
    return deps.rag_store.search(query, k=5)

def edit_post_content(post_id: str, edits: dict, deps: EditorDeps) -> dict:
    """Apply edits to post (side-effect via deps)."""
    post = deps.post_store.load(post_id)
    updated = apply_edits(post, edits)  # Pure function
    deps.post_store.save(post_id, updated)  # Dep handles I/O
    return {"status": "updated", "post_id": post_id}

def generate_banner(prompt: str, deps: EditorDeps) -> str:
    """Generate banner image (side-effect via deps)."""
    return deps.banner_service.generate(prompt)
```

**Tests**:
- `tests/agents/test_editor_tools.py` (mock deps)

**Success**:
- [ ] All file I/O via `EditorDeps`
- [ ] Tools are testable with mocks
- [ ] No direct Path operations in tools

---

### E.2: Ranking Agent Audit Metadata (1 day)
**Status**: [ ] Not Started

**Goal**: Track model/prompt used for each comparison

**Implementation**:

```python
# src/egregora/agents/ranking/store.py
@dataclass(frozen=True)
class RankingComparison:
    """Audit record for pairwise comparison."""
    comparison_id: str
    post_a_id: str
    post_b_id: str
    winner_id: str
    profile_id: str  # NEW: Who ranked
    model_id: str    # NEW: Which model
    prompt_hash: str # NEW: Prompt version
    timestamp: datetime
```

**Tests**:
- `tests/agents/test_ranking_audit.py`

**Success**:
- [ ] All comparisons tracked with metadata
- [ ] Can filter rankings by model/profile

---

## Priority F: Observability & Ops (Weeks 6-7)

### F.1: Structured Logging (2 days)
**Status**: [ ] Not Started

**Goal**: Standardize log fields across stages

**Implementation**:

```python
# src/egregora/utils/logging.py
import structlog

def configure_logging(config: Config):
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )

# Usage in stages
logger = structlog.get_logger()

logger.info(
    "stage_complete",
    stage="enrichment",
    source="whatsapp",
    rows_in=1000,
    rows_out=950,
    duration_sec=45.2,
    llm_calls=50,
    tokens_used=12500,
)
```

**Metrics to track**:
- Rows in/out per stage
- LLM calls per stage
- Tokens used
- Duration per stage
- Tool calls per agent

**Success**:
- [ ] All stages emit structured logs
- [ ] Logs are JSON (parseable)
- [ ] Can aggregate metrics from logs

---

### F.2: Dry-Run Mode (1 day)
**Status**: [ ] Not Started

**Goal**: Preview stage output without execution

**Implementation**:

```python
# src/egregora/pipeline/stage.py
class Stage(ABC):
    def dry_run(self, table: ibis.Table, config: Config) -> dict:
        """Preview stage without executing."""
        return {
            "stage": self.__class__.__name__,
            "input_rows": table.count().execute(),
            "estimated_output_rows": self._estimate_output(table),
            "sample_input": table.limit(5).execute().to_dict(),
            "will_checkpoint": not self.is_complete(config.output_dir),
        }
```

**CLI**:
```bash
egregora pipeline run --dry-run whatsapp.zip
# Output: Stage summary table with estimates
```

**Success**:
- [ ] All stages support `--dry-run`
- [ ] Dry-run shows sample rows + estimates

---

## Priority G: Reliability & Performance (Weeks 7-8)

### G.1: LLM Backpressure & Circuit Breaker (3 days)
**Status**: [ ] Not Started

**Goal**: Graceful degradation on LLM failures

**Implementation**:

```python
# src/egregora/utils/circuit_breaker.py
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"    # Normal operation
    OPEN = "open"        # Failing, skip calls
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """Circuit breaker for LLM calls."""

    def __init__(self, failure_threshold: int = 5, timeout: timedelta = timedelta(minutes=5)):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker."""
        if self.state == CircuitState.OPEN:
            if datetime.now() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                logger.warning("Circuit breaker OPEN, skipping LLM call")
                return None  # Degrade gracefully

        try:
            result = func(*args, **kwargs)
            self.failure_count = 0
            self.state = CircuitState.CLOSED
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker OPEN after {self.failure_count} failures")

            raise

# Token bucket for rate limiting
class TokenBucket:
    """Rate limiter for LLM API calls."""

    def __init__(self, capacity: int = 60, refill_rate: int = 1):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = datetime.now()

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens."""
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on time elapsed."""
        now = datetime.now()
        elapsed = (now - self.last_refill).total_seconds()
        new_tokens = int(elapsed * self.refill_rate)

        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
```

**Usage**:
```python
# src/egregora/enrichment/core.py
breaker = CircuitBreaker(failure_threshold=5)
bucket = TokenBucket(capacity=60, refill_rate=1)

def enrich_media_safe(table: ibis.Table) -> ibis.Table:
    """Enrich with circuit breaker + rate limiting."""

    def enrich_row(row):
        if not bucket.acquire():
            logger.warning("Rate limit exceeded, skipping enrichment")
            return row  # Return original

        return breaker.call(enrich_single_row, row)

    return table.mutate(enriched=enrich_row)
```

**Tests**:
- `tests/unit/test_circuit_breaker.py`
- `tests/unit/test_token_bucket.py`

**Success**:
- [ ] LLM failures don't crash pipeline
- [ ] Rate limiting prevents quota exhaustion
- [ ] Graceful degradation (skip enrichment)

---

### G.2: Vectorized UDFs (2 days)
**Status**: [ ] Not Started

**Goal**: Reduce Python overhead in common operations

**Current**:
```python
# Slow: Row-by-row Python UDF
def media_to_markdown(url: str) -> str:
    return f"![media]({url})"

table = table.mutate(markdown=media_to_markdown(table.url))
```

**Optimized**:
```python
# Fast: Vectorized Ibis expression
table = table.mutate(
    markdown=ibis.literal("![media](") + table.url + ibis.literal(")")
)
```

**Targets**:
- Media URL → markdown conversion
- UUID generation (use DuckDB's uuid() function)
- Simple string transforms

**Tests**:
- `tests/unit/test_vectorized_udfs.py` (correctness)
- `tests/performance/test_udf_benchmarks.py` (speed)

**Success**:
- [ ] 10x speedup on common UDFs
- [ ] Benchmark suite tracks regression

---

## Priority H: Security & Secrets (Week 8)

### H.1: Secrets Provider Abstraction (1 day)
**Status**: [ ] Not Started

**Goal**: Centralized secret management

**Implementation**:

```python
# src/egregora/config/secrets.py
from abc import ABC, abstractmethod

class SecretsProvider(ABC):
    """Abstract secrets provider."""

    @abstractmethod
    def get_secret(self, key: str) -> str | None:
        """Retrieve secret by key."""
        ...

class EnvSecretsProvider(SecretsProvider):
    """Read secrets from environment variables."""

    def get_secret(self, key: str) -> str | None:
        return os.getenv(key)

class FileSecretsProvider(SecretsProvider):
    """Read secrets from file (e.g., .env)."""

    def __init__(self, secrets_file: Path):
        self.secrets = self._load_secrets(secrets_file)

    def get_secret(self, key: str) -> str | None:
        return self.secrets.get(key)

# Dependency injection
class AgentDeps:
    def __init__(self, secrets: SecretsProvider):
        self.secrets = secrets
        self.api_key = secrets.get_secret("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in secrets")
```

**Tests**:
- `tests/unit/test_secrets_provider.py`

**Success**:
- [ ] All agents use `SecretsProvider`
- [ ] Fail-fast on missing secrets
- [ ] Clear error messages

---

## Priority I: Testing Strategy (Weeks 9-10)

### I.1: Golden IR Fixtures per Adapter (2 days)
**Status**: [ ] Not Started

**Goal**: Snapshot tests for adapter outputs

**Implementation**:

```bash
# Directory structure
tests/fixtures/adapters/
├── whatsapp/
│   ├── input/
│   │   └── chat.zip
│   └── golden/
│       └── ir_output.parquet
└── slack/
    ├── input/
    │   └── export.json
    └── golden/
        └── ir_output.parquet
```

**Test**:
```python
# tests/adapters/test_whatsapp_adapter_golden.py
def test_whatsapp_adapter_output(snapshot):
    """Test WhatsApp adapter against golden fixture."""
    adapter = WhatsAppAdapter()

    input_path = FIXTURES / "adapters/whatsapp/input/chat.zip"
    golden_path = FIXTURES / "adapters/whatsapp/golden/ir_output.parquet"

    # Parse source
    result = adapter.parse_source(input_path)

    # Load golden
    golden = ibis.read_parquet(golden_path)

    # Assert schema match
    assert result.schema() == golden.schema()

    # Assert content match (first 100 rows)
    assert result.limit(100).execute().equals(
        golden.limit(100).execute()
    )
```

**Success**:
- [ ] Golden fixtures for WhatsApp + Slack
- [ ] CI fails on schema/content drift
- [ ] Easy to regenerate goldens

---

### I.2: Property Tests for Privacy (1 day)
**Status**: [ ] Not Started

**Goal**: Verify privacy invariants

**Implementation**:

```python
# tests/unit/test_privacy_properties.py
from hypothesis import given, strategies as st

@given(st.text(min_size=1))
def test_anonymization_is_deterministic(name: str):
    """Same name always produces same UUID."""
    uuid1 = anonymize_author(name)
    uuid2 = anonymize_author(name)
    assert uuid1 == uuid2

@given(st.text(min_size=1))
def test_no_real_names_survive_gate(name: str):
    """Real names never appear after privacy gate."""
    table = ibis.memtable([{"author": name, "message": f"Hi from {name}"}])

    result = PrivacyGate.run(table, PrivacyConfig())

    # Assert name doesn't appear anywhere
    text = result.execute().to_string()
    assert name not in text

def test_uuid5_stability():
    """UUID5 generation is stable across runs."""
    # Same input always produces same UUID
    uuid1 = uuid5(NAMESPACE_DNS, "John Doe")
    uuid2 = uuid5(NAMESPACE_DNS, "John Doe")
    assert str(uuid1) == str(uuid2)
```

**Success**:
- [ ] Privacy invariants tested with property tests
- [ ] 1000+ random inputs verified

---

### I.3: Agent Contract Tests (1 day)
**Status**: [ ] Not Started

**Goal**: Verify agent behavior with fake models

**Implementation**:

```python
# tests/agents/test_editor_contract.py
def test_editor_tool_sequencing():
    """Editor calls tools in expected order."""
    fake_model = FakeModel(responses=[
        "query_rag: Search for post context",
        "edit_post_content: Update title",
        "generate_banner: Create banner",
    ])

    agent = create_editor_agent(model=fake_model)
    result = agent.run("Edit post 123")

    # Assert tool call sequence
    assert result.tool_calls == [
        "query_rag",
        "edit_post_content",
        "generate_banner",
    ]

def test_ranking_agent_persists_results():
    """Ranking agent saves comparisons to store."""
    fake_model = FakeModel(winner="post_a")
    store = InMemoryRankingStore()

    agent = create_ranking_agent(model=fake_model, store=store)
    agent.compare("post_a", "post_b")

    # Assert comparison persisted
    comparisons = store.get_comparisons()
    assert len(comparisons) == 1
    assert comparisons[0].winner_id == "post_a"
```

**Success**:
- [ ] All agents tested with fake models
- [ ] Tool sequencing verified
- [ ] Persistence verified

---

## Priority J: CLI & DX (Weeks 10-11)

### J.1: Unified CLI with Subcommands (3 days)
**Status**: [ ] Not Started

**Goal**: Single `egregora` CLI with stage subcommands

**Current**:
```bash
egregora process whatsapp.zip  # Runs full pipeline
egregora edit post.md
egregora rank --site-dir .
```

**Proposed**:
```bash
egregora ingest whatsapp.zip --output ir.parquet
egregora privacy ir.parquet --output safe.parquet
egregora pipeline run safe.parquet --output processed/
egregora rag index processed/ --output rag.duckdb
egregora rank compare --site-dir . --comparisons 50
egregora render mkdocs --input processed/ --output site/
```

**Implementation**:

```python
# src/egregora/cli/__init__.py
import typer

app = typer.Typer(help="Egregora: WhatsApp → Blog Pipeline")

# Subcommand groups
app.add_typer(ingest_app, name="ingest")
app.add_typer(privacy_app, name="privacy")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(rag_app, name="rag")
app.add_typer(rank_app, name="rank")
app.add_typer(render_app, name="render")

# Legacy compatibility
app.command("process")(process_legacy)  # Calls all stages
```

**Each subcommand prints stage summary**:
```
┌─────────────────────────────────────────────────────────┐
│ STAGE: Privacy Gate                                     │
├─────────────────────────────────────────────────────────┤
│ Input:    1,234 rows                                    │
│ Output:   1,234 rows (0 filtered)                       │
│ Authors:  45 → 45 UUIDs                                 │
│ PII:      3 phone numbers detected                      │
│ Duration: 2.3s                                          │
└─────────────────────────────────────────────────────────┘
```

**Tests**:
- `tests/cli/test_subcommands.py`

**Success**:
- [ ] All stages accessible via CLI
- [ ] Consistent output format
- [ ] Legacy `process` still works

---

## 90-Day Roadmap Summary

### Weeks 1-2: Foundation
- [ ] Adapter plugin system (A.1)
- [ ] Strict IR schema contract (A.2)
- [ ] Quick wins (QW-1, QW-2, QW-3)

### Weeks 3-4: Privacy & Data
- [ ] Mandatory privacy pass (B.1)
- [ ] Privacy config extension (B.2)
- [ ] Centralize DuckDB access (C.1)
- [ ] Pandas escape hatch (C.2)

### Weeks 5-6: Stages & Agents
- [ ] Standard checkpoint trait (D.1)
- [ ] Editor agent refactor (E.1)
- [ ] Ranking audit metadata (E.2)

### Weeks 7-8: Observability & Reliability
- [ ] Structured logging (F.1)
- [ ] Dry-run mode (F.2)
- [ ] Circuit breaker + backpressure (G.1)
- [ ] Vectorized UDFs (G.2)
- [ ] Secrets provider (H.1)

### Weeks 9-10: Testing
- [ ] Golden IR fixtures (I.1)
- [ ] Property tests for privacy (I.2)
- [ ] Agent contract tests (I.3)

### Weeks 11-12: DX & Finalization
- [ ] Unified CLI (J.1)
- [ ] Pre-commit enforcement (J.2)
- [ ] Architecture docs (J.3)
- [ ] Performance benchmarks

---

## Success Metrics

**Code Quality**:
- [ ] Zero pandas imports outside `compat/`
- [ ] All adapters pass schema validation
- [ ] Privacy gate never bypassed

**Performance**:
- [ ] 10x speedup on vectorized UDFs
- [ ] <2s per stage checkpoint decision
- [ ] Circuit breaker prevents quota exhaustion

**Testing**:
- [ ] 95%+ test coverage
- [ ] Property tests for all privacy logic
- [ ] Golden fixtures for all adapters

**Developer Experience**:
- [ ] <5 min to add new adapter
- [ ] Clear error messages (no stack traces)
- [ ] Single CLI command per stage

---

## Living ADRs (Architecture Decision Records)

**ADR-001: Sources → Adapters → IR**
- Decision: Strict IR schema contract at adapter boundary
- Rationale: Enables plugin system, validates third-party adapters
- Status: Approved (Week 1)

**ADR-002: Privacy as a Hard Gate**
- Decision: Mandatory privacy gate before LLM processing
- Rationale: Fail-safe architecture, no PII leaks possible
- Status: Approved (Week 2)

**ADR-003: Ibis-First Data Layer**
- Decision: Ban pandas except in `compat/` module
- Rationale: Type safety, performance, DuckDB integration
- Status: Approved (Week 3)

**ADR-004: Agents as Orchestrators**
- Decision: Agents call pure tools, deps handle side effects
- Rationale: Testability, separation of concerns
- Status: Approved (Week 5)

**ADR-005: Unified CLI**
- Decision: Stage-based subcommands with consistent output
- Rationale: Composability, observability, debugging
- Status: Approved (Week 11)

---

## Open Questions

1. **Slack adapter**: Full implementation in Weeks 3-4?
2. **Hugo renderer**: Alternative to MkDocs?
3. **Multi-tenant deployments**: Privacy implications?
4. **LLM backend abstraction**: Support Claude/OpenAI?
5. **Distributed processing**: DuckDB → Spark for large datasets?

---

**Last Updated**: 2025-01-08
**Next Review**: End of Week 2 (after foundation tasks)
**Status**: Ready for execution 🚀
