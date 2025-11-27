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
uv run egregora write export.zip --refresh=writer  # Invalidate writer cache
uv run egregora init ./output --no-interactive  # For CI/CD

# Serve
cd output && uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

## Breaking Changes

### 2025-11-27 (PR #981 - LanceDB RAG Backend)

**New RAG Backend with LanceDB**
- **Added:** New `egregora.rag` package with LanceDB-based vector storage
- **Architecture:** Clean protocol-based design with `RAGBackend` interface
- **API:** Simplified API compared to legacy `VectorStore`:
  ```python
  # New API (egregora.rag)
  from egregora.rag import index_documents, search, RAGQueryRequest
  from egregora.data_primitives import Document, DocumentType

  # Index documents
  doc = Document(content="# Post\n\nContent", type=DocumentType.POST)
  index_documents([doc])

  # Search
  request = RAGQueryRequest(text="search query", top_k=5)
  response = search(request)
  for hit in response.hits:
      print(f"{hit.score:.2f}: {hit.text[:50]}")
  ```
- **Configuration:** New settings in `.egregora/config.yml`:
  ```yaml
  paths:
    lancedb_dir: .egregora/lancedb  # LanceDB storage location

  rag:
    enabled: true
    top_k: 5
    min_similarity_threshold: 0.7
    indexable_types: ["POST"]  # Document types to index (configurable)
  ```
- **Dependencies:** Replaced `langchain-text-splitters` and `langchain-core` with `lancedb>=0.4.0`
- **Chunking:** Simple whitespace-based chunking (no LangChain dependency)
- **Status:** The legacy `VectorStore` in `egregora.agents.shared.rag` is now deprecated
- **Migration:** Legacy VectorStore will be removed in a future PR. New code should use `egregora.rag` package.
- **Security:** Fixed potential SQL injection in delete operations with proper string escaping
- **Flexibility:**
  - Indexable document types are now configurable via `rag.indexable_types` setting
  - Embedding function is dependency-injected for easier testing and alternative models

**Key Improvements Over Legacy RAG:**
1. **Cleaner Architecture:** Protocol-based design with `RAGBackend` interface
2. **Better Performance:** LanceDB provides faster vector search than DuckDB VSS
3. **Simpler API:** Direct document indexing without adapter coupling
4. **More Configurable:** Indexable types, storage paths, and search parameters are all configurable
5. **Better Error Handling:** More specific exception handling with clear error messages

**Breaking Changes (Fixed in Follow-up):**
- **Similarity Scores:** Now use cosine metric instead of L2 distance (default)
  - Previous implementation: Scores could be negative due to L2 distance
  - Current implementation: Scores in [-1, 1] range using `.metric("cosine")`
  - Impact: Scores will differ from earlier versions; re-index recommended
- **Filters API:** Changed from `dict[str, Any]` to `str`
  - Before: `filters={"category": "programming"}` (not actually supported)
  - After: `filters="category = 'programming'"` (SQL WHERE clause)
  - Rationale: Exposes LanceDB's native filtering without abstraction layer
  - Example:
    ```python
    # Search with SQL filtering
    request = RAGQueryRequest(
        text="search query",
        top_k=5,
        filters="metadata_json LIKE '%programming%'"  # SQL WHERE clause
    )
    response = search(request)
    ```
- **Backend Initialization:** Removed unused `top_k_default` parameter
  - Before: `LanceDBRAGBackend(..., top_k_default=5)`
  - After: `LanceDBRAGBackend(...)` (use `RAGQueryRequest.top_k` instead)
- **Query Limits:** Increased `top_k` maximum from 20 to 100
  - Allows more flexible retrieval for analytics and batch processing

### 2025-11-26 (PR #975 - Resumability & Fixes)

**MkDocs Plugin Rename**
- **Changed:** `mkdocs-blogging-plugin` renamed to `blog` in `mkdocs.yml` templates
- **Impact:** Custom `mkdocs.yml` files using the old plugin name will fail to build
- **Migration:** Update `plugins:` section in `mkdocs.yml`:
  ```yaml
  plugins:
    - blog  # was 'blogging'
  ```

### 2025-11-25 (PR #926 - RAG Indexing Optimization)

**VectorStore Facade Pattern**
- **Changed:** RAG operations centralized as VectorStore methods
- **Before:** Direct function calls: `index_documents_for_rag(output, rag_dir, storage, ...)`
- **After:** Method calls: `store.index_documents(output, embedding_model=...)`
- **New Methods:**
  - `VectorStore.index_documents(output_format, *, embedding_model)` - Index documents from adapter
  - `VectorStore.index_media(docs_dir, *, embedding_model)` - Index media enrichments
  - `VectorStore.query_media(query, ...)` - Search for relevant media
  - `VectorStore.query_similar_posts(table, ...)` - Find similar blog posts
  - `VectorStore.is_available()` - Check if RAG is available (static)
  - `VectorStore.embed_query(query_text, *, model)` - Embed query text (static)
