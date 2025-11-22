# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Overview

**Egregora**: WhatsApp conversations → blog posts via LLM. Privacy-first staged pipeline with anonymization before AI processing.

- **Repository**: https://github.com/franklinbaldo/egregora
- **Python**: 3.12+ | **Package Manager**: uv | **Primary LLM**: Google Gemini

## Recent Changes (2025-11-17)

**Infrastructure Simplification** (5 major changes, ~1,500 LOC removed):

1. **Tracking Infrastructure**: Event-sourced `run_events` removed, simplified to stateful `runs` table
   - Pattern: INSERT with status='running', UPDATE to 'completed'/'failed'
   - Lineage: `parent_run_id` column for simple lineage (no separate table needed)
   - Extensibility: `attrs` JSON column for future metadata

2. **IR Schema**: Python as single source of truth (SQL/JSON lockfiles removed)
   - Canonical: `src/egregora/database/validation.py:IR_MESSAGE_SCHEMA`
   - No multi-file sync: Update schema in Python only
   - Lockfiles deleted: No need for synchronization artifacts

3. **Validation**: `validate_stage` decorator removed
   - Pattern: Call `validate_ir_schema(table)` manually when needed
   - Simpler: No auto-detection of methods vs functions
   - Explicit > implicit

4. **Fingerprinting**: Content-based fingerprinting completely removed
   - Checkpointing: File existence checks only (simpler, transparent)
   - No expensive table sorting or PyArrow conversions
   - Can add back lightweight fingerprinting if truly needed

5. **Dev Tooling**: Custom scripts replaced with standard ruff
   - Import bans: `ruff.lint.flake8-tidy-imports.banned-api` in pyproject.toml
   - Complexity: `radon cc` for cyclomatic complexity
   - Quality: `scripts/quality.sh` shell script (not custom Python orchestrator)

**Checkpoint Simplification**: Checkpointing is now **OPT-IN** (disabled by default).
- Default behavior: Always rebuild from scratch (simpler, fewer mysteries)
- Enable with `--resume` flag or `checkpoint_enabled: true` in config
- Rationale: Alpha mindset - simplicity over premature optimization
- See commit history and `docs/SIMPLIFICATION_PLAN.md` for details

## Recent Changes (2025-11-22)

