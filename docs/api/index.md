# API Reference

Complete API documentation for all Egregora modules.

## Overview

Egregora is organized into functional modules following the staged pipeline architecture:

```
egregora/
├── ingestion/       # Parse WhatsApp exports
├── privacy/         # Anonymization & PII detection
├── augmentation/    # Enrichment & profiling
├── knowledge/       # RAG, annotations, rankings
├── generation/      # LLM writer & editor
├── publication/     # Site scaffolding
├── core/            # Shared models & schemas
├── orchestration/   # CLI & pipeline coordination
├── config/          # Configuration management
└── utils/           # Batch processing, caching
```

## Quick Navigation

### Pipeline Stages

| Module | Description | Key Classes |
|--------|-------------|-------------|
| [Ingestion](ingestion/parser.md) | Parse WhatsApp exports | `parse_whatsapp_export()` |
| [Privacy](privacy/anonymizer.md) | Anonymization | `anonymize_dataframe()`, `detect_pii()` |
| [Augmentation](augmentation/enrichment.md) | Enrich context | `enrich_urls()`, `create_profiles()` |
| [Knowledge](knowledge/rag.md) | RAG & annotations | `RAGStore`, `Annotator` |
| [Generation](generation/writer.md) | Content generation | `Writer`, `Editor` |
| [Publication](publication/scaffolding.md) | Site creation | `scaffold_site()` |

### Core Modules

| Module | Description |
|--------|-------------|
| [Schema](core/schema.md) | Database schemas |
| [Models](core/models.md) | Pydantic models |
| [Types](core/types.md) | Type definitions |

### Orchestration

| Module | Description |
|--------|-------------|
| [Pipeline](orchestration/pipeline.md) | End-to-end workflow |
| [CLI](orchestration/cli.md) | Command-line interface |

## Usage Examples

### Parse WhatsApp Export

```python
from egregora.ingestion import parse_whatsapp_export

df = parse_whatsapp_export("whatsapp-export.zip")
```

### Anonymize Data

```python
from egregora.privacy import anonymize_dataframe

df_anon = anonymize_dataframe(df)
```

### Generate Posts

```python
from egregora.generation import generate_posts
from google import genai

client = genai.Client(api_key="your-key")
posts = generate_posts(df_anon, client, rag_store)
```

### Run Full Pipeline

```python
from egregora.orchestration import run_pipeline

run_pipeline(
    export_path="whatsapp-export.zip",
    output_dir="my-blog/",
    api_key="your-key"
)
```

## Common Patterns

### DataFrame Transformations

All data flows through Ibis DataFrames:

```python
import ibis

# Create connection
conn = ibis.duckdb.connect("egregora.db")

# Load data
df = conn.table("rag_chunks")

# Query
results = df.filter(df.score > 0.8).execute()
```

### Batch Processing

Process large datasets efficiently:

```python
from egregora.utils.batch import batch_process

results = batch_process(
    items=messages,
    func=embed_text,
    batch_size=100
)
```

### Caching

Cache expensive operations:

```python
from egregora.utils.cache import get_cache

cache = get_cache(".egregora/cache/")
result = cache.get("key", default=lambda: expensive_operation())
```

## Type Hints

Egregora uses type hints throughout:

```python
from typing import List
from egregora.core.types import ConversationRow, BlogPost

def process_messages(
    messages: List[ConversationRow]
) -> List[BlogPost]:
    ...
```

## Next Steps

- Browse the module documentation in the sidebar
- See [User Guide](../guide/architecture.md) for conceptual overview
- Check [Development Guide](../development/contributing.md) for contributing
