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
uv run egregora top --limit=10          # Show top-ranked posts
uv run egregora doctor                  # Run health checks
uv run egregora runs list               # List pipeline runs

# Reader agent
uv run egregora read rank ./output/docs/posts
uv run egregora show reader-history --limit=20

# Serve
cd output && uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

## Breaking Changes

**Recent (last 60 days)** - See [CHANGELOG.md](CHANGELOG.md) for full history

### 2025-11-27 (PR #TBD - Async RAG Migration with Dual-Queue Embedding Router)

**Complete Async Migration of RAG Backend**
- **Changed:** All RAG APIs are now fully async
- **Before:** Sync API with blocking calls
  ```python
  # Old sync API (no longer supported)
  from egregora.rag import index_documents, search
  index_documents([doc])  # Blocking call
  response = search(request)  # Blocking call
  ```
- **After:** Async API with proper await
  ```python
  # New async API (required)
  from egregora.rag import index_documents, search
  await index_documents([doc])  # Async call
  response = await search(request)  # Async call
  ```
- **Migration for Sync Callers:** Use `asyncio.run()` wrapper
  ```python
  import asyncio
  asyncio.run(index_documents([doc]))
  response = asyncio.run(search(request))
  ```

**Dual-Queue Embedding Router**
- **Added:** New `egregora.rag.embedding_router` module with intelligent routing
- **Architecture:** Dual-queue system routes requests to optimal endpoint
  - **Single endpoint:** Low-latency, preferred for queries (1 request/sec)
  - **Batch endpoint:** High-throughput, used for bulk indexing (1000 embeddings/min)
- **Features:**
  - Independent rate limit tracking per endpoint
  - Automatic 429 fallback and retry with exponential backoff
  - Request accumulation during rate limits
  - Intelligent routing based on request size and endpoint availability
- **Configuration:** New settings in `.egregora/config.yml`:
  ```yaml
  rag:
    embedding_max_batch_size: 100  # Max texts per batch request
    embedding_timeout: 60.0  # Timeout for embedding requests
  ```
- **Performance:** Significantly improved throughput for bulk indexing operations
- **Asymmetric Embeddings:** Proper support for Google Gemini's asymmetric embeddings
  - Documents: `RETRIEVAL_DOCUMENT` task type
  - Queries: `RETRIEVAL_QUERY` task type
  - Better retrieval quality through task-specific embeddings

**Breaking Changes:**
- **API Surface:** All `index_documents()` and `search()` calls must use `await`
- **Sync Integration:** Sync code must wrap calls in `asyncio.run()`
- **Test Updates:** All RAG tests converted to async (`@pytest.mark.asyncio`)
- **Impact:** Any code calling RAG functions must be updated to handle async

**Performance Improvements:**
- **Chunking:** Fixed O(n²) performance issue in text chunking
- **Embedding Router:**
  - Dual-queue architecture maximizes API quota utilization
  - Automatic fallback prevents cascading failures
  - Request batching reduces API calls by up to 100x

**Migration Guide:**
1. **Async Context (Pydantic-AI tools):** Already async, just add `await`
2. **Sync Context (pipeline orchestration):** Wrap in `asyncio.run()`
3. **Tests:** Add `@pytest.mark.asyncio` decorator and `await` calls
4. **Custom Embedding Functions:** Must now be async with signature:
   ```python
   async def embed_fn(texts: Sequence[str], task_type: str) -> list[list[float]]
   ```

