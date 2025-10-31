# Project Structure

Understanding the Egregora codebase organization.

## Repository Layout

```
egregora/
├── src/egregora/           # Main source code
├── tests/                  # Test suite
├── docs/                   # Documentation (MkDocs)
├── .claude/                # Claude Code configuration
├── .github/                # GitHub Actions workflows
├── pyproject.toml          # Project configuration
├── mkdocs.yml              # Documentation configuration
├── README.md               # Project overview
└── LICENSE                 # MIT License
```

## Source Code Structure

```
src/egregora/
├── ingestion/              # Parse WhatsApp exports
│   ├── __init__.py
│   └── parser.py           # Main parsing logic
│
├── privacy/                # Anonymization & PII detection
│   ├── __init__.py
│   ├── anonymizer.py       # Name anonymization
│   └── detector.py         # PII detection
│
├── augmentation/           # Enrichment & profiling
│   ├── __init__.py
│   ├── enrichment/
│   │   ├── __init__.py
│   │   ├── core.py         # Enrichment logic
│   │   ├── media.py        # Media enrichment
│   │   └── batch.py        # Batch processing
│   └── profiler.py         # Author profiles
│
├── knowledge/              # RAG, annotations, rankings
│   ├── __init__.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── store.py        # Vector store
│   │   ├── embedder.py     # Embedding generation
│   │   ├── retriever.py    # Similarity search
│   │   └── chunker.py      # Text chunking
│   ├── annotations.py      # Conversation metadata
│   └── ranking/
│       ├── __init__.py
│       ├── elo.py          # Elo scoring
│       ├── agent.py        # Comparison agent
│       └── store.py        # Rating persistence
│
├── generation/             # LLM writer & editor
│   ├── __init__.py
│   ├── writer/
│   │   ├── __init__.py
│   │   ├── core.py         # Main writer
│   │   ├── tools.py        # Tool definitions
│   │   ├── handlers.py     # Tool handlers
│   │   ├── formatting.py   # Output formatting
│   │   └── context.py      # Context building
│   └── editor/
│       ├── __init__.py
│       ├── agent.py        # Interactive editor
│       └── document.py     # Document handling
│
├── publication/            # Site scaffolding
│   ├── __init__.py
│   └── site/
│       ├── __init__.py
│       └── scaffolding.py  # MkDocs site creation
│
├── core/                   # Shared models & schemas
│   ├── __init__.py
│   ├── schema.py           # Ibis schemas
│   ├── models.py           # Pydantic models
│   ├── types.py            # Type definitions
│   └── database_schema.py  # Database schemas
│
├── orchestration/          # CLI & pipeline
│   ├── __init__.py
│   ├── cli.py              # Typer CLI
│   ├── pipeline.py         # End-to-end orchestration
│   ├── database.py         # Database management
│   ├── serialization.py    # Data serialization
│   ├── logging_setup.py    # Logging configuration
│   └── write_post.py       # Post writing
│
├── config/                 # Configuration management
│   ├── __init__.py
│   ├── model.py            # Model configuration
│   ├── site.py             # Site configuration
│   └── types.py            # Config types
│
├── utils/                  # Utilities
│   ├── __init__.py
│   ├── batch.py            # Batch processing
│   ├── cache.py            # Disk cache
│   ├── checkpoints.py      # Checkpoint management
│   ├── zip.py              # ZIP handling
│   ├── genai.py            # Gemini client utils
│   ├── gemini_dispatcher.py # API dispatcher
│   └── base_dispatcher.py  # Base dispatcher
│
├── testing/                # Testing utilities
│   ├── __init__.py
│   └── gemini_recorder.py  # API recording
│
├── templates/              # Jinja2 templates
│   └── (various .jinja2 files)
│
└── prompts/                # Deprecated prompt templates
    └── (legacy files)
```

## Key Files

### Configuration

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, tool configs |
| `mkdocs.yml` | Documentation configuration |
| `.github/workflows/` | CI/CD pipelines |
| `.claude/` | Claude Code hooks and commands |

### Entry Points

