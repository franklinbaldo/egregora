# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Note:** For the most recent breaking changes (last 60 days), see [CLAUDE.md](CLAUDE.md#breaking-changes).

## [Unreleased]

### 2025-12-15 - Configuration File Path Clarity

#### Changed
- Updated CLI help, diagnostics, and docs to reference `.egregora.toml` instead of the legacy `.egregora/config.yml`, with TOML-based examples to guide users.

#### Migration
- Existing projects using `.egregora/config.yml` should move settings into a root-level `.egregora.toml` for consistency with the current tooling.

### 2025-12-13 - Simplification: Remove Over-Engineered Sub-Features

#### Removed
- **Privacy Module:** Removed entire PII detection and structural anonymization system
  - Deleted `src/egregora/privacy/` directory (anonymizer, UUID namespaces, privacy config)
  - Removed privacy integration from WhatsApp adapter and agents
  - Removed privacy-related configuration classes (`PrivacySettings`, `PIIPreventionSettings`, etc.)
  - Removed privacy constants (`AuthorPrivacyStrategy`, `MentionPrivacyStrategy`, `PIIScope`, etc.)
  - **Impact:** 600+ lines removed

- **CLI Commands:** Removed `egregora config` and `egregora runs` commands
  - Deleted `src/egregora/cli/config.py` and `src/egregora/cli/runs.py`
  - Core commands (`write`, `init`, `read`) remain functional
  - **Impact:** 400+ lines removed

- **Output Formats:** Removed Parquet/JSON export adapter
  - Deleted `src/egregora/output_sinks/parquet/` directory
  - Kept MkDocs as the only output format (as documented in FEATURES.md)
  - **Impact:** 200+ lines removed

- **Dead Code Cleanup:** Removed PII remnants detected by Vulture
  - Removed `_replace_pii_media_references()` function from enricher
  - **Impact:** 13+ lines removed

#### Rationale
Removed over-engineered implementation details (sub-features) to reduce complexity while maintaining all core functionality. Total impact: **2,154 lines removed** across 27 files.

Core features (RAG, media processing, banner generation, ELO ratings, model rotation) remain unchanged and fully functional.

See `REMOVAL_PLAN.md` for detailed removal strategy and `VULTURE_ANALYSIS.md` for dead code analysis.

### 2025-11-28 - De-Async Refactor & Privacy Alignment

#### Changed
- **BREAKING:** RAG APIs (`index_documents`, `search`) are now fully synchronous.
  - Reverted the previous "Async RAG" direction to align with the core synchronous architecture.
  - Concurrency is now handled via thread pools rather than asyncio event loops.
- **Documentation:** Updated architecture guides to reflect that Privacy is an integral part of the Input Adapter stage, not a standalone pipeline step.
- **Documentation:** Updated configuration reference with explicit warnings about model prefixes (`google-gla:` vs `models/`).
- **Documentation:** Updated RAG documentation to remove all `async`/`await` references.

### 2025-11-27 - MkDocs Scaffold Defaults

#### Changed
- **BREAKING:** Default posts directory created by `egregora init` moved from `docs/blog/posts` to `docs/posts`
  - Existing sites remain valid; no migration is needed unless your automation assumes the old path
  - New scaffolds use the flatter structure to match current MkDocs defaults

### 2025-11-27 - Async RAG Migration with Dual-Queue Embedding Router

#### Changed
- **BREAKING:** All RAG APIs are now fully async
  - Before: `index_documents([doc])` (blocking)
  - After: `await index_documents([doc])` (async)
  - Migration: Wrap in `asyncio.run()` for sync callers

#### Added
- Dual-queue embedding router (`egregora.rag.embedding_router`)
  - Single endpoint: Low-latency (1 request/sec)
  - Batch endpoint: High-throughput (1000 embeddings/min)
  - Independent rate limit tracking per endpoint
  - Automatic 429 fallback and retry with exponential backoff
- Asymmetric embeddings support
  - Documents: `RETRIEVAL_DOCUMENT` task type
  - Queries: `RETRIEVAL_QUERY` task type
- New RAG settings:
  - `embedding_max_batch_size: 100`
  - `embedding_timeout: 60.0`
  - `embedding_max_retries: 3`