**Files Changed:**
- `src/egregora/rag/__init__.py`: Async API signatures
- `src/egregora/rag/lancedb_backend.py`: Async backend methods
- `src/egregora/rag/embedding_router.py`: New dual-queue router
- `src/egregora/rag/embeddings_async.py`: New async embedding API
- `src/egregora/agents/writer.py`: Tool updated with `await`
- `src/egregora/orchestration/write_pipeline.py`: Wrapped in `asyncio.run()`
- `tests/unit/rag/*.py`: All tests converted to async

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
│   ├── main.py              # Main app (write, init, top, doctor)
│   ├── read.py              # Reader agent commands
│   └── runs.py              # Run tracking commands
├── orchestration/            # Workflows (Layer 3)
│   ├── write_pipeline.py    # Main pipeline coordination
│   ├── context.py           # PipelineContext, PipelineRunParams
│   └── factory.py           # Factory for creating pipeline components
├── transformations/          # Pure functional (Layer 2)
│   ├── windowing.py         # Window creation, checkpointing
│   └── enrichment.py        # Enrichment transformations
├── input_adapters/          # Layer 2
│   ├── whatsapp/            # WhatsApp adapter package
│   │   ├── adapter.py       # Main adapter
│   │   ├── parsing.py       # Export parsing
│   │   ├── commands.py      # In-chat command parsing
│   │   ├── dynamic.py       # Dynamic conversation handling
│   │   └── utils.py         # WhatsApp utilities
│   ├── iperon_tjro.py       # Brazilian judicial API adapter
│   ├── self_reflection.py   # Re-ingest past posts adapter
│   ├── base.py              # Base adapter implementations
│   └── registry.py          # InputAdapterRegistry
├── output_adapters/         # Layer 2
│   ├── mkdocs/              # MkDocs output adapter
│   │   ├── adapter.py       # Main adapter
│   │   └── paths.py         # Path conventions
│   ├── parquet/             # Parquet output adapter
│   │   ├── adapter.py       # Main adapter
│   │   └── schema.py        # Parquet schema
│   ├── base.py              # Base adapter implementations
│   └── conventions.py       # Output conventions
├── database/                # Layer 2
│   ├── ir_schema.py         # All schema definitions (IR_MESSAGE_SCHEMA, etc.)
│   ├── duckdb_manager.py    # DuckDBStorageManager
│   ├── views.py             # View registry (daily_aggregates, etc.)
│   ├── tracking.py          # Run tracking (INSERT+UPDATE)
│   ├── run_store.py         # Run tracking storage
│   ├── elo_store.py         # ELO ratings storage
│   ├── sql.py               # SQLManager (Jinja2 templates)
│   ├── streaming/stream.py  # Streaming utilities
│   ├── init.py              # Database initialization
│   ├── protocols.py         # Database protocols
│   └── utils.py             # Database utilities
├── rag/                     # RAG implementation (Layer 2)
│   ├── lancedb_backend.py   # LanceDB backend (async)
│   ├── embedding_router.py  # Dual-queue embedding router
│   ├── embeddings_async.py  # Async embedding API
│   ├── ingestion.py         # Document ingestion
│   ├── backend.py           # RAGBackend protocol
│   └── models.py            # Pydantic models (RAGQueryRequest, etc.)
├── data_primitives/         # Layer 1
│   ├── document.py          # Document, DocumentType, MediaAsset
│   └── protocols.py         # OutputAdapter, InputAdapter protocols
├── agents/                  # Pydantic-AI agents
│   ├── writer.py            # Post generation agent
│   ├── enricher.py          # URL/media enrichment agent
│   ├── reader/              # Reader agent package
│   │   ├── agent.py         # Main reader agent
│   │   ├── elo.py           # ELO ranking system
│   │   ├── models.py        # Reader models
│   │   └── reader_runner.py # Reader execution runner
│   ├── banner/              # Banner generation agent
│   │   └── agent.py         # Banner generation
│   ├── tools/               # Agent tools
│   │   ├── skill_injection.py  # Skill injection system
│   │   └── skill_loader.py     # Skill loading
│   ├── registry.py          # AgentResolver, ToolRegistry
│   ├── avatar.py            # Avatar generation utilities
│   ├── formatting.py        # Formatting utilities
│   ├── model_limits.py      # Model context window limits
│   ├── models.py            # Pydantic models for agents
│   └── shared/annotations/  # Annotation utilities
├── privacy/                 # Anonymization
│   ├── anonymizer.py        # Anonymization logic
│   ├── detector.py          # PII detection
│   ├── patterns.py          # Regex patterns for PII
│   ├── uuid_namespaces.py   # UUID namespace management
│   └── config.py            # Runtime privacy config
├── config/                  # Pydantic V2 settings
│   ├── settings.py          # EgregoraConfig (all settings classes)
│   ├── config_validation.py # Date/timezone validation
│   └── overrides.py         # ConfigOverrideBuilder
├── init/                    # Site initialization
│   └── scaffolding.py       # MkDocs site scaffolding
├── knowledge/               # Author profiling tools
│   └── profiles.py          # Profile management for LLM
├── ops/                     # Unified media operations
│   └── media.py             # Media extraction, deduplication
├── rendering/               # Site rendering templates (Jinja2)
│   └── templates/site/      # MkDocs site templates
├── resources/               # Resource files
│   ├── prompts.py           # PromptManager (Jinja2 prompt templates)
│   └── sql/                 # SQL templates (Jinja2)
│       ├── ddl/             # DDL templates
│       └── dml/             # DML templates
├── prompts/                 # Default Jinja2 prompt templates
│   ├── writer.jinja         # Writer agent prompt
│   ├── banner.jinja         # Banner agent prompt
│   ├── reader_system.jinja  # Reader system prompt
│   └── ...                  # Other prompts
├── templates/               # System output templates
│   ├── journal.md.jinja     # Agent execution journals
│   └── conversation.xml.jinja  # XML conversation format
├── utils/                   # Utility functions
│   ├── batch.py             # Batching utilities
│   ├── cache.py             # Caching utilities
│   ├── datetime_utils.py    # Date/time utilities
│   ├── filesystem.py        # Filesystem operations
│   ├── frontmatter_utils.py # YAML frontmatter parsing
│   ├── metrics.py           # Metrics collection
│   ├── network.py           # Network utilities
│   ├── paths.py             # Path utilities (slugify, etc.)
│   ├── quota.py             # Quota tracking
│   ├── retry.py             # Retry logic
│   ├── serialization.py     # Serialization utilities
│   ├── text.py              # Text processing utilities
│   └── zip.py               # ZIP file handling
├── constants.py             # Type-safe enums and constants
└── diagnostics.py           # Health check system
```

## Design Principles

✅ **Privacy-First:** Anonymize BEFORE LLM (critical invariant)
✅ **Ibis Everywhere:** DuckDB tables, pandas only at boundaries
✅ **Functional Transforms:** `Table → Table` (no classes)
✅ **Schemas as Contracts:** All stages preserve `IR_MESSAGE_SCHEMA`
✅ **Simple Default:** Full rebuild (--resume for incremental)
✅ **Alpha Mindset:** Clean breaks, no backward compatibility

## Agents

Four specialized Pydantic-AI agents handle different pipeline stages:

1. **Writer** (`agents/writer.py`) - Generate blog posts from conversation windows
   - Input: XML conversation window, Output: Markdown with frontmatter
   - Tools: RAG search for past content, L3 cache for zero-cost re-runs
   - Config: `models.writer`, `writer.custom_instructions`

2. **Enricher** (`agents/enricher.py`) - Extract and enrich URLs/media/text
   - URL: title/description extraction, Media: captions/descriptions, Text: key points
   - L1 cache for asset-level caching
   - Config: `models.enricher`, `models.enricher_vision`, `enrichment.*`

3. **Reader** (`agents/reader/`) - Post quality evaluation via ELO ranking
   - Pairwise comparison (A vs B), SQLite persistence, comparison history
   - Use: `egregora read rank`, `egregora top`, `egregora show reader-history`
   - Config: `models.reader`, `reader.comparisons_per_post`, `reader.k_factor`

4. **Banner** (`agents/banner/`) - Generate cover images with Gemini Imagen
   - Input: post title/summary, Output: PNG to `docs/assets/banners/`
   - Config: `models.banner`

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

### Prompt Management

```python
from egregora.resources.prompts import PromptManager

