# Egregora Repository Restructure

## Summary

This restructure applies a **flat, feature-oriented** organization on top of PR #585, with agent tools properly grouped under `agents/tools/`.

### Key Principles

1. **Flat where possible** - Minimize directory nesting
2. **Organize by feature** - Not by architectural pattern
3. **Clear separation** - `ingestion/` for inputs, `rendering/` for outputs
4. **Agent grouping** - All LLM-powered agents under `agents/`
5. **Tool cohesion** - Agent tools (RAG, annotations, profiler) grouped under `agents/tools/`

## New Structure

```
src/egregora/
  # Single entry points
  cli.py                    # All CLI commands (typer app)
  pipeline.py               # Core pipeline logic

  # Core data models (at root)
  schema.py                 # Message schemas
  types.py                  # Type definitions
  models.py                 # Data models
  registry.py               # Input/output format registry
  prompt_templates.py       # Prompt templates

  # Agent behaviors (grouped)
  agents/
    writer/                 # Post generation
    editor/                 # Content editing
    ranking/                # ELO-based ranking
    banner/                 # Banner generation
    tools/                  # Agent tools & utilities
      rag/                  # Retrieval augmented generation
      annotations/          # Conversation annotation storage
      profiler.py           # Author profiling
      shared.py             # Common tool functions
    loader.py               # Agent loading
    registry.py             # Tool registry
    resolver.py             # Agent resolution

  # Core features
  enrichment/               # Content enrichment
  privacy/                  # PII detection & anonymization
  ingestion/                # Input parsers (WhatsApp, Slack)
    base.py                 # InputSource abstraction
    parser.py               # WhatsApp parser
    whatsapp_input.py       # WhatsApp adapter
    slack_input.py          # Slack adapter (template)

  # Infrastructure
  llm/                      # LLM clients (Pydantic AI)
  database/                 # Database & persistence
    schema.py               # Database schemas
    connection.py           # DuckDB connection
    streaming/              # Ibis streaming utilities
  rendering/                # Output rendering
    base.py                 # OutputFormat abstraction
    mkdocs.py               # MkDocs adapter
    hugo.py                 # Hugo adapter (template)
    templates/              # Site templates
  config/                   # Configuration management
  utils/                    # Utilities (paths, cache, batch, etc.)
  init/                     # Project initialization

  # Assets
  prompts/                  # Prompt templates (system, enrichment)
```

## Migration Map

### Flattened Hierarchies

- `core/` → Root files (`schema.py`, `types.py`, `models.py`)
- `core/database_schema.py` → `database/schema.py`
- `generation/writer` → `agents/writer`
- `generation/editor` → `agents/editor`
- `generation/banner` → `agents/banner`
- `knowledge/ranking` → `agents/ranking`
- `knowledge/rag` → **`agents/tools/rag`**
- `knowledge/annotations.py` → **`agents/tools/annotations/`**
- `augmentation/enrichment` → `enrichment/`
- `augmentation/profiler.py` → **`agents/tools/profiler.py`**

### New Organizations

- `orchestration/cli.py` → `cli.py`
- `orchestration/pipeline.py` → `pipeline.py`
- `orchestration/database.py` → `database/connection.py`
- `orchestration/logging_setup.py` → `utils/logging_setup.py`
- `orchestration/serialization.py` → `utils/serialization.py`
- `orchestration/write_post.py` → `utils/write_post.py`
- `streaming/` → `database/streaming/`
- `testing/gemini_recorder.py` → `devtools/gemini_recorder.py`
- `agents/tools.py` → `agents/tools/shared.py`

### PR #585 Abstractions

- `core/input_source.py` → `ingestion/base.py`
- `core/output_format.py` → `rendering/base.py`
- `core/registry.py` → `registry.py`
- `init/mkdocs_output.py` → `rendering/mkdocs.py`
- `init/hugo_output.py` → `rendering/hugo.py`
- `templates/` → `rendering/templates/`

## Import Changes

All imports updated automatically via sed + ruff:

```python
# Before
from egregora.generation.writer import write_posts_for_period
from egregora.knowledge.rag import query_context
from egregora.knowledge.annotations import AnnotationStore
from egregora.augmentation.profiler import get_active_authors
from egregora.orchestration.cli import app

# After
from egregora.agents.writer import write_posts_for_period
from egregora.agents.tools.rag import query_context
from egregora.agents.tools.annotations import AnnotationStore
from egregora.agents.tools.profiler import get_active_authors
from egregora.cli import app
```

## Benefits

1. **Easier navigation** - One-level browsing shows all features
2. **Clear purpose** - Directory names indicate what they do
3. **Symmetric I/O** - `ingestion/` ↔ `rendering/` symmetry
4. **Agent cohesion** - Related LLM behaviors grouped together
5. **Tool organization** - Agent tools properly grouped under `agents/tools/`
6. **Reduced nesting** - Less cognitive overhead

## Compatibility

All absolute imports preserved. Tests updated. No API-breaking changes.
