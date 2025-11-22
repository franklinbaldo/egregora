# CLAUDE.md

Developer guidance for Claude Code when working with this repository.

## Overview

**Egregora** is a privacy-first AI pipeline that extracts structured knowledge from unstructured communication (chats, legal feeds, archives). It synthesizes emergent intelligence from group conversations into coherent articles and documentation.

- **Repository:** https://github.com/franklinbaldo/egregora
- **Stack:** Python 3.12+ | uv | Ibis | DuckDB | Pydantic-AI | Google Gemini
- **Core Principle:** Privacy before intelligence (names → UUIDs before LLM)
- **Philosophy:** Alpha mindset—clean breaks over backward compatibility

## Quick Reference

```bash
# Setup
uv sync --all-extras
python dev_tools/setup_hooks.py  # MANDATORY before commits

# Test
uv run pytest tests/                    # All tests
uv run pytest tests/unit/               # Fast unit tests
uv run pytest --cov=egregora tests/     # With coverage

# Quality
uv run pre-commit run --all-files       # All checks (line length: 110)
uv run ruff check --fix src/            # Auto-fix linting issues

# Run
export GOOGLE_API_KEY="your-key"
uv run egregora write export.zip --output=./output
uv run egregora write export.zip --resume  # Incremental (opt-in)
uv run egregora init ./output --no-interactive  # For CI/CD

# Serve
cd output && uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

## Breaking Changes

### 2025-11-22 (PR #855)

**OutputAdapter.documents() → Iterator[Document]**
- **Before:** `def documents(self) -> list[Document]`
- **After:** `def documents(self) -> Iterator[Document]`
- **Migration:** Use `list(adapter.documents())` if you need random access
- **Rationale:** Memory efficiency for sites with 1000s of documents

**Statistics Page Auto-generation**
- Generates `posts/{date}-statistics.md` after pipeline runs
- Uses `daily_aggregates_view` (View Registry pattern)
- Non-critical path: errors don't block completion

**Interactive Init**
- `egregora init` now prompts for site name
- Auto-detects non-TTY (CI/CD) and disables prompts
- Use `--no-interactive` to explicitly disable

### 2025-11-17 (Infrastructure Simplification)

**~1,500 LOC removed:**
- Event-sourced `run_events` → simple `runs` table (INSERT + UPDATE pattern)
- IR schema: Python single source of truth (no SQL/JSON lockfiles)
- Validation: Manual `validate_ir_schema()` calls (decorator removed)
- Fingerprinting: Removed (file existence checks only)
- Checkpointing: Opt-in via `--resume` (default: full rebuild)

## Architecture

### Pipeline Stages

```
Ingestion → Privacy → Enrichment → Generation → Publication
  ↓           ↓           ↓            ↓            ↓
Parse ZIP   UUIDs      LLM ctx      Posts       MkDocs
```

**Critical Invariant:** Privacy stage runs BEFORE any LLM processing.

### Three-Layer Functional Architecture

```
Layer 3: orchestration/        # High-level workflows (write_pipeline.run)
Layer 2: transformations/      # Pure functional (Table → Table)
         input_adapters/       # Bring data IN
         output_adapters/      # Take data OUT
         database/            # Persistence, views, tracking
Layer 1: data_primitives/      # Foundation models (Document, etc.)
```

**Key Pattern:** No `PipelineStage` abstraction—all transforms are pure functions.

### Code Structure

```
src/egregora/
├── cli/                      # Typer commands
├── orchestration/            # Workflows (Layer 3)
│   └── write_pipeline.py    # Main pipeline coordination
├── transformations/          # Pure functional (Layer 2)
│   └── windowing.py         # Window creation, checkpointing
├── input_adapters/          # Layer 2
│   ├── whatsapp.py          # WhatsApp parser
│   ├── iperon_tjro.py       # Brazilian judicial API
│   └── self_reflection.py   # Re-ingest past posts
├── output_adapters/         # Layer 2
│   └── mkdocs/adapter.py    # MkDocs output
├── database/                # Layer 2
│   ├── ir_schema.py         # Schemas (IR_MESSAGE_SCHEMA, RUNS_TABLE_SCHEMA)
│   ├── duckdb_manager.py    # Connection management
│   ├── views.py             # View registry (daily_aggregates, etc.)
│   └── tracking.py          # Run tracking (INSERT+UPDATE)
├── data_primitives/         # Layer 1
│   ├── document.py          # Document, DocumentType
│   └── protocols.py         # OutputAdapter, InputAdapter
├── agents/                  # Pydantic-AI agents
│   ├── writer.py            # Post generation
│   ├── enricher.py          # URL/media enrichment
│   └── shared/rag/          # RAG implementation
├── privacy/                 # Anonymization
└── config/                  # Pydantic V2 settings
    └── settings.py          # EgregoraConfig