**Quality-of-Life Improvements** (PR #855):

1. **Statistics Page Auto-generation**
   - Generates `posts/{date}-statistics.md` automatically after pipeline runs
   - Shows total messages, unique authors, date range, and daily activity table
   - Uses existing `daily_aggregates_view` (View Registry)
   - Non-critical path: errors don't block pipeline completion

2. **WhatsApp System Message Filtering**
   - Automatically removes 18+ system message patterns (encryption notices, join/leave, calls, etc.)
   - Reduces noise in LLM inputs for cleaner post generation
   - Logged count of removed messages for transparency

3. **Interactive Site Initialization**
   - `egregora init` now prompts for site name (improves UX)
   - Auto-detects non-TTY environments (CI/CD) and disables prompts
   - Use `--no-interactive` flag to explicitly disable

4. **OutputAdapter Memory Optimization** (BREAKING)
   - `documents()` method changed from `list[Document]` to `Iterator[Document]`
   - Enables processing sites with thousands of documents without memory issues
   - **Migration**: Materialize with `list(adapter.documents())` if you need random access

5. **GitHub Actions Template**
   - Fixed Jinja escaping in `.github/workflows/publish.yml.jinja`
   - Proper handling of GitHub Actions variables

## Quick Commands

```bash
# Setup
uv sync --all-extras
python dev_tools/setup_hooks.py

# Test
uv run pytest tests/                    # All tests
uv run pytest tests/unit/               # Unit only
uv run pytest --cov=egregora tests/     # With coverage

# Lint
uv run pre-commit run --all-files       # All checks (line length: 110)
uv run ruff check --fix src/            # Auto-fix

# Run pipeline (default: full rebuild)
export GOOGLE_API_KEY="your-key"
uv run egregora write export.zip --output=./output
uv run egregora write export.zip --step-size=100 --step-unit=messages

# Opt-in incremental processing (resume from checkpoint)
uv run egregora write export.zip --output=./output --resume

# Site initialization
uv run egregora init ./output            # Interactive (prompts for site name)
uv run egregora init ./output --no-interactive  # Non-interactive (for CI/CD)

# Observability
uv run egregora runs tail               # Recent runs
uv run egregora runs show <run_id>      # Run details

# Serve
cd output && uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

## Pre-commit Hooks Are Mandatory

Every contributor must install the repository's pre-commit hooks immediately after cloning so local commits run the same linting,
formatting, and security checks as CI. Run `python dev_tools/setup_hooks.py` (preferred) or `uv run pre-commit install` before
opening a pull request, and re-run the command whenever the hook list changes. If the hooks are missing, your commits may fail in
CI and will be blocked from merging.

**VCR cassettes**: First run needs `GOOGLE_API_KEY`, subsequent runs replay from `tests/cassettes/`.

## Parallel Subagent Delegation

For repetitive tasks across 5+ independent files:

**When to use**: Similar tasks, independent files, clear pattern, 5+ files
**How**: Launch multiple Task tool calls in single message

```python
# Example: Fix BLE001 across 10 files → 5 parallel subagents
Task 1: Fix BLE001 in writer_agent.py
Task 2: Fix BLE001 in cli.py
Task 3: Fix BLE001 in enrichment/batch.py + enrichment/core.py
```

**Subagent prompt guidelines**:
1. Exact file paths + error codes
2. Clear rules (e.g., "NEVER use `except Exception:`")
3. Verification command
4. Disable git operations
5. Request summary

**After completion**: Verify with `ruff check`, review diff, run tests, format, single commit

**Don't delegate**: Coordinated changes, interdependent files, exploratory work

## Post-Commit Reflection

After each commit/push, reflect on:
- Technical decisions and why
- What worked/didn't work
- Error patterns
- Architecture insights

Ask permission to update CLAUDE.md with valuable insights (non-obvious fixes, architecture decisions, design tradeoffs).

## Naming Conventions (Updated 2025-01)

Egregora follows PEP 8 and Python idioms for clear, consistent naming across the codebase.

### Module Names

- **Use descriptive snake_case**: `file_system.py` not `filesystem.py`
- **Be specific over generic**: `duckdb_manager.py` not `storage.py`, `writer_runner.py` not `core.py`
- **Avoid redundant names**: `llm_tools.py` not `shared/shared.py`

### Class Names

**Configuration (Pydantic models in `config/settings.py`)**:
- Pattern: `*Settings` for Pydantic BaseModel configs
- Examples: `ModelSettings`, `RAGSettings`, `PipelineSettings`, `WriterAgentSettings`
- Distinguishes Pydantic models (persisted) from runtime dataclasses (ephemeral)

**Runtime contexts (dataclasses)**:
- Pattern: `*Context` or `*Config` for runtime-only dataclasses
- Examples: `WriterAgentContext`, `ProcessConfig`, `RuntimeContext`
- Never persisted, used for function parameters

**Database**:
- Pattern: `{Technology}{Purpose}` for managers
- Examples: `DuckDBStorageManager` not `StorageManager`
- Pattern: `{Domain}{Type}` for data models
- Examples: `IRMessageRow` not `IRv1Row`, `IR_MESSAGE_SCHEMA` not `IR_V1_SCHEMA`

**Utils**:
- Pattern: `*Settings` for configuration dataclasses
- Example: `ZipValidationSettings` not `ZipValidationLimits`

**Adapters (System Boundaries)**:
- Pattern: `Input*` for bringing data INTO the pipeline, `Output*` for taking data OUT
- Examples: `InputAdapter` not `SourceAdapter`, `OutputAdapter` not `OutputFormat`
- Registries: `InputAdapterRegistry`, `OutputAdapterRegistry`
- Implementations: `WhatsAppAdapter`, `SlackAdapter` (implement `InputAdapter`)
- Implementations: `MkDocsOutputAdapter`, `HugoOutputAdapter` (implement `OutputAdapter`)
- Rationale: Creates clear symmetry defining system boundaries (IN vs OUT)

### Function Names

- **Use explicit verbs**: `get_adapter_metadata()` not `adapter_meta()`
- **Be descriptive**: `embed_texts_in_batch()` not `embed_batch()`
- **Clarify purpose**: `embed_query_text()` not `embed_query()`

### Variable Names

- **Source-agnostic naming**: `input_file` not `zip_file`, `input_path` not `zip_path`
- **Explicit thresholds**: `min_similarity_threshold` not `min_similarity`

### File Renames Summary

| Old                                | New                                    | Rationale                          |
|------------------------------------|----------------------------------------|------------------------------------|
| `config/schema.py`                 | `config/settings.py`                   | Settings not schema                |
| `database/storage.py`              | `database/duckdb_manager.py`           | Explicit technology                |
| `database/schemas.py`              | `database/ir_schema.py`                | Focus on IR                        |
| `utils/filesystem.py`              | `utils/file_system.py`                 | PEP 8 snake_case                   |
| `utils/dates.py`                   | `utils/time_utils.py`                  | Broader scope                      |
| `agents/shared/shared.py`          | `agents/shared/llm_tools.py`           | Avoid redundancy                   |
| `agents/shared/profiler.py`        | `agents/shared/author_profiles.py`     | Noun-based clarity                 |
| `agents/writer/core.py`            | `agents/writer/writer_runner.py`       | Explicit role                      |
| `agents/writer/context.py`         | `agents/writer/context_builder.py`     | Action-based naming                |
| `agents/banner/generator.py`       | `agents/banner/image_generator.py`     | Content type explicit              |
| `storage/output_format.py`         | `storage/output_adapter.py`            | Adapter not just format            |
| `rendering/mkdocs_output_format.py` | `output_adapters/mkdocs_output_adapter.py` | Consistent adapter naming   |

### Package Renames Summary

| Old                | New                      | Rationale                                    |
|--------------------|--------------------------|----------------------------------------------|
| `core/` + `types.py` | `data_primitives/`     | Consolidates fundamental data models         |
| `adapters/`        | `input_adapters/`        | Explicit: brings data INTO pipeline          |
| `rendering/`       | `output_adapters/`       | Explicit: takes data OUT of pipeline         |

## Architecture: Staged Pipeline

```
Ingestion → Privacy → Augmentation → Knowledge ← Generation → Publication
Parse ZIP   UUIDs     LLM enrich      RAG/Elo     Writer      MkDocs
```

These stages are coordinated by the **orchestration layer** (`orchestration/`), which provides high-level workflows like `write_pipeline.run()` that execute the complete sequence.

### Key Stages

1. **Ingestion** (`input_adapters/`): `InputAdapter` → `parse()` → `IR_MESSAGE_SCHEMA`
2. **Privacy** (`privacy/`): Names → UUIDs, PII detection BEFORE LLM
3. **Augmentation** (agents): LLM URL/media descriptions, profiles
4. **Knowledge** (`agents/shared/rag/`): RAG (DuckDB VSS), annotations, Elo rankings
5. **Generation** (`agents/`): Pydantic-AI agents with tools (writer, reader, enricher)
6. **Publication** (`output_adapters/`): `OutputAdapter` → `persist()` → MkDocs/Hugo/etc.

### Design Principles

1. **Trust the LLM**: Full context → editorial decisions
2. **Ibis everywhere**: DuckDB tables, pandas only at boundaries
3. **Privacy-first**: Anonymize before LLM
4. **Schemas as contracts**: All stages preserve `CONVERSATION_SCHEMA`
5. **Functional transforms**: `Table → Table`
6. **Alpha mindset**: No backward compatibility, clean breaks

### Modern Patterns (Phases 2-7, 2025-01)

**Config objects**: `EgregoraConfig` + `RuntimeContext` dataclasses (no >5 params)
**Frozen dataclasses**: `@dataclass(frozen=True, slots=True)`
**Simple resume**: Check output exists → skip
**Source organization**: `sources/{whatsapp,slack}/`, generic in `ingestion/base.py`
**Generic naming**: `parse_source()` not `parse_export()`

**Flexible windowing (Phase 7)**:
- Units: `messages` (count), `hours`/`days` (time), `bytes` (text size)
- Sequential indices (0, 1, 2...) not calendar keys
- Runtime-only (NOT persisted)
- CLI: `--step-size`, `--step-unit`, `--min-window-size`

**View Registry (C.1)**:
- `ViewBuilder = Callable[[Table], Table]`
- Centralized pipeline transformations: `views.get("chunks")`
- Built-in: `chunks`, `hourly_aggregates`, `daily_aggregates`
- Register: `@views.register("my_view")`
- Docs: `docs/pipeline/view-registry.md`

**DuckDBStorageManager (C.2)**:
- Centralized DuckDB + parquet checkpointing
- `with DuckDBStorageManager() as storage:`
- `storage.write_table(table, "name", checkpoint=True)`
- `storage.execute_view("output", builder, "input")`
- Docs: `docs/database/storage-manager.md`

**Schema Validation**:
- Manual validation via `validate_ir_schema(table)` function
- Call explicitly when needed (no decorator)
- Pattern: Validate inputs/outputs of critical transformations
- Docs: `src/egregora/database/validation.py` docstrings

**Run Tracking (D.1)**:
- Auto tracking in `.egregora/runs.duckdb`
- `egregora runs tail` / `egregora runs show <run_id>`
- Observability only (don't depend on for pipeline logic)
- Docs: `docs/observability/runs-tracking.md`

**Agent Skill Injection (2025-01-11)**:
- Sub-agents via `use_skill(ctx, "skill-name", "task")`
- Skills in `.egregora/skills/*.md`
- Parent gets summary only
- Deps must implement `SkillInjectionSupport` protocol
- Files: `agents/tools/skill_loader.py`, `skill_injection.py`
- Tests: `tests/agents/test_skill_injection.py`
- Docs: `.egregora/skills/README.md`

## Code Structure

**Three-Layer Functional Architecture**: The codebase follows clean architecture with explicit separation of concerns. **No PipelineStage abstraction** - all transformations are pure functions (Table → Table).

### Why Functional?

**ELIMINATED** (2025-01-12): `PipelineStage` class hierarchy. The OOP stage abstraction added unnecessary ceremony for what are fundamentally simple functional transformations. Benefits of removal:

- ✅ **Simpler**: Functions > Classes for Table → Table transforms
- ✅ **Explicit**: `orchestration/` sequences steps directly, no dynamic discovery
- ✅ **Functional**: Embraces "Functional transforms: Table → Table" (Design Principles)
- ✅ **Less boilerplate**: -811 lines of code, clearer intent

**Validation** done manually when needed (decorator removed for simplicity):

```python
from egregora.database.validation import validate_ir_schema

def filter_messages(data: Table, min_length: int = 0) -> Table:
    validate_ir_schema(data)  # Validate input if needed
    result = data.filter(data.text.length() >= min_length)
    return result
```

### Three Layers

**Layer 3: Business Workflows** (`orchestration/`)
- High-level execution flows for user-facing commands
- Explicitly sequences functional transformations
- `write_pipeline.py`: Complete write workflow (ingest → process → generate → publish)

**Layer 2: Infrastructure** (`transformations/`, `input_adapters/`, `output_adapters/`, `database/`)
- **`transformations/`**: Pure functional data manipulation (windowing, media processing)
- **`database/`**: Persistence, tracking, views, validation (infrastructure + state)
- **`input_adapters/`**: Brings external data IN to the system
- **`output_adapters/`**: Takes structured data OUT for publication

**Layer 1: Foundation** (`data_primitives/`)
- Core data models: Document, DocumentType, GroupSlug, PostSlug
- Universal data types used across all layers

```
src/egregora/
├── cli/                      # CLI commands and interface
│   ├── main.py              # Main Typer app (write, init, top, doctor)
│   ├── runs.py              # Run tracking commands
│   └── read.py              # Reader agent commands
├── orchestration/            # BUSINESS WORKFLOWS (Layer 3)
│   ├── write_pipeline.py    # Write workflow: ingest → process → generate → publish
│   └── context.py           # Runtime context
├── data_primitives/          # FOUNDATION (Layer 1)
│   ├── document.py          # Document, DocumentType, DocumentCollection
│   ├── base_types.py        # GroupSlug, PostSlug
│   └── protocols.py         # Core protocols (OutputAdapter, UrlConvention)
├── transformations/          # PURE FUNCTIONAL TRANSFORMATIONS (Layer 2)
│   └── windowing.py         # create_windows, Window, checkpointing
├── ops/                      # Operational transformations
│   └── media.py             # Media operations
├── database/                 # INFRASTRUCTURE & STATE (Layer 2)
│   ├── ir_schema.py         # IR schema definitions (IR_MESSAGE_SCHEMA, runs table)
│   ├── duckdb_manager.py    # DuckDB connection management (C.2)
│   ├── validation.py        # Schema validation
│   ├── views.py             # View registry (C.1)
│   └── tracking.py          # Run tracking (INSERT+UPDATE pattern)
├── config/
│   ├── settings.py          # EgregoraConfig (Pydantic settings models)
│   └── config_validation.py # Config validation utilities
├── input_adapters/           # INPUT ADAPTERS (Layer 2)
│   ├── base.py              # InputAdapter protocol
│   ├── whatsapp.py          # WhatsAppAdapter
│   ├── iperon_tjro.py       # Brazilian judicial API adapter
│   ├── self_reflection.py   # Self-reflection adapter
│   └── registry.py          # Adapter registry
├── privacy/                  # Anonymization, PII detection
│   ├── anonymizer.py        # UUID-based anonymization
│   └── detector.py          # PII detection
├── agents/                   # Pydantic-AI agents
│   ├── writer.py            # Post generation agent
│   ├── reader.py            # Reader/ranking agent
│   ├── enricher.py          # URL/media enrichment agent
│   ├── shared/              # Shared agent utilities
│   │   └── rag/             # RAG implementation
│   │       ├── indexing.py  # Document indexing
│   │       ├── retriever.py # Vector search
│   │       └── store.py     # Vector store
│   └── tools/               # Agent skills & tool injection
├── output_adapters/          # OUTPUT ADAPTERS (Layer 2)
│   ├── base.py              # OutputAdapter base implementations
│   ├── conventions.py       # URL conventions
│   └── mkdocs/              # MkDocs implementation
│       ├── adapter.py       # MkDocsAdapter
│       └── paths.py         # Path resolution
├── knowledge/                # Knowledge management
│   └── profiles.py          # Author profiling
├── init/                     # Site initialization
├── prompts/                  # LLM prompt templates
├── rendering/                # Rendering logic
├── resources/                # Package resources (prompts, templates)
├── templates/                # Jinja2 templates
└── utils/                    # Shared utilities
    ├── cache.py             # DiskCache
    ├── batch.py             # Batch processing
    ├── quota.py             # Rate limiting
    ├── filesystem.py        # File utilities
    ├── frontmatter_utils.py # YAML frontmatter parsing
    ├── paths.py             # Path utilities (slugify, etc)
    └── zip.py               # ZIP file operations
```

## Database Schemas

All in `database/ir_schema.py`:

**Ephemeral** (in-memory):
- `CONVERSATION_SCHEMA`: Pipeline data (timestamp, author, message, etc.)

**Persistent** (DuckDB/Parquet):
- `RUNS_TABLE_SCHEMA`: Pipeline run tracking (simplified stateful model)
- `RAG_CHUNKS_SCHEMA`: Vector embeddings
- `ANNOTATIONS_SCHEMA`: Conversation metadata
- `ELO_RATINGS_SCHEMA`: Post quality

**Invariant**: All stages preserve `CONVERSATION_SCHEMA` (now `IR_MESSAGE_SCHEMA`)

## Testing

- `tests/unit/`: Pure functions
- `tests/integration/`: DuckDB, API (VCR)
- `tests/e2e/`: Full pipeline (golden fixtures)
- `tests/agents/`: Agent tests

**VCR**: Record/replay Gemini calls (cassettes in `tests/cassettes/`)
**Golden fixtures**: `tests/fixtures/golden/expected_output/`
**VSS**: Use `--retrieval-mode=exact` in CI

## Configuration

**Env vars**: Only `GOOGLE_API_KEY`

**Config file**: `.egregora/config.yml` (maps to `EgregoraConfig`)

```yaml
models:
  writer: google-gla:gemini-flash-latest
  enricher: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001

rag:
  enabled: true
  top_k: 5
  mode: ann                    # "ann" or "exact"

writer:
  custom_instructions: "..."
  enable_banners: true

pipeline:
  step_size: 100
  step_unit: messages          # "messages", "hours", "days", "bytes"
```

**Custom prompts**: `.egregora/prompts/` overrides `src/egregora/prompts/`

### Model Thinking/Reasoning

Enable thinking for complex tasks:

```python
# Gemini
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
settings = GoogleModelSettings(google_thinking_config={'include_thoughts': True})

# Claude
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
settings = AnthropicModelSettings(anthropic_thinking={'type': 'enabled', 'budget_tokens': 1024})
```

**Token tracking**: `tokens_input`, `tokens_output`, `tokens_cache_*`, `tokens_thinking`, `tokens_reasoning`

**Journal entries**: Auto-saved to `output/journal/journal_*.md`
- Intercalated log: thinking + journal entries + tool calls/returns
- YAML frontmatter with timestamp
- Benefits: transparency, debugging, audit trail, continuity

## Development Workflow

### Adding Features

1. Identify pipeline stage
2. Check if `CONVERSATION_SCHEMA` needs updates (rarely)
3. Write tests first
4. Keep simple (can LLM do it with better prompting?)
5. Update docs

### Modifying Stages

- All stages: `Table → Table`
- Privacy MUST run before LLM
- Preserve `CONVERSATION_SCHEMA` columns
- Add columns via `.mutate()`, never drop core

### Adding Agent Tools

1. Define in `agents/writer/tools.py`
2. Register in `ToolRegistry`
3. Add to agent init
4. Test with VCR

### Debugging

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

## OutputAdapter Protocol (Updated 2025-11-22)

The `OutputAdapter` Protocol defines the contract for persisting and retrieving documents. Located in `data_primitives/protocols.py`, it provides bidirectional document access for both publishing and re-ingestion (self-reflection).

### Core Methods

**Persistence:**
```python
def persist(self, document: Document) -> None:
    """Persist document so it becomes available at its canonical URL."""
```
- Renamed from `serve()` for clarity (breaking change)
- Idempotent: Overwrites existing files for same slug/identifier
- See "Slug Collision Behavior" below for collision handling

**Document Retrieval:**
```python
def read_document(self, doc_type: DocumentType, identifier: str) -> Document | None:
    """Retrieve a single document by its doc_type primary identifier."""
```

**Document Listing (Table-based):**
```python
def list_documents(self, doc_type: DocumentType | None = None) -> Table:
    """Return all known documents as an Ibis table, optionally filtered by doc_type."""
```
- Returns Ibis Table for efficient filtering/querying
- Used by RAG indexing for incremental updates

**Document Listing (Object-based):**
```python
def documents(self) -> Iterator[Document]:
    """Return all managed documents as Document objects (lazy iterator)."""
```
- Added in PR #861, changed to Iterator in PR #855 reconciliation (2025-11-22)
- Returns lazy iterator for memory efficiency (can iterate sites with 1000s of documents)
- Used by self-reflection adapter to re-ingest published posts
- Filters documents by type and scans filesystem for all content
- Materialize with `list()` if you need len() or random access

**Path Resolution:**
```python
def resolve_document_path(self, identifier: str) -> Path:
    """Resolve storage identifier (from list_documents) to actual filesystem path."""
```
- Added in PR #861 (2025-11-22)
- Enables format-agnostic document reingestion
- MkDocs: identifier is relative path from site_root

### Usage Patterns

**Publishing (Generation → Publication):**
```python
adapter = MkDocsAdapter()
adapter.initialize(site_root, url_context)
adapter.persist(document)  # Writes to disk at canonical URL
```

**Re-ingestion (Self-Reflection):**
```python
adapter = MkDocsAdapter()
adapter.initialize(site_root)
# documents() returns Iterator - consumed by list comprehension
posts = [doc for doc in adapter.documents() if doc.type == DocumentType.POST]
# Feed back into pipeline for meta-analysis
```

**RAG Indexing (Incremental Updates):**
```python
# Lazy iteration - processes documents one at a time (memory efficient)
for document in adapter.documents():
    path = adapter.resolve_document_path(document.metadata["storage_identifier"])
    # Index document for vector search without loading all documents into memory
```

## Slug Collision Behavior (OutputAdapter)

**P1 Badge Response**: The `persist()` method has **intentional overwriting behavior** for slug-based paths.

### Design Rationale

**Posts** (slug + date):
- Path: `posts/YYYY-MM-DD-{slug}.md`
- Collision: **Overwrites** (second post with same slug+date replaces first)
- Rationale: Posts are identified by (slug, date), not content. Writing the same slug twice should UPDATE the file, like `UPDATE` in SQL or `PUT` in REST. This is idempotent publishing.

**Profiles** (UUID):
- Path: `profiles/{uuid}.md`
- Collision: **Overwrites** (updating profile for same UUID)
- Rationale: Profiles are identified by UUID. Updating a user's profile should replace the existing file, not create duplicates.

**Enrichment URLs** (content hash):
- Path: `enrichments/{hash}.md`
- Collision: **Detects and resolves** with suffix (`{hash}-1.md`)
- Rationale: Hash collisions are rare but theoretically possible. Resolution adds numeric suffix.

### Error Reporting (Future Enhancement)

Currently `persist()` returns `None` (fire-and-forget). If collision reporting is needed:

**Option 1**: Add optional return type (backward compatible)
```python
def persist(self, document: Document) -> ServeResult | None:
    """Returns ServeResult if error, None if success."""
```

**Option 2**: Use exceptions for errors
```python
def persist(self, document: Document) -> None:
    """Raises ServeError on collision (if strict mode enabled)."""
    if strict and path.exists():
        raise SlugCollisionError(...)
```

**Decision**: DEFER until needed. Current overwriting behavior is correct for idempotent publishing.

## TENET-BREAK Philosophy

Intentional principle violations:

**Tenets**: `no-compat`, `clean`, `no-defensive`, `propagate-errors`

**Format**:
```python
# TENET-BREAK(scope)[@owner][P0|P1|P2][due:YYYY-MM-DD]:
# tenet=<code>; why=<constraint>; exit=<condition> (#issue)
```

## Privacy & Security

**Flow**: Parse → UUIDs (deterministic) → PII scan → LLM (anonymized only)

**In-chat commands**:
```
/egregora set alias "Casey"
/egregora opt-out
/egregora opt-in
```

## Common Pitfalls

1. Never bypass privacy stage
2. Use Ibis, not pandas (convert only at boundaries)
3. Respect schemas in `database/ir_schema.py`
4. Commit VCR cassettes to repo
5. Use `--retrieval-mode=exact` without VSS extension

## Dependencies

**Core**: Ibis, DuckDB, Pydantic-AI, Google Gemini, MkDocs Material, uv
**Optional**: pytest-vcr, Pydantic Logfire, mkdocs-rss-plugin

## Deployment

```bash
cd output && mkdocs build
mkdocs gh-deploy
# Or: Netlify/Vercel/Cloudflare Pages (deploy ./site/)
```

## Related Docs

- `README.md`: User docs, quick start
- `docs/`: Architecture, privacy, API reference
- `tests/fixtures/golden/`: Example outputs
