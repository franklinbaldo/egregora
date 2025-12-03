# RAG (Retrieval-Augmented Generation) API

The RAG module provides vector-based document retrieval using LanceDB for fast similarity search.

## Overview

Egregora's RAG system enables the writer agent to search through past content for relevant context. It uses:

- **LanceDB** for vector storage and similarity search
- **Google Gemini embeddings** (`models/gemini-embedding-001`)
- **Dual-queue embedding router** for optimal API quota utilization
- **Async architecture** for efficient I/O

## Configuration

Configure RAG in `.egregora/config.yml`:

```yaml
rag:
  enabled: true                     # Enable RAG for writer agent
  top_k: 5                          # Number of results to retrieve
  min_similarity_threshold: 0.7     # Minimum similarity score (0.0-1.0)
  indexable_types: ["POST"]         # Document types to index

  # Embedding router settings
  embedding_max_batch_size: 100     # Max texts per batch request
  embedding_timeout: 60.0           # Request timeout (seconds)
  embedding_max_retries: 5          # Max retries on error

paths:
  lancedb_dir: .egregora/lancedb    # Vector database location
```

## Data Models

See [RAG Data Models](models.md)

## Usage Examples

### Basic Search

```python
import asyncio
from egregora.rag import index_documents, search
from egregora.rag.models import RAGQueryRequest
from egregora.data_primitives.document import Document, DocumentType

# Index documents
async def index_docs():
    doc = Document(
        content="# Python Async\n\nGuide to async programming...",
        type=DocumentType.POST,
        metadata={"title": "Async Programming"}
    )
    await index_documents([doc])

asyncio.run(index_docs())

# Search
async def search_docs():
    request = RAGQueryRequest(
        text="async programming best practices",
        top_k=5
    )
    response = await search(request)

    for hit in response.hits:
        print(f"Score: {hit.score:.2f}")
        print(f"Text: {hit.text[:100]}...")
        print()

asyncio.run(search_docs())
```

### Search with Filters

```python
# Search with SQL filtering
request = RAGQueryRequest(
    text="machine learning",
    top_k=10,
    filters="metadata_json LIKE '%python%'"
)
response = await search(request)
```

### Custom Embedding Function

```python
from egregora.rag import index_documents

async def custom_embed(texts: list[str], task_type: str) -> list[list[float]]:
    """Custom embedding function."""
    # Your embedding logic here
    return embeddings

# Index with custom embeddings
await index_documents(
    documents=[doc1, doc2],
    embedding_fn=custom_embed
)
```

## Backend

### RAGBackend Protocol

::: egregora.rag.backend.RAGBackend
    options:
      show_source: true
      show_root_heading: true
      show_category_heading: true
      members_order: source
      heading_level: 4

### LanceDB Implementation

::: egregora.rag.lancedb_backend.LanceDBRAGBackend
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

## Embedding Router

The dual-queue embedding router optimizes API quota utilization:

- **Single endpoint**: Low-latency, preferred for queries (1 request/sec)
- **Batch endpoint**: High-throughput, used for bulk indexing (1000 embeddings/min)
- **Automatic fallback**: Falls back between endpoints on 429 errors
- **Request batching**: Reduces API calls by up to 100x

::: egregora.rag.embedding_router
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

## Performance Tips

1. **Batch indexing**: Index documents in batches for better throughput
2. **Top-K selection**: Use 5-10 for best performance/relevance tradeoff
3. **Filters**: Apply SQL filters to narrow search space
4. **Similarity threshold**: Set to 0.7+ to filter low-relevance results
5. **Async usage**: Always use `await` - don't block the event loop

## Architecture

```
┌─────────────────┐
│  Writer Agent   │
└────────┬────────┘
         │ RAGQueryRequest
         ▼
┌─────────────────┐
│  RAG Backend    │  ← Protocol-based (swappable)
│   (LanceDB)     │
└────────┬────────┘
         │
    ┌────┴─────┬──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌──────────┐
│ Vector │ │ Embed  │ │ Chunking │
│ Search │ │ Router │ │ Logic    │
└────────┘ └────────┘ └──────────┘
```

## See Also

- [Chunked RAG Augmentation](../features/chunked-rag-augmentation.md)
- [Configuration Reference](../configuration.md)
- [Writer Agent](../features/writer.md)
