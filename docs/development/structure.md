# Project Structure

Understanding the Egregora codebase organization.

## Repository Layout

```
egregora/
├── src/egregora/           # Main source code
├── tests/                  # Test suite (unit, integration, e2e)
├── docs/                   # Documentation (MkDocs)
├── dev_tools/              # Development utilities
├── .github/                # GitHub Actions workflows
├── pyproject.toml          # Project configuration (uv/ruff/pytest)
├── mkdocs.yml              # Documentation site configuration
├── README.md               # Project manifesto
├── CLAUDE.md               # Developer guide for AI assistants
└── LICENSE                 # MIT License
```

## Source Code Structure

Based on the three-layer functional architecture:

```
src/egregora/
├── cli/                      # Typer commands
│   ├── main.py              # Main app (write, init, top, doctor)
│   ├── read.py              # Reader agent commands
│   └── runs.py              # Run tracking commands
│
├── orchestration/            # Layer 3: High-level workflows
│   ├── write_pipeline.py    # Main pipeline coordination
│   ├── context.py           # PipelineContext, PipelineRunParams
│   └── factory.py           # Factory for creating pipeline components
│
├── transformations/          # Layer 2: Pure functional transforms
│   ├── windowing.py         # Window creation, checkpointing
│   └── enrichment.py        # Enrichment transformations
│
├── input_adapters/          # Layer 2: Bring data IN
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
│
├── output_adapters/         # Layer 2: Take data OUT
│   ├── mkdocs/              # MkDocs output adapter
│   │   ├── adapter.py       # Main adapter
│   │   └── paths.py         # Path conventions
│   ├── parquet/             # Parquet output adapter
│   │   ├── adapter.py       # Main adapter
│   │   └── schema.py        # Parquet schema
│   ├── base.py              # Base adapter implementations
│   └── conventions.py       # Output conventions
│
├── database/                # Layer 2: Persistence
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
│
├── rag/                     # Layer 2: RAG implementation
│   ├── lancedb_backend.py   # LanceDB backend (async)
│   ├── embedding_router.py  # Dual-queue embedding router
│   ├── embeddings_async.py  # Async embedding API
│   ├── ingestion.py         # Document ingestion
│   ├── backend.py           # RAGBackend protocol
│   └── models.py            # Pydantic models (RAGQueryRequest, etc.)
│
├── data_primitives/         # Layer 1: Foundation models
│   ├── document.py          # Document, DocumentType, MediaAsset
│   └── protocols.py         # OutputAdapter, InputAdapter protocols
│
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
│
├── privacy/                 # Anonymization
│   ├── anonymizer.py        # Anonymization logic
│   ├── detector.py          # PII detection
│   ├── patterns.py          # Regex patterns for PII
│   ├── uuid_namespaces.py   # UUID namespace management
│   └── config.py            # Runtime privacy config
│
├── config/                  # Pydantic V2 settings
│   ├── settings.py          # EgregoraConfig (all settings classes)
│   ├── config_validation.py # Date/timezone validation
│   └── overrides.py         # ConfigOverrideBuilder
│
├── init/                    # Site initialization
│   └── scaffolding.py       # MkDocs site scaffolding
│
├── knowledge/               # Author profiling tools
│   └── profiles.py          # Profile management for LLM
│
├── ops/                     # Unified media operations
│   └── media.py             # Media extraction, deduplication
│
├── rendering/               # Site rendering templates
│   └── templates/site/      # MkDocs site templates (Jinja2)
│
├── resources/               # Resource files
│   ├── prompts.py           # PromptManager (Jinja2 prompt templates)
│   └── sql/                 # SQL templates (Jinja2)
│       ├── ddl/             # DDL templates
│       └── dml/             # DML templates
│
├── prompts/                 # Default Jinja2 prompt templates
│   ├── writer.jinja         # Writer agent prompt
│   ├── banner.jinja         # Banner agent prompt
│   ├── reader_system.jinja  # Reader system prompt
│   └── ...                  # Other prompts
│
├── templates/               # System output templates
│   ├── journal.md.jinja     # Agent execution journals
│   └── conversation.xml.jinja  # XML conversation format
│
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
│
├── constants.py             # Type-safe enums and constants
└── diagnostics.py           # Health check system
```

