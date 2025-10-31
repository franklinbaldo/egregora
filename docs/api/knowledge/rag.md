# Knowledge - RAG

Retrieval-Augmented Generation for context-aware content generation.

## Overview

The RAG module provides vector embedding, storage, and retrieval using DuckDB with the VSS extension.

## API Reference

### Store

::: egregora.knowledge.rag.store
    options:
      show_root_heading: true
      show_source: true

### Embedder

::: egregora.knowledge.rag.embedder
    options:
      show_root_heading: true
      show_source: true

### Retriever

::: egregora.knowledge.rag.retriever
    options:
      show_root_heading: true
      show_source: true

### Chunker

::: egregora.knowledge.rag.chunker
    options:
      show_root_heading: true
      show_source: true

## Usage

### Create RAG Store

```python
from egregora.knowledge.rag import create_rag_store

store = create_rag_store(
    db_path="egregora.db",
    embedding_model="models/text-embedding-004",
    dimensions=768
)
```

### Embed and Store

```python
from egregora.knowledge.rag import embed_and_store

# Embed messages and store in vector database
embed_and_store(
    df=messages,
    store=store,
    client=gemini_client,
    batch_size=100
)
```

### Retrieve Context

```python
from egregora.knowledge.rag import retrieve_context

# Retrieve similar past content
context = retrieve_context(
    query="What did we discuss about AI safety?",
    store=store,
    top_k=10,
    nprobe=10  # ANN search quality
)

# Returns list of chunks with scores
for chunk in context:
    print(f"{chunk['score']:.2f}: {chunk['content'][:100]}...")
```

## Chunking Strategies

### Fixed Size

```python
from egregora.knowledge.rag import chunk_messages

chunks = chunk_messages(
    df=messages,
    chunk_size=512,    # tokens
    overlap=50         # token overlap
)
```

### Conversation-Aware

```python
chunks = chunk_messages(
    df=messages,
    chunk_size=512,
    by_conversation=True  # respect thread boundaries
)
```

## Retrieval Modes

### ANN (Approximate Nearest Neighbor)

Fast, scalable, requires VSS extension:

```python
store = create_rag_store(
    db_path="egregora.db",
    retrieval_mode="ann"
)

results = retrieve_context(
    query=query,
    store=store,
    nprobe=10  # Quality parameter (1-100)
)
```

### Exact Search

Slower, no extension required:

```python
store = create_rag_store(
    db_path="egregora.db",
    retrieval_mode="exact"
)

results = retrieve_context(query=query, store=store)
```

## Examples

### Complete RAG Pipeline

```python
from egregora.knowledge.rag import (
    create_rag_store,
    chunk_messages,
    embed_and_store,
    retrieve_context
)

# 1. Create store
store = create_rag_store("egregora.db")

# 2. Chunk messages
chunks = chunk_messages(messages, chunk_size=512)

# 3. Embed and store
embed_and_store(chunks, store, gemini_client)

# 4. Retrieve for generation
context = retrieve_context(
    query="Summarize recent AI discussions",
    store=store,
    top_k=10
)

# 5. Use in prompt
prompt = f"""
Context from past conversations:
{context}

Generate a new post about...
"""
```

### Index Existing Posts

```python
from egregora.knowledge.rag import index_posts

# Index generated blog posts for future retrieval
index_posts(
    posts_dir="docs/posts/",
    store=store,
    client=gemini_client
)
```

## Performance

### Batch Embedding

```python
from egregora.knowledge.rag import embed_batch

# Embed multiple texts at once
texts = [msg.content for msg in messages]
embeddings = embed_batch(
    texts=texts,
    client=gemini_client,
    batch_size=100  # API allows up to 100
)
```

### Caching

```python
from egregora.utils.cache import get_cache

cache = get_cache(".egregora/cache/embeddings/")

# Embeddings are automatically cached by content hash
embedding = cache.get(text_hash) or embed_text(text)
```

## See Also

- [Knowledge - Annotations](annotations.md) - Conversation metadata
- [User Guide - Knowledge Base](../../guide/knowledge.md) - Conceptual overview
- [Generation - Writer](../generation/writer.md) - Using RAG in generation