```

## Design Principles

✅ **Privacy-First:** Anonymize BEFORE LLM (critical invariant)
✅ **Ibis Everywhere:** DuckDB tables, pandas only at boundaries
✅ **Functional Transforms:** `Table → Table` (no classes)
✅ **Schemas as Contracts:** All stages preserve `IR_MESSAGE_SCHEMA`
✅ **Simple Default:** Full rebuild (--resume for incremental)
✅ **Alpha Mindset:** Clean breaks, no backward compatibility

## Naming Conventions

### Modules
- **Descriptive snake_case:** `file_system.py` not `filesystem.py`
- **Specific over generic:** `duckdb_manager.py` not `storage.py`

### Classes
- **Pydantic configs:** `*Settings` (e.g., `ModelSettings`, `RAGSettings`)
- **Runtime contexts:** `*Context` (e.g., `WriterAgentContext`)
- **Database managers:** `{Technology}{Purpose}` (e.g., `DuckDBStorageManager`)
- **Adapters:** `Input*` for IN, `Output*` for OUT (e.g., `WhatsAppAdapter`, `MkDocsAdapter`)

### Functions
- **Explicit verbs:** `get_adapter_metadata()` not `adapter_meta()`
- **Descriptive:** `embed_texts_in_batch()` not `embed_batch()`

### Variables
- **Source-agnostic:** `input_file` not `zip_file`
- **Explicit thresholds:** `min_similarity_threshold` not `min_similarity`

## Key Patterns

### View Registry

```python
from egregora.database.views import views, daily_aggregates_view

# Get view
stats = daily_aggregates_view(messages_table)

# Register custom view
@views.register("my_view")
def my_view_builder(table: Table) -> Table:
    return table.filter(...)
```

### DuckDB Storage Manager

```python
from egregora.database.duckdb_manager import DuckDBStorageManager

with DuckDBStorageManager() as storage:
    storage.write_table(table, "name", checkpoint=True)
    result = storage.execute_view("output", builder, "input")
```

### Schema Validation

```python
from egregora.database.validation import validate_ir_schema

def transform(data: Table) -> Table:
    validate_ir_schema(data)  # Manual validation
    result = data.filter(...)
    return result
```

### OutputAdapter Protocol

```python
def persist(self, document: Document) -> None:
    """Persist document (idempotent overwrites)."""

def documents(self) -> Iterator[Document]:
    """Lazy iteration for memory efficiency."""

def resolve_document_path(self, identifier: str) -> Path:
    """Resolve identifier to filesystem path."""
```

**Breaking change:** `serve()` deprecated → use `persist()`

### Run Tracking

```python
from egregora.database.tracking import record_run

# Pattern: INSERT + UPDATE
record_run(conn, run_id, "write", "running", started_at)
# ... do work ...
record_run(conn, run_id, "write", "completed", finished_at)
```

## Configuration

**File:** `.egregora/config.yml`

```yaml
models:
  writer: google-gla:gemini-flash-latest
  enricher: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001

rag:
  enabled: true
  top_k: 5
  mode: ann  # "ann" or "exact" (use "exact" in CI without VSS)

pipeline:
  step_size: 1
  step_unit: days  # "days", "hours", "messages"
```

**Custom prompts:** `.egregora/prompts/` (overrides `src/egregora/prompts/`)

## Testing

```bash
# Unit tests (fast, no API)
uv run pytest tests/unit/