| File | Purpose |
|------|---------|
| `orchestration/cli.py` | Main CLI entry point (`egregora` command) |
| `orchestration/pipeline.py` | Pipeline orchestration |
| `orchestration/write_post.py` | Post generation workflow |

## Module Responsibilities

### Ingestion

**Purpose**: Parse WhatsApp exports into structured DataFrames

**Key functions**:
- `parse_whatsapp_export()`: Main parsing function
- Format detection (iOS vs Android)
- Multi-line message handling

### Privacy

**Purpose**: Protect user privacy before AI processing

**Key functions**:
- `anonymize_dataframe()`: Replace names with UUIDs
- `detect_pii()`: Scan for sensitive information
- `reverse_anonymization()`: Local name restoration

### Augmentation

**Purpose**: Add context using LLMs

**Key functions**:
- `enrich_urls()`: Describe linked content
- `enrich_media()`: Describe media references
- `create_author_profiles()`: Generate bios

### Knowledge

**Purpose**: Persistent indexes and metadata

**Components**:
- **RAG**: Vector embeddings + similarity search
- **Annotations**: Conversation threading and topics
- **Rankings**: Elo-based quality scores

### Generation

**Purpose**: LLM-powered content creation

**Key functions**:
- `generate_posts()`: Main writer with tool calling
- `edit_post()`: Interactive refinement
- Tool definitions for structured output

### Publication

**Purpose**: Create MkDocs sites

**Key functions**:
- `scaffold_site()`: Initialize site structure
- Template rendering
- Post writing to markdown

### Core

**Purpose**: Shared data structures

**Key modules**:
- `schema.py`: Ibis DataFrame schemas
- `models.py`: Pydantic validation models
- `types.py`: Type aliases and enums

### Orchestration

**Purpose**: Coordinate the pipeline

**Key functions**:
- `main()`: CLI entry point
- `run_pipeline()`: End-to-end execution
- Command definitions (process, init, edit, rank)

## Design Patterns

### DataFrame-Centric

All data flows through Ibis DataFrames:

```python
# Parse → DataFrame
df = parse_whatsapp_export("export.zip")

# Transform → DataFrame
df = anonymize_dataframe(df)

# Enrich → DataFrame
df = enrich_urls(df, client)
```

### Lazy Evaluation

Ibis defers computation until needed:

```python
# Build query
df = table.filter(...).select(...).group_by(...)

# Execute when needed
result = df.execute()
```

### Tool Calling

LLMs use structured tools:

```python
def write_post(title: str, content: str, tags: List[str]) -> None:
    """Tool for LLM to write a blog post."""
    ...

# LLM calls the tool
posts = llm.generate_with_tools([write_post])
```

### Caching

Expensive operations are cached:

```python
@cache.memoize()
def embed_text(text: str, client: genai.Client) -> List[float]:
    """Cached embedding generation."""
    ...
```

## Dependencies

### Core Dependencies

- **ibis-framework**: DataFrame API
- **duckdb**: Analytics database
- **google-genai**: Gemini API
- **pydantic**: Data validation
- **typer**: CLI framework
- **rich**: Terminal formatting

### Optional Dependencies

- **mkdocs**: Documentation (docs)
- **pytest**: Testing (test)
- **ruff**: Linting (lint)
- **pre-commit**: Git hooks (lint)

## Development Practices

### Code Organization

- **One module per stage**: Clear separation
- **Flat is better than nested**: Avoid deep hierarchies
- **Explicit imports**: No `import *`
- **Type hints**: Throughout the codebase

### Naming Conventions

- **Functions**: `lowercase_with_underscores`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_CASE_WITH_UNDERSCORES`
- **Private**: `_leading_underscore`

### File Organization

Within a module:

1. Imports (stdlib, third-party, local)
2. Constants
3. Type definitions
4. Helper functions
5. Main public API
6. Entry point (if applicable)

## See Also

- [Contributing Guide](contributing.md) - Development workflow
- [Testing Guide](testing.md) - Test organization
- [API Reference](../api/index.md) - Detailed API docs