- **Migration:**
  ```python
  # Before
  from egregora.agents.shared.rag import index_documents_for_rag, query_media
  indexed = index_documents_for_rag(output, rag_dir, storage, embedding_model=model)
  results = query_media(query, store, media_types=types, ...)

  # After
  from egregora.agents.shared.rag import VectorStore
  store = VectorStore(rag_dir / "chunks.parquet", storage=storage)
  indexed = store.index_documents(output, embedding_model=model)
  results = store.query_media(query, media_types=types, ...)
  ```

**Reduced RAG Export Surface**
- **Removed from `egregora.agents.shared.rag` exports:** All internal functions
- **Now exported:** Only `VectorStore` and `DatasetMetadata`
- **Rationale:** VectorStore is the single public API; internal functions are implementation details
- **Impact:** Code importing individual RAG functions will break
- **Migration:** Use VectorStore methods instead of direct function imports

**OutputSink Protocol Cleanup**
- **Removed:** `resolve_document_path()` from OutputSink protocol
- **Rationale:** Filesystem-specific method didn't belong in general output protocol
- **Impact:** Code relying on OutputSink having this method will break
- **Migration:** Check for method existence with `hasattr()` or use concrete adapter types

**Deterministic File Locations**
- **Changed:** RAG directory now uses settings instead of hardcoded paths
- **Before:** `site_root / ".egregora" / "rag"` hardcoded in multiple locations
- **After:** `config.paths.rag_dir` from settings (default: `.egregora/rag`)
- **Configuration:** Set `paths.rag_dir` in `.egregora/config.yml` to customize
- **Rationale:** All file locations should be configurable, not scattered throughout code

**Improved Exception Handling**
- **Changed:** `_index_new_documents` now catches specific exceptions
- **Before:** `except Exception: # noqa: BLE001`
- **After:** Catches `OSError`, `ValueError`, `PromptTooLargeError` explicitly
- **Impact:** Unexpected errors now propagate with full stack traces for debugging
- **Rationale:** Blanket exception catching hides bugs; be explicit about expected errors

### 2025-11-23 (Multi-PR Merge)

**Tiered Caching Architecture (PR #890)**
- **New Feature:** Three-tier cache system (L1: Enrichment, L2: RAG, L3: Writer)
- **CLI Addition:** `--refresh` flag to invalidate cache tiers
- **Cache Tiers:**
  - L1: Asset enrichment results (URLs, media)
  - L2: Vector search results with index metadata invalidation
  - L3: Writer output with semantic hashing (zero-cost re-runs)
- **Usage:** `egregora write export.zip --refresh=writer` or `--refresh=all`
- **Rationale:** Massive cost reduction for unchanged windows

**Writer Input Format: Markdown → XML (PR #889)**
- **Before:** Conversation passed as Markdown table
- **After:** Compact XML format via `_build_conversation_xml()`
- **Breaking:** Custom prompt templates must use `conversation_xml` (not `markdown_table`)
- **Template:** Uses `src/egregora/templates/conversation.xml.jinja`
- **Rationale:** ~40% token reduction, better structure preservation

**VSS Extension & Avatar Fallbacks (PR #893)**
- VSS extension now loaded explicitly before HNSW operations
- Fallback avatar generation using getavataaars.com (deterministic from UUID hash)
- Banner path conversion to web-friendly relative URLs
- Idempotent scaffold (detects existing mkdocs.yml)

**WhatsApp Parser Refactor (PR #894)**
- **Removed:** Hybrid DuckDB+Python `_parse_messages_duckdb()`
- **Added:** Pure Python `_parse_whatsapp_lines()` generator
- **Migration:** No API changes, internal refactor only
- **Rationale:** Eliminates serialization overhead, single-pass processing

**Privacy Validation Moved to Input Adapters (PR #892)**
- **Removed:** Mandatory `validate_text_privacy()` from `AnnotationStore.save_annotation()`
- **Rationale:** Allow public datasets (judicial records) with legitimate PII
- **Impact:** Privacy validation is now optional, use at input adapter level (e.g., WhatsApp)

**Circular Import Cleanup (PR #891)**
- **Removed:** Lazy `__getattr__` shim in `agents/__init__.py`
- **Changed:** Writer agent expects `output_format` in execution context (not direct import)
- **Migration:** Ensure `PipelineContext.output_format` is set before writer execution
- **Rationale:** Cleaner architecture, no import-time side effects

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