#### Fixed
- O(n²) performance issue in text chunking
- Chunk overlap to prevent context loss

#### Migration Guide
1. **Async Context (Pydantic-AI tools):** Add `await`
2. **Sync Context (pipeline orchestration):** Wrap in `asyncio.run()`
3. **Tests:** Add `@pytest.mark.asyncio` decorator
4. **Custom Embedding Functions:** Must be async:
   ```python
   async def embed_fn(texts: Sequence[str], task_type: str) -> list[list[float]]
   ```

#### Files Changed
- `src/egregora/rag/__init__.py` - Async API signatures
- `src/egregora/rag/lancedb_backend.py` - Async backend methods
- `src/egregora/rag/embedding_router.py` - New dual-queue router
- `src/egregora/rag/embeddings_async.py` - New async embedding API
- `src/egregora/agents/writer.py` - Tool updated with `await`
- `src/egregora/orchestration/write_pipeline.py` - Wrapped in `asyncio.run()`
- `tests/unit/rag/*.py` - All tests converted to async

---

### 2025-11-27 - LanceDB RAG Backend

#### Added
- New `egregora.rag` package with LanceDB-based vector storage
- Clean protocol-based design with `RAGBackend` interface
- Simplified API:
  ```python
  from egregora.rag import index_documents, search, RAGQueryRequest
  await index_documents([doc])
  response = await search(RAGQueryRequest(text="query", top_k=5))
  ```
- Configuration:
  ```yaml
  paths:
    lancedb_dir: .egregora/lancedb
  rag:
    enabled: true
    top_k: 5
    min_similarity_threshold: 0.7
    indexable_types: ["POST"]
  ```

#### Changed
- **BREAKING:** Similarity scores now use cosine metric (was L2 distance)
  - Scores in [-1, 1] range
  - Re-indexing recommended
- **BREAKING:** Filters API changed from `dict[str, Any]` to SQL `str`
  - Before: `filters={"category": "programming"}`
  - After: `filters="category = 'programming'"`
- **BREAKING:** Removed `top_k_default` parameter from backend initialization
  - Use `RAGQueryRequest.top_k` instead
- **BREAKING:** Increased `top_k` maximum from 20 to 100

#### Removed
- Dependencies: `langchain-text-splitters`, `langchain-core`

#### Deprecated
- `egregora.agents.shared.rag` module (use `egregora.rag` instead)

#### Fixed
- Potential SQL injection in delete operations with proper string escaping

---

### 2025-11-26 - Resumability & Fixes

#### Changed
- **BREAKING:** `mkdocs-blogging-plugin` renamed to `blog` in `mkdocs.yml` templates
  - Before: `plugins: - blogging`
  - After: `plugins: - blog`
  - Impact: Custom `mkdocs.yml` files will fail to build

#### Migration
```yaml
# Update mkdocs.yml
plugins:
  - blog  # was 'blogging'
```

---

### 2025-11-25 - RAG Indexing Optimization

#### Changed
- **BREAKING:** RAG operations centralized as VectorStore methods
  - Before: `index_documents_for_rag(output, rag_dir, storage, ...)`
  - After: `store.index_documents(output, embedding_model=...)`
- **BREAKING:** Reduced RAG export surface
  - Removed: All internal functions from `egregora.agents.shared.rag`
  - Now exported: Only `VectorStore` and `DatasetMetadata`
- **BREAKING:** Removed `resolve_document_path()` from OutputSink protocol
  - Filesystem-specific method didn't belong in general output protocol
- **BREAKING:** RAG directory now uses settings instead of hardcoded paths
  - Before: `site_root / ".egregora" / "rag"` (hardcoded)
  - After: `config.paths.rag_dir` (configurable, default: `.egregora/rag`)

#### Added
- VectorStore facade with methods:
  - `index_documents(output_format, *, embedding_model)`
  - `index_media(docs_dir, *, embedding_model)`
  - `query_media(query, ...)`
  - `query_similar_posts(table, ...)`
  - `is_available()` (static)
  - `embed_query(query_text, *, model)` (static)

#### Improved
- Exception handling: Catches `OSError`, `ValueError`, `PromptTooLargeError` explicitly
  - Before: `except Exception: # noqa: BLE001`
  - Unexpected errors now propagate with full stack traces

