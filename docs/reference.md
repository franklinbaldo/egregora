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
  writer: google-gla:gemini-flash-latest
  enricher: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001

rag:
  enabled: true
  top_k: 5
  mode: ann  # "ann" (fast) or "exact" (no VSS extension required)

pipeline:
  step_size: 1
  step_unit: days  # "days", "hours", "messages"
```

**Custom Prompts:**
To override the default prompts, place Jinja2 templates in `.egregora/prompts/`.

---

## 📂 Output Structure

```
my-blog/
├── docs/
│   ├── posts/              # Generated posts (YYYY-MM-DD-slug.md)
│   ├── profiles/           # Author profiles with avatars
│   ├── media/              # Enriched media descriptions
│   ├── journal/            # Continuity journals
│   └── index.md            # Home page
├── .egregora/
│   ├── config.yml          # Local config
│   ├── runs.duckdb         # Run tracking
│   ├── rag.duckdb          # Vector embeddings (L2 cache)
│   ├── enrichment.duckdb   # Asset metadata (L1 cache)
│   ├── writer_cache.duckdb # Generated posts (L3 cache)
│   └── checkpoint.json     # Resume state
└── mkdocs.yml              # Site config
```

---

## 🏗️ Architecture

### Three-Layer Functional Architecture

1.  **Layer 3: Orchestration** (`src/egregora/orchestration/`)
    *   High-level workflows.
    *   Coordinates the flow of data between adapters and transforms.

2.  **Layer 2: Transformations** (`src/egregora/transformations/`)
    *   Pure functional transforms (`Table -> Table`).
    *   Includes windowing, aggregation, and ranking.

3.  **Layer 1: Data Primitives** (`src/egregora/data_primitives/`)
    *   Foundation models (`Document`, `Message`).
    *   Protocols and interfaces.

### Design Principles

*   **Intelligence-First:** Pattern recognition > manual configuration.
*   **Functional Purity:** Transforms are stateless where possible.
*   **Type-Safe:** 100% type coverage with Pydantic and MyPy.