# Load Jinja2 templates from .egregora/prompts/ or src/egregora/prompts/
manager = PromptManager(custom_dir=Path(".egregora/prompts"))
prompt = manager.get_template("writer.jinja")
rendered = prompt.render(conversation_xml=xml, custom_instructions=instructions)
```

### SQL Template Management

```python
from egregora.database.sql import SQLManager

# Load SQL templates from resources/sql/
sql_mgr = SQLManager()
query = sql_mgr.render("ddl/create_index.sql.jinja",
                       table="messages",
                       column="timestamp")
conn.execute(query)
```

### Type-Safe Constants

```python
from egregora.constants import (
    DocumentType,
    PipelineStep,
    StepStatus,
    RetrievalMode,
    KNOWN_MODEL_LIMITS
)

# Use enums instead of magic strings
if step == PipelineStep.ENRICHMENT:
    max_tokens = KNOWN_MODEL_LIMITS["gemini-flash"]
```

### URL Generation (UrlConvention Protocol)

**See [docs/architecture/protocols.md](docs/architecture/protocols.md#url-generation) for complete documentation.**

Quick summary: `UrlConvention` protocol enables deterministic URL generation for documents.

```python
from egregora.data_primitives.protocols import UrlContext, UrlConvention

# UrlContext: frozen dataclass with context for URL generation
ctx = UrlContext(base_url="https://example.com", site_prefix="/blog")

