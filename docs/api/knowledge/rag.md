# Retrieval-Augmented Generation (RAG)

The RAG module provides LanceDB-based vector storage and retrieval for enriched content.

## Overview

Egregora's RAG system uses:

- **LanceDB**: Fast vector storage with native filtering
- **Synchronous API**: All operations are synchronous, using thread pools for concurrency
- **Dual-Queue Router**: Intelligent routing between single and batch embedding endpoints
- **Asymmetric Embeddings**: Different task types for documents vs queries

## Quick Start

```python
from egregora.rag import index_documents, search, RAGQueryRequest
from egregora.data_primitives import Document, DocumentType

def example():
    # Index documents
    doc = Document(content="# Post\n\nContent", type=DocumentType.POST)
    index_documents([doc])

    # Search
    request = RAGQueryRequest(text="search query", top_k=5)
    response = search(request)

    for hit in response.hits:
        print(f"{hit.score:.2f}: {hit.text[:50]}")

example()
```

## Configuration

Configure RAG in `.egregora/config.yml`:

```yaml
paths:
  lancedb_dir: .egregora/lancedb

rag:
  enabled: true
  top_k: 5
  min_similarity_threshold: 0.7
  indexable_types: ["POST"]
  embedding_max_batch_size: 100
  embedding_timeout: 60.0
```

## API Reference

### Main Functions

::: egregora.rag.index_documents
    options:
      show_root_heading: true
      heading_level: 3

::: egregora.rag.search
    options:
      show_root_heading: true
      heading_level: 3

### Backend Protocol

::: egregora.rag.backend.VectorStore
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - add
        - query
        - delete

### LanceDB Backend

::: egregora.rag.lancedb_backend.LanceDBRAGBackend
    options:
      show_root_heading: true
      heading_level: 3

## Data Models

### Query Request

::: egregora.rag.models.RAGQueryRequest
    options:
      show_source: true
      show_root_heading: true
      show_category_heading: true
      members_order: source
      heading_level: 3

### Query Response

::: egregora.rag.models.RAGQueryResponse
    options:
      show_source: true
      show_root_heading: true
      show_category_heading: true
      members_order: source
      heading_level: 3

### Retrieval Hit

::: egregora.rag.models.RAGHit
    options:
      show_source: true
      show_root_heading: true
      show_category_heading: true
      members_order: source
      heading_level: 3

## Architecture

### Dual-Queue Embedding Router

The embedding router intelligently routes requests to optimal endpoints using thread pools for concurrency:

- **Single Endpoint**: Low-latency, preferred for queries (1 request/sec)
- **Batch Endpoint**: High-throughput, used for bulk indexing (1000 embeddings/min)

**Features:**

- Independent rate limit tracking per endpoint
- Automatic 429 fallback and retry with exponential backoff
- Request accumulation during rate limits
- Intelligent routing based on request size and endpoint availability

### Asymmetric Embeddings

Google Gemini supports task-specific embeddings:

- **Documents**: `RETRIEVAL_DOCUMENT` task type for indexing
- **Queries**: `RETRIEVAL_QUERY` task type for searching

This improves retrieval quality by using different embedding strategies for documents vs queries.

## Examples

### Basic Indexing

```python
from egregora.rag import index_documents
from egregora.data_primitives import Document, DocumentType

def index_posts():
    docs = [
        Document(
            content="# First Post\n\nContent here",
            type=DocumentType.POST,
            metadata={"category": "tech"}
        ),
        Document(
            content="# Second Post\n\nMore content",
            type=DocumentType.POST,
            metadata={"category": "life"}
        )
    ]

    index_documents(docs)
    print(f"Indexed {len(docs)} documents")

index_posts()
```

### Advanced Search

```python
from egregora.rag import search, RAGQueryRequest

def search_posts():
    # Search with SQL filters
    request = RAGQueryRequest(
        text="machine learning",
        top_k=10,
        filters="metadata_json LIKE '%tech%'",  # SQL WHERE clause
        min_similarity=0.7
    )

    response = search(request)

    print(f"Found {len(response.hits)} results in {response.query_time_ms}ms")
    for hit in response.hits:
        print(f"Score: {hit.score:.3f}")
        print(f"Type: {hit.document_type}")
        print(f"Text: {hit.text[:100]}...")
        print()

search_posts()
```

### Custom Embedding Function

```python
from typing import Sequence
from egregora.rag import index_documents
from egregora.data_primitives import Document, DocumentType

def custom_embed(texts: Sequence[str], task_type: str) -> list[list[float]]:
    """Custom embedding function."""
    # Use your own embedding model
    embeddings = []
    for text in texts:
        # ... your embedding logic ...
        embeddings.append([0.1] * 768)  # Example
    return embeddings

def index_with_custom_embeddings():
    docs = [Document(content="Test", type=DocumentType.POST)]

    # Pass custom embedding function
    index_documents(docs, embedding_fn=custom_embed)

index_with_custom_embeddings()
```

## Performance

### Indexing Performance

- **Small batches (< 10 docs)**: ~100-200ms per document
- **Large batches (100+ docs)**: ~20-50ms per document (batched)
- **Bottleneck**: Embedding API rate limits

### Search Performance

- **Vector search**: < 10ms for 10K documents
- **With filters**: < 50ms for 10K documents
- **Bottleneck**: Query embedding latency (~100ms)

### Optimization Tips

1. **Batch indexing**: Index in large batches (100+ documents)
2. **Configure batch size**: Adjust `embedding_max_batch_size` in config
3. **Use filters**: SQL filters are very fast (pre-filter before vector search)
4. **Adjust top_k**: Lower `top_k` = faster search

## Migration from Legacy RAG

The legacy `egregora.agents.shared.rag.VectorStore` is deprecated. Migrate to `egregora.rag`:

**Before (Legacy):**

```python
from egregora.agents.shared.rag import VectorStore

store = VectorStore(rag_dir / "chunks.parquet", storage=storage)
indexed = store.index_documents(output, embedding_model=model)
results = store.query_media(query, media_types=types)
```

**After (New):**

```python
from egregora.rag import index_documents, search, RAGQueryRequest

def migrate():
    # Index documents
    index_documents(docs)

    # Search
    request = RAGQueryRequest(text=query, top_k=5)
    response = search(request)

migrate()
```

## See Also

- [Architecture Guide](../../guide/architecture.md#rag-retrieval-augmented-generation) - RAG system architecture
- [LanceDB Documentation](https://lancedb.github.io/lancedb/) - Underlying vector database
