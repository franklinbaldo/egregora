# Egregora Reference Manual 📚

This document contains detailed technical reference material for Egregora v3.

## 🛠️ CLI Commands

### Basic Processing
```bash
# Default: 1 day per window, full rebuild
egregora write export.zip --output=./blog

# Custom windowing
egregora write export.zip --step-size=7 --step-unit=days        # Weekly posts
egregora write export.zip --step-size=100 --step-unit=messages  # By message count

# Date filtering
egregora write export.zip --from-date=2025-01-01 --to-date=2025-01-31

# Incremental (resume from last checkpoint)
egregora write export.zip --resume
```

### Reader Agent (Ranking)
The `read` command evaluates and ranks blog posts using the Reader Agent.

```bash
# Evaluate posts in a site
egregora read ./my-blog

# Show top 20 rankings
egregora read ./my-blog --limit 20
```

**Note:** The `read` command requires the path to the **site root** (the directory containing `.egregora/config.yml`), not the posts directory itself. It automatically resolves the posts directory from the configuration.

### Multiple Input Sources
```bash
# WhatsApp (default)
egregora write export.zip --output=./blog

# Self-reflection: Feed past posts back into pipeline
egregora write ./existing-blog --source=self --output=./meta-analysis

# Brazilian judicial API (TJRO)
egregora write config.json --source=iperon-tjro --output=./legal-archive
```

### Selective Cache Invalidation
Egregora uses a tiered caching system to avoid expensive re-computation. You can invalidate specific tiers:

```bash
# Only regenerate posts (keep enrichment + RAG)
egregora write export.zip --refresh=writer

# Rebuild RAG index (keep enrichment + writer cache)
egregora write export.zip --refresh=rag

# Full rebuild (invalidate all caches)
egregora write export.zip --refresh=all
```

---

## ⚙️ Configuration

The default configuration is generated at `.egregora/config.yml`.

```yaml
models:
  # Agents use provider-prefixed IDs (pydantic-ai style)
  writer: google-gla:gemini-2.0-flash
  enricher: google-gla:gemini-2.0-flash

  # API calls use direct Google GenAI IDs
  embedding: models/gemini-embedding-001

rag:
  enabled: true
  top_k: 5

pipeline:
  step_size: 1
  step_unit: days  # "days", "hours", "messages"
```

**Custom Prompts:**
To override the default prompts, place Jinja2 templates in `.egregora/prompts/`.

---

## 📂 Output Structure

When initialized, Egregora creates the following structure (scaffolded by `egregora init`):

```
my-blog/
├── docs/
│   ├── posts/              # Generated posts (YYYY-MM-DD-slug.md)
│   ├── profiles/           # Author profiles with avatars
│   ├── media/              # Enriched media descriptions
│   ├── journal/            # Continuity journals
│   └── index.md            # Home page
├── .egregora/              # Internal data & config
│   ├── config.yml          # Local config
│   ├── runs.duckdb         # Run tracking
│   ├── lancedb/            # Vector embeddings (RAG)
│   ├── mkdocs.yml          # Real MkDocs config
│   └── ...
└── mkdocs.yml              # Symlink to .egregora/mkdocs.yml (for convenience)
```

**Note on `mkdocs.yml`**: Egregora manages the real configuration in `.egregora/mkdocs.yml` to keep the root clean, but creates a symlink at the root so standard tools like `mkdocs serve` work out of the box.

---

## 🏗️ Architecture

Egregora uses a modular architecture designed for performance and flexibility.

### Core Components

1.  **Orchestration:** (`src/egregora/orchestration/`)
    *   Coordinates the flow of data between adapters and transforms.
    *   Manages the pipeline lifecycle and state.

2.  **Transformations:** (`src/egregora/transformations/`)
    *   Data processing modules using Ibis/DuckDB.
    *   Handles windowing, aggregation, and ranking.

3.  **Data Primitives:** (`src/egregora/data_primitives/`)
    *   Core models like `Document` and `Message`.
    *   Defines the protocols for input/output adapters.

### Data Flow

1.  **Ingestion:** Raw data (e.g., WhatsApp ZIP) is parsed into structured tables.
2.  **Privacy:** PII is redacted and authors are anonymized (within the Adapter).
3.  **Enrichment:** Media and links are analyzed by AI agents.
4.  **RAG:** Content is indexed in LanceDB for historical context.
5.  **Generation:** The Writer Agent synthesizes posts using the enriched context.
6.  **Publication:** The final output is written to disk (Markdown, Parquet, etc.).

### Design Principles

*   **Intelligence-First:** We rely on AI for pattern recognition and synthesis.
*   **Functional Purity:** Data transformations are stateless where possible.
*   **Type-Safe:** The codebase is fully typed to prevent runtime errors.
