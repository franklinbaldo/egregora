# CLAUDE.md

Developer guidance for Claude Code when working with this repository.

## Overview

**Egregora** is a privacy-first AI pipeline that extracts structured knowledge from unstructured communication. It runs locally, transforming chat exports into a static blog using LLMs.

- **Repository:** https://github.com/franklinbaldo/egregora
- **Stack:** Python 3.12+ | uv | Ibis | DuckDB | LanceDB | Pydantic-AI
- **Core Goal:** Transform chaotic chat logs into structured, readable knowledge.

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

## Architecture

### Pipeline Flow

```
Ingestion → Privacy → Enrichment → Generation → Publication
  ↓           ↓           ↓            ↓            ↓
Parse ZIP   UUIDs      LLM ctx      Posts       MkDocs
```

### Data Processing

*   **High-Performance Data Handling:** We use **Ibis** and **DuckDB** to process large chat exports efficiently. Transformations are written as pure functions (`Table -> Table`) to handle data without loading it all into Python memory.
*   **Privacy & Safety:** Data is anonymized (UUIDs) and PII is redacted before it hits the LLM. This is handled in the `privacy/` module.
*   **RAG (Retrieval-Augmented Generation):** We use **LanceDB** for vector storage to provide historical context to the Writer agent.

### Code Structure

```
src/egregora/
├── cli/                      # Typer commands
├── orchestration/            # High-level workflows
├── transformations/          # Pure functional transforms (Ibis)
├── input_adapters/           # Data ingestion (WhatsApp, etc.)
├── output_adapters/          # Data persistence (MkDocs, Parquet)
├── database/                 # Storage management (DuckDB, SQL)
├── rag/                      # Vector search (LanceDB)
├── data_primitives/          # Core models (Document, etc.)
├── agents/                   # Pydantic-AI agent logic
│   ├── writer.py             # Post generation
│   ├── enricher.py           # Media/URL analysis
│   ├── reader/               # Quality ranking (ELO)
│   └── banner/               # Image generation
├── privacy/                  # Anonymization logic
├── config/                   # Settings (Pydantic)
└── utils/                    # Shared utilities
```

### URL Convention vs Output Adapter

We separate logical URL generation from filesystem storage:
*   **UrlConvention:** Pure string logic. Determines the canonical URL for a document.
*   **OutputAdapter:** Filesystem logic. Handles writing files to disk (e.g., `docs/posts/slug.md`).

## Design Principles

✅ **Privacy & Safety:** Built-in safeguards to protect user data. Privacy is configurable but enabled by default for sensitive operations.
✅ **Performance:** Ibis expressions over Pandas/Python loops for large data.
✅ **Functional Core:** Transformations should be side-effect free where possible.
✅ **Type Safety:** 100% type coverage with Pydantic and MyPy.
✅ **Evolution:** We prioritize clean code and improvement over strict backward compatibility for internal APIs.

## Agents

1.  **Writer** (`agents/writer.py`): Generates blog posts. Uses RAG for context and profiles for style matching.
2.  **Enricher** (`agents/enricher.py`): Analyzes links and media to provide context.
3.  **Reader** (`agents/reader/`): Ranks posts using an ELO system to identify high-quality content.
4.  **Banner** (`agents/banner/`): Generates cover images using Gemini Imagen.

## Development Workflow

### Making Changes
1.  **Identify the Layer:** Is this orchestration, logic (agent), or data transformation?
2.  **Test First:** Write tests in `tests/`. Use `pytest-vcr` for API interactions.
3.  **Run Checks:** `uv run pre-commit run --all-files` is mandatory.

### Key Patterns

**LanceDB RAG Backend:**
```python
from egregora.rag.lancedb_backend import LanceDBRAGBackend
# Backend handles vector indexing and search using LanceDB
```

**Pydantic-AI Agents:**
Agents use dependency injection for tools and resources.
```python
class WriterDeps:
    resources: WriterResources
    # ...
```

**Configuration:**
Always load config via `egregora.config.settings.load_egregora_config`. Do not use environment variables for app settings (only API keys).

## Known Issues

*   **Sync/Async:** The core pipeline is synchronous (using `ThreadPoolExecutor` for parallelism). `writer.py` uses `asyncio.run` internally for the agent but exposes a blocking API.
*   **RAG Backend:** Fully migrated to LanceDB. Legacy DuckDB VSS code has been removed/deprecated.