#### Migration
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

---

### 2025-11-23 - Multi-PR Merge

#### Added
- **Tiered Caching Architecture** (PR #890)
  - L1: Asset enrichment results (URLs, media)
  - L2: Vector search results with index metadata invalidation
  - L3: Writer output with semantic hashing (zero-cost re-runs)
  - CLI: `--refresh` flag to invalidate cache tiers
  - Usage: `egregora write export.zip --refresh=writer` or `--refresh=all`

#### Changed
- **BREAKING:** Writer input format: Markdown → XML (PR #889)
  - Before: Conversation passed as Markdown table
  - After: Compact XML format via `_build_conversation_xml()`
  - Template: `src/egregora/templates/conversation.xml.jinja`
  - Impact: Custom prompt templates must use `conversation_xml` (not `markdown_table`)
  - Rationale: ~40% token reduction, better structure preservation

#### Fixed
- VSS extension now loaded explicitly before HNSW operations (PR #893)
- Fallback avatar generation using avataaars.io (deterministic from UUID hash)
- Banner path conversion to web-friendly relative URLs
- Idempotent scaffold (detects existing mkdocs.yml)

#### Refactored
- **WhatsApp Parser** (PR #894)
  - Removed: Hybrid DuckDB+Python `_parse_messages_duckdb()`
  - Added: Pure Python `_parse_whatsapp_lines()` generator
  - No API changes, internal refactor only
  - Rationale: Eliminates serialization overhead, single-pass processing

#### Removed
- **Privacy Validation** (PR #892)
  - Removed: Mandatory `validate_text_privacy()` from `AnnotationStore.save_annotation()`
  - Rationale: Allow public datasets (judicial records) with legitimate PII
  - Impact: Privacy validation is now optional, use at input adapter level
- **Circular Import Cleanup** (PR #891)
  - Removed: Lazy `__getattr__` shim in `agents/__init__.py`
  - Changed: Writer agent expects `output_format` in execution context (not direct import)
  - Migration: Ensure `PipelineContext.output_format` is set before writer execution

---

### 2025-11-22 - OutputAdapter Iterator & Auto-generation

#### Changed
- **BREAKING:** `OutputAdapter.documents() → Iterator[Document]`
  - Before: `def documents(self) -> list[Document]`
  - After: `def documents(self) -> Iterator[Document]`
  - Migration: Use `list(adapter.documents())` if you need random access
  - Rationale: Memory efficiency for sites with 1000s of documents

#### Added
- Statistics page auto-generation
  - Generates `posts/{date}-statistics.md` after pipeline runs
  - Uses `daily_aggregates_view` (View Registry pattern)
  - Non-critical path: errors don't block completion
- Interactive init
  - `egregora init` now prompts for site name
  - Auto-detects non-TTY (CI/CD) and disables prompts
  - Use `--no-interactive` to explicitly disable

---

### 2025-11-17 - Infrastructure Simplification

#### Removed
- ~1,500 LOC removed:
  - Event-sourced `run_events` → simple `runs` table (INSERT + UPDATE pattern)
  - IR schema: Python single source of truth (no SQL/JSON lockfiles)
  - Validation: Manual `validate_ir_schema()` calls (decorator removed)
  - Fingerprinting: Removed (file existence checks only)

#### Changed
- Checkpointing: Opt-in via `--resume` (default: full rebuild)

---

## Migration Tips

### General Principles
1. **Read breaking changes carefully** - Test changes in development first
2. **Update dependencies** - Run `uv sync --all-extras` after updating
3. **Check configuration** - Many changes introduce new config options
4. **Run tests** - `uv run pytest tests/unit/` for quick sanity check
5. **Use VCR cassettes** - First run of integration tests needs `GOOGLE_API_KEY`

### Getting Help
- File issues: https://github.com/franklinbaldo/egregora/issues
- Check docs: [docs/](docs/)
- Read CLAUDE.md: [CLAUDE.md](CLAUDE.md)

---

## Semantic Versioning

Since we're pre-1.0, breaking changes can occur in any release. Once we hit 1.0:
- **MAJOR** version: Breaking changes
- **MINOR** version: New features (backward compatible)
- **PATCH** version: Bug fixes (backward compatible)