## Module Responsibilities

### CLI (`cli/`)

**Purpose**: Command-line interface using Typer.

**Key commands**:
- `egregora write`: Process chat exports and generate posts
- `egregora init`: Initialize MkDocs site scaffold
- `egregora top`: Show top-ranked posts
- `egregora doctor`: Run health checks
- `egregora runs`: Manage pipeline runs
- `egregora read`: Reader agent commands

### Orchestration (`orchestration/`)

**Purpose**: High-level workflow coordination (Layer 3).

**Key modules**:
- `write_pipeline.py`: Main pipeline orchestration
- `context.py`: `PipelineContext` and `PipelineRunParams`
- `factory.py`: Component factory pattern

**Pattern**: Coordinates input adapters, transformations, agents, and output adapters.

### Transformations (`transformations/`)

**Purpose**: Pure functional transformations (Layer 2).

**Key functions**:
- `create_windows()`: Group messages into windows
- `enrich_window()`: Add enrichments to windows
- All functions follow `Table → Table` pattern

**Principle**: No side effects, pure transformations only.

### Input Adapters (`input_adapters/`)

**Purpose**: Parse external data into IR schema (Layer 2).

**Available adapters**:
- **WhatsApp**: Parse `.zip` exports with multi-format support
- **Iperon TJRO**: Brazilian judicial records API
- **Self Reflection**: Re-ingest past blog posts

**Registry**: `InputAdapterRegistry` for adapter discovery.

### Output Adapters (`output_adapters/`)

**Purpose**: Persist documents to various formats (Layer 2).

**Available adapters**:
- **MkDocs**: Create static site structure
- **Parquet**: Export structured data

**Protocol**: `OutputAdapter` with `persist()` and `documents()` methods.

### Database (`database/`)

**Purpose**: DuckDB management and schemas (Layer 2).

**Key components**:
- **ir_schema.py**: Single source of truth for all schemas
- **DuckDBStorageManager**: Context manager for database access
- **View Registry**: Reusable DuckDB views
- **Run Tracking**: Pipeline run history
- **SQLManager**: Jinja2-based SQL templating

### RAG (`rag/`)

**Purpose**: Vector search and retrieval (Layer 2).

**Architecture**:
- **LanceDB Backend**: Async vector storage
- **Embedding Router**: Dual-queue rate limiting
- **Async API**: All operations are async

**Key features**:
- Asymmetric embeddings (document vs query)
- Automatic rate limit handling
- Configurable indexable types

### Data Primitives (`data_primitives/`)

**Purpose**: Foundation models and protocols (Layer 1).

**Key classes**:
- `Document`: Core document abstraction
- `DocumentType`: Enum for document types
- `MediaAsset`: Media metadata
- `OutputAdapter`: Protocol for outputs
- `InputAdapter`: Protocol for inputs

### Agents (`agents/`)

**Purpose**: Pydantic-AI agents for LLM interactions.

**Agents**:
- **Writer**: Generate blog posts from windows
- **Enricher**: Extract and enrich URLs/media
- **Reader**: ELO-based post quality ranking
- **Banner**: Generate cover images (Gemini Imagen)

**Tools**: Skill injection system for dynamic tool loading.

### Privacy (`privacy/`)

**Purpose**: Anonymization before LLM processing.

**Key functions**:
- `deterministic_author_uuid()`: Name → UUID
- `detect_pii()`: Scan for sensitive data
- Namespace management for scoped anonymity

### Config (`config/`)

**Purpose**: Pydantic V2 settings management.

**Key classes**:
- `EgregoraConfig`: Root configuration
- Settings for models, RAG, pipeline, paths, etc.
- `ConfigOverrideBuilder`: Programmatic config modification

### Utils (`utils/`)

**Purpose**: Cross-cutting utilities.