# UrlConvention: Protocol for deterministic URL generation
# Pure function pattern: same document → same URL (no I/O, no side effects)
# Pattern ensures stable URLs across rebuilds (critical for SEO/links)
```

**Key properties:**
- Deterministic: same document → same URL
- Pure: no I/O, no side effects
- Versioned: `name` and `version` properties for compatibility checks

## Configuration

**See [docs/configuration.md](docs/configuration.md) for complete auto-generated reference.**

**File:** `.egregora/config.yml`

**Key settings groups** (13 Pydantic V2 classes):
- `models`, `rag`, `writer`, `enrichment`, `pipeline`, `paths`, `database`, `output`, `reader`, `quota`

**Minimal config:**
```yaml
models:
  writer: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001
rag:
  enabled: true
pipeline:
  step_size: 1
  step_unit: days
```

**Custom prompts:** `.egregora/prompts/` (overrides `src/egregora/prompts/`)

**Regenerate docs:** `python dev_tools/generate_config_docs.py`

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

**Pre-commit hooks are MANDATORY** - Install with `python dev_tools/setup_hooks.py`

```bash
uv run pre-commit run --all-files  # Mandatory (runs all hooks)
uv run pytest tests/unit/          # Fast sanity check
```

**Pre-commit hooks configured:**

1. **Ruff (strict configuration)**
   - `ruff check --fix --unsafe-fixes` - Linting with auto-fixes
   - `ruff-format` - Code formatting (black-compatible)
   - Line length: 110 characters
   - Enforces: import sorting, unused imports, complexity limits, security checks

2. **Standard hooks (pre-commit-hooks)**
   - `check-added-large-files` - Prevent committing large files
   - `check-ast` - Validate Python syntax
   - `check-case-conflict` - Prevent case conflicts
   - `check-json` - Validate JSON files
   - `check-toml` - Validate TOML files
   - `check-yaml` - Validate YAML files
   - `debug-statements` - Prevent debug statements (`print`, `pdb`)
   - `end-of-file-fixer` - Ensure files end with newline
   - `mixed-line-ending` - Normalize line endings
   - `trailing-whitespace` - Remove trailing whitespace

**Quality checks** (not in pre-commit, run manually):
```bash
scripts/quality.sh  # Additional complexity, dead code, security scans
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

## Known Issues & Current Limitations

### Architecture

**Legacy RAG Code**
- `egregora.agents.shared.rag` module still exists but is deprecated
- All new code should use `egregora.rag` package
- **TODO:** Remove legacy RAG module in future cleanup PR

**Mixed Sync/Async Patterns**
- RAG APIs are fully async (correct)
- Pipeline orchestration is sync with `asyncio.run()` wrappers
- **Consider:** Full async pipeline migration for better performance

**Constants Module Organization**
- `constants.py` at root level (good for visibility)
- Some constants still duplicated across modules
- **TODO:** Consolidate all magic strings to `constants.py`

### Configuration

**Privacy Settings Placeholder**
- `PrivacySettings` class exists but is empty
- Privacy behavior is hardcoded in `privacy/` module
- **TODO:** Make privacy behavior configurable

**Model Naming Inconsistency**
- Some models use Pydantic-AI format (`google-gla:*`)
- Some use Google GenAI format (`models/*`)
- Both work but documentation should clarify

### Testing

**VCR Cassette Management**
- First run requires `GOOGLE_API_KEY`
- Cassettes committed to repo (can get large)
- **Consider:** Cassette cleanup policy

**Async Test Coverage**
- RAG tests converted to async
- Some integration tests still sync
- **TODO:** Convert remaining tests to async where appropriate

### Performance

**Chunking Performance**
- Fixed O(n²) issue in text chunking (PR #TBD)
- May still have issues with very large documents (>100K tokens)
- **Monitor:** Document size limits

**Embedding Router**
- Dual-queue router improves throughput significantly
- Still subject to Google API rate limits
- **TODO:** Add configurable retry strategies per endpoint

### Documentation

**API Documentation**
- Inline docstrings exist but incomplete
- No auto-generated API docs (Sphinx/mkdocstrings)
- **TODO:** Add comprehensive API documentation

**Migration Guides**
- Breaking changes documented in CLAUDE.md
- No automated migration scripts
- **Consider:** Add migration tooling for major version bumps

### Deployment

**GitHub Pages Deployment**
- Automated deployment to demo site works
- Requires manual secrets configuration
- **TODO:** Document deployment setup process

**Docker Support**
- No official Docker image yet
- Users must install dependencies manually
- **Consider:** Add Dockerfile for containerized deployment

### Known Bugs

**None currently tracked** - File issues at https://github.com/franklinbaldo/egregora/issues

## Resources

- **README.md:** User-facing docs, quick start
- **docs/:** Architecture, privacy, API reference
- **tests/fixtures/golden/:** Example outputs
- **SECURITY.md:** Security policy
