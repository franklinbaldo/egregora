# Egregora V3 Infrastructure Guide

> **🏗️ Architecture Reference**
>
> This guide details the infrastructure components implemented in V3 Phase 2, focusing on Input Adapters and Repositories.

---

## Input Adapters

Input adapters normalize external data sources into the canonical `Entry` format (Atom-compliant). They are responsible for ingestion and normalization, but not enrichment or privacy filtering (which are pipeline steps).

### RSSAdapter

The `RSSAdapter` parses RSS 1.0, RSS 2.0, and Atom feeds using `feedparser`.

**Features:**
- **Universal Parsing:** Handles all major feed formats.
- **Robustness:** Gracefully handles missing fields, encoding issues, and date normalization.
- **Identity:** Generates deterministic IDs (UUIDv5) if the feed is missing standard IDs.
- **Timezone Safety:** All timestamps are converted to UTC (`datetime(tzinfo=UTC)`).

**Usage:**

```python
from pathlib import Path
from egregora_v3.infra.adapters.rss import RSSAdapter

adapter = RSSAdapter()

# Parse a URL
for entry in adapter.parse("https://example.com/feed.xml"):
    print(f"[{entry.updated}] {entry.title}")

# Parse a local file
for entry in adapter.parse(Path("feed.xml")):
    print(entry.title)
```

---

## Document Repository

The `DuckDBDocumentRepository` provides persistence for `Entry` (raw input) and `Document` (processed output) objects.

### DuckDBDocumentRepository

A SQL-based repository using DuckDB as the engine. It uses a single database file (or in-memory) with two main tables:
1. `entries`: Stores raw inputs.
2. `documents`: Stores processed artifacts (Posts, Media, etc.).

**Schema Strategy:**
- **Hybrid Schema:** Core Atom fields (`id`, `title`, `updated`, `content`) are first-class columns for fast SQL querying.
- **JSON Storage:** Complex nested structures (`links`, `authors`, `extensions`) are stored as JSON blobs to avoid complex joins.
- **Raw Dump:** The full Pydantic model is also stored as `raw_json` to ensure perfect object reconstruction (round-tripping) without data loss.

**Usage:**

```python
from egregora_v3.infra.repository.duckdb import DuckDBDocumentRepository
from egregora_v3.core.types import Document, DocumentType

# Initialize (creates tables automatically)
repo = DuckDBDocumentRepository("pipeline.duckdb")

# Save a document
doc = Document.create(
    content="Hello World",
    doc_type=DocumentType.POST,
    title="My First Post"
)
repo.save(doc)

# Retrieve
loaded = repo.get(doc.id)

# List with filtering
posts = repo.list(doc_type=DocumentType.POST)
```

---

## Pipeline Context

The `PipelineContext` manages request-scoped state for the execution of a pipeline run. It is designed to be injected into Pydantic AI agents.

**Fields:**
- `run_id` (UUID): Unique identifier for the execution.
- `config` (EgregoraConfig): Configuration for the run.
- `dry_run` (bool): Flag to skip side-effecting operations.

**Usage:**

```python
from egregora_v3.core.pipeline import PipelineContext
from egregora_v3.core.config import EgregoraConfig

ctx = PipelineContext(
    config=EgregoraConfig.load(),
    dry_run=True
)
```