**Categories**:
- **Data**: batch, serialization, text
- **I/O**: filesystem, zip, network
- **Observability**: metrics, quota, retry
- **Caching**: disk cache management

## Design Patterns

### Functional Pipeline

All transformations are pure functions:

```python
def transform(data: ibis.Table) -> ibis.Table:
    """Pure function: Table → Table"""
    return data.filter(...).mutate(...)
```

### Protocol-Based

Clean interfaces using Python protocols:

```python
class InputAdapter(Protocol):
    def read_messages(self) -> Iterator[dict[str, Any]]: ...
    def get_metadata(self) -> InputAdapterMetadata: ...
```

### Dependency Injection

Components receive dependencies explicitly:

```python
def run_pipeline(
    adapter: InputAdapter,
    output: OutputAdapter,
    config: EgregoraConfig,
    storage: DuckDBStorageManager,
) -> PipelineResult:
    ...
```

### Registry Pattern

Adapters and views use registries:

```python
from egregora.input_adapters.registry import registry

@registry.register("whatsapp")
class WhatsAppAdapter:
    ...
```

### Context Manager

Resources managed with context managers:

```python
with DuckDBStorageManager() as storage:
    storage.write_table(table, "name")
```

## File Organization

Within a module:

1. **Module docstring**: Purpose and usage
2. **Imports**: stdlib, third-party, local (separated)
3. **Constants**: Module-level constants
4. **Type definitions**: TypeVars, Protocols
5. **Helper functions**: Private (_) helpers
6. **Main public API**: Public functions/classes
7. **Entry point**: `if __name__ == "__main__":` (if applicable)

## Naming Conventions

### Modules
- **Descriptive snake_case**: `file_system.py` not `filesystem.py`
- **Specific over generic**: `duckdb_manager.py` not `storage.py`

### Classes
- **Pydantic configs**: `*Settings` (e.g., `ModelSettings`)
- **Runtime contexts**: `*Context` (e.g., `WriterAgentContext`)
- **Database managers**: `{Technology}{Purpose}` (e.g., `DuckDBStorageManager`)
- **Adapters**: `{Name}Adapter` (e.g., `WhatsAppAdapter`, `MkDocsAdapter`)

### Functions
- **Explicit verbs**: `get_adapter_metadata()` not `adapter_meta()`
- **Descriptive**: `embed_texts_in_batch()` not `embed_batch()`

### Variables
- **Source-agnostic**: `input_file` not `zip_file`
- **Explicit thresholds**: `min_similarity_threshold` not `min_similarity`

## Dependencies

### Core

- **ibis-framework**: DataFrame abstraction
- **duckdb**: Analytics database
- **lancedb**: Vector storage
- **google-genai**: Google Gemini API
- **pydantic-ai**: Type-safe AI agents
- **pydantic**: Data validation
- **typer**: CLI framework
- **rich**: Terminal formatting
- **uv**: Package management

### Optional

- **mkdocs**: Documentation (docs extra)
- **mkdocs-material**: Material theme (docs extra)
- **pytest**: Testing (test extra)
- **ruff**: Linting (lint extra)
- **pre-commit**: Git hooks (lint extra)

## Testing Structure

```
tests/
├── unit/                   # Fast, isolated tests
│   ├── test_privacy.py
│   ├── test_adapters.py
│   ├── rag/
│   └── ...
├── integration/            # Component integration
│   ├── test_pipeline.py
│   └── ...
└── e2e/                    # End-to-end workflows
    └── test_write_workflow.py
```

## Development Workflow

1. **Setup**: `python dev_tools/setup_hooks.py`
2. **Install deps**: `uv sync --all-extras`
3. **Run tests**: `uv run pytest tests/`
4. **Quality checks**: `uv run pre-commit run --all-files`
5. **Build docs**: `uvx mkdocs serve`

## See Also

- [Contributing Guide](contributing.md) - Development workflow
- [Testing Guide](testing.md) - Test organization
- [Architecture Overview](../guide/architecture.md) - High-level architecture
- [API Reference](../api/index.md) - Detailed API docs