# Integration (VCR cassettes)
uv run pytest tests/integration/  # First run needs GOOGLE_API_KEY

# E2E (full pipeline)
uv run pytest tests/e2e/

# VSS in CI (no extension)
uv run pytest --retrieval-mode=exact tests/
```

**VCR:** First run records to `tests/cassettes/`, subsequent runs replay.

## Development Workflow

### Before Starting

1. Install hooks: `python dev_tools/setup_hooks.py`
2. Read recent changes in this file
3. Check `docs/` for architecture details

### Making Changes

1. Identify layer (orchestration, transformations, data_primitives)
2. Preserve `IR_MESSAGE_SCHEMA` columns (add, never drop core)
3. Privacy MUST run before LLM
4. Write tests first
5. Keep simple (can LLM do it with better prompting?)

### Before Committing

```bash
uv run pre-commit run --all-files  # Mandatory
uv run pytest tests/unit/          # Fast sanity check
```

### Commit Messages

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** feat, fix, refactor, test, docs, chore

### Git Safety

- NEVER update git config
- NEVER force push to main/master
- NEVER skip hooks (--no-verify)
- ONLY commit when user explicitly asks
- Check authorship before amending

## Common Patterns

### Adding a New Source

1. Create `input_adapters/my_source.py`
2. Implement `InputAdapter` protocol
3. Register in `input_adapters/registry.py`
4. Add tests with VCR cassettes

### Adding a New Output Format

1. Create `output_adapters/my_format/adapter.py`
2. Implement `OutputAdapter` protocol
3. Add `persist()`, `documents()`, `resolve_document_path()`
4. Add tests

### Modifying Pipeline Stages

- All stages: `Table → Table`
- Validate with `validate_ir_schema()` when needed
- Add columns via `.mutate()`, never drop core
- Privacy MUST run before LLM

## Parallel Subagent Delegation

**When:** Repetitive tasks across 5+ independent files
**How:** Multiple `Task` tool calls in single message

```python
# Example: Fix BLE001 across 10 files → 5 parallel subagents
Task 1: Fix BLE001 in writer.py
Task 2: Fix BLE001 in cli.py
Task 3: Fix BLE001 in enricher.py + reader.py
```

**Prompt guidelines:**
1. Exact file paths + error codes
2. Clear rules (e.g., "NEVER use `except Exception:`")
3. Verification command
4. Disable git operations
5. Request summary

**Don't delegate:** Coordinated changes, interdependent files, exploratory work

## TENET-BREAK Philosophy

Intentional principle violations for pragmatic alpha development:

```python
# TENET-BREAK(scope)[@owner][P0|P1|P2][due:YYYY-MM-DD]:
# tenet=<code>; why=<constraint>; exit=<condition> (#issue)
```

**Tenets:** `no-compat`, `clean`, `no-defensive`, `propagate-errors`

## Privacy & Security

**Flow:** Parse → UUIDs (deterministic) → PII scan → LLM (anonymized only)

**In-chat commands:**
```
/egregora set alias "Casey"
/egregora opt-out
/egregora opt-in
```

## Debugging

```python
# Inspect Ibis tables
table.schema()
table.limit(5).execute()

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check VSS extension
conn.execute("SELECT * FROM duckdb_extensions() WHERE extension_name = 'vss'")
```

## Common Pitfalls

1. ❌ Never bypass privacy stage
2. ❌ Don't use pandas (use Ibis, convert only at boundaries)
3. ❌ Don't modify `IR_MESSAGE_SCHEMA` without migration plan
4. ✅ Commit VCR cassettes to repo
5. ✅ Use `--retrieval-mode=exact` in CI without VSS

## Post-Commit Reflection

After commits, reflect on:
- Technical decisions and rationale
- What worked/didn't work
- Error patterns
- Architecture insights

Ask permission to update CLAUDE.md with valuable insights.

## Resources

- **README.md:** User-facing docs, quick start
- **docs/:** Architecture, privacy, API reference
- **tests/fixtures/golden/:** Example outputs
- **SECURITY.md:** Security policy
