# Chunked RAG Augmentation

**Status:** ✅ Implemented
**Completed:** Phase 8 (2025-01)
**Tracking:** Commit `d45b62f` - feat: implement chunked RAG augmentation

## Overview

This document describes the **Chunked RAG Augmentation** feature, which enhances the RAG (Retrieval-Augmented Generation) system to provide better context coverage for multi-topic conversations.

### Current Limitation

The current RAG implementation treats the entire conversation window as a single query:

```python
# Current approach (simplified)
def _query_rag_for_context(table: Table, ...):
    query_text = table.execute().to_csv(sep="|", index=False)  # Entire conversation
    query_vec = embed_query_text(query_text, model=embedding_model)
    results = store.search(query_vec, top_k=5)  # Single query
```

**Problem:** When a conversation covers multiple distinct topics, the single embedding "averages" across all topics, potentially missing relevant context for specific sub-topics.

**Example:** A 500-message conversation covering:
- Messages 1-150: Travel to Paris
- Messages 151-300: Debugging a coding issue
- Messages 301-500: Recipe discussions

Current RAG might only retrieve Paris-related posts (dominant theme), missing relevant coding and recipe posts.

## Proposed Solution

### High-Level Architecture

```
Messages Table (after annotations)
    ↓
consolidate_messages_to_markdown(table)
    ↓
chunk_markdown(markdown, max_tokens=1800, overlap=150)
    ↓
FOR EACH chunk:
    embed_query_text(chunk) → query vector
    store.search(query_vector, top_k=5) → results
    ↓
COLLECT all results → [(chunk_text, similarity, document_id, ...)]
    ↓
deduplicate_by_document(results, n=1)  # Keep top-1 per document
    ↓
sort_by_similarity() → top-5 overall
    ↓
format_as_context() → "## Related Previous Posts..."
```

### Key Design Decisions

#### 1. **Chunk Alignment with Storage**

Use the same chunking strategy as RAG storage (`chunk_markdown()` from `rag/chunker.py`):
- **Paragraph boundaries:** Split on `\n\n`
- **Max tokens:** 1800 (safe under Gemini's 2048 limit)
- **Overlap:** 150 tokens between consecutive chunks

**Rationale:** Semantic alignment between query chunks and storage chunks improves retrieval quality.

#### 2. **Document-Level Deduplication (n=1)**

After collecting results from all chunk queries, deduplicate to keep only the **highest-scoring chunk per document**.

**Example:**
```
Query chunk 1 → "Post-123 chunk 0" (similarity: 0.90)
Query chunk 2 → "Post-123 chunk 1" (similarity: 0.85)
Query chunk 3 → "Post-456 chunk 0" (similarity: 0.88)

After dedup (n=1):
→ "Post-123 chunk 0" (0.90) - kept (highest for Post-123)
→ "Post-456 chunk 0" (0.88) - kept (highest for Post-456)
```

**Rationale:** Avoids redundancy while ensuring diverse document coverage. Each retrieved document provides unique context.

#### 3. **Top-5 Final Results**

After deduplication, sort by similarity and return top-5 chunks overall.

**Rationale:** Balances context richness with prompt length constraints.

## Implementation Plan

### Phase 1: Core Functions

#### 1.1 Message Consolidation

**File:** `src/egregora/agents/writer/context_builder.py`

```python
def consolidate_messages_to_markdown(table: Table) -> str:
    """Convert conversation table to markdown string for chunking.

    Format:
        ## Message 1
        **Author:** uuid-123
        **Timestamp:** 2025-01-15 10:30

        Message text here...

        ## Message 2
        **Author:** uuid-456
        **Timestamp:** 2025-01-15 10:35

        Another message...

    Args:
        table: Conversation table with columns (timestamp, author, message, ...).
            The helper expects a pyarrow.Table or iterable of mapping rows.
            Pandas DataFrames are intentionally unsupported to keep the
            formatting path Arrow/Ibis-native.

    Returns:
        Markdown-formatted string suitable for chunk_markdown()
    """
```

**Rationale:** Markdown format with paragraph breaks works well with existing paragraph-based chunker.

#### 1.2 Batch RAG Query

**File:** `src/egregora/agents/writer/context_builder.py`

```python
def query_rag_per_chunk(
    chunks: list[str],
    store: VectorStore,
    embedding_model: str,
    top_k: int = 5,
    min_similarity_threshold: float = 0.7,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
) -> list[dict]:
    """Query RAG for each chunk and collect all results.

    Args:
        chunks: List of text chunks from chunk_markdown()
        store: VectorStore instance
        embedding_model: Embedding model name (e.g., "google-gla:gemini-embedding-001")
        top_k: Number of results per chunk query
        min_similarity_threshold: Minimum cosine similarity (0-1)
        retrieval_mode: "ann" (approximate) or "exact" (brute-force)
        retrieval_nprobe: ANN nprobe parameter (IVF index)
        retrieval_overfetch: Candidate multiplier for ANN

    Returns:
        List of result dicts with keys:
            - content: chunk text
            - similarity: cosine similarity score
            - document_id: unique document identifier
            - post_slug: post slug (if post document)
            - post_title: post title
            - chunk_index: chunk index within document
            - metadata: additional metadata
    """
    all_results = []

    for i, chunk in enumerate(chunks):
        logger.debug("Querying RAG for chunk %d/%d", i + 1, len(chunks))
        query_vec = embed_query_text(chunk, model=embedding_model)
        results = store.search(
            query_vec=query_vec,
            top_k=top_k,
            min_similarity_threshold=min_similarity_threshold,
            mode=retrieval_mode,
            nprobe=retrieval_nprobe,
            overfetch=retrieval_overfetch,
        )

        # Convert Ibis table to dict records
        df = results.execute()
        chunk_results = df.to_dict('records')
        all_results.extend(chunk_results)

    logger.info(
        "Collected %d total results from %d chunks",
        len(all_results),
        len(chunks)
    )
    return all_results
```

#### 1.3 Document-Level Deduplication

**File:** `src/egregora/agents/writer/context_builder.py`

```python
def deduplicate_by_document(results: list[dict], n: int = 1) -> list[dict]:
    """Keep top-n chunks per document_id, ranked by similarity.

    Args:
        results: List of result dicts with 'document_id' and 'similarity' keys
        n: Number of chunks to keep per document (default: 1)

    Returns:
        Deduplicated list of results

    Example:
        >>> results = [
        ...     {'document_id': 'post-123', 'similarity': 0.90, ...},
        ...     {'document_id': 'post-123', 'similarity': 0.85, ...},
        ...     {'document_id': 'post-456', 'similarity': 0.88, ...},
        ... ]
        >>> deduplicate_by_document(results, n=1)
        [
            {'document_id': 'post-123', 'similarity': 0.90, ...},
            {'document_id': 'post-456', 'similarity': 0.88, ...}
        ]
    """
    from collections import defaultdict

    # Group by document_id
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        doc_id = result.get('document_id')
        if doc_id:
            by_doc[doc_id].append(result)

    # Keep top-n per document
    deduplicated = []
    for doc_id, doc_results in by_doc.items():
        # Sort by similarity (descending)
        sorted_results = sorted(
            doc_results,
            key=lambda x: x.get('similarity', 0.0),
            reverse=True
        )
        deduplicated.extend(sorted_results[:n])

    logger.debug(
        "Deduplication: %d results → %d unique documents (n=%d per doc)",
        len(results),
        len(deduplicated),
        n
    )

    return deduplicated
```

### Phase 2: Integration

#### 2.1 Replace `_query_rag_for_context()`

**File:** `src/egregora/agents/writer/context_builder.py`

```python
def _query_rag_for_context(
    table: Table,
    client: genai.Client,
    rag_dir: Path,
    *,
    embedding_model: str,
    retrieval_mode: str = "ann",
    retrieval_nprobe: int | None = None,
    retrieval_overfetch: int | None = None,
    return_records: bool = False,
) -> Result[RagContext, str] | tuple[str, list[dict[str, Any]]]:
    """Query RAG using chunked conversation approach.

    NEW IMPLEMENTATION (Phase 8):
    1. Consolidate messages to markdown
    2. Chunk markdown (paragraph boundaries, 1800 tokens, 150 overlap)
    3. Query RAG for each chunk (top-5 per chunk)
    4. Deduplicate: keep top-1 chunk per document
    5. Sort by similarity and return top-5 overall

    This provides better topic coverage for multi-topic conversations
    compared to the old single-query approach.
    """
    try:
        store = VectorStore(rag_dir / "chunks.parquet")

        # Step 1: Consolidate to markdown
        markdown = consolidate_messages_to_markdown(table)
        if not markdown.strip():
            logger.info("No messages to consolidate for RAG query")
            if return_records:
                return ("", [])
            return Failure(RagErrorReason.NO_HITS)

        # Step 2: Chunk markdown (reuse existing chunker)
        from egregora.agents.shared.rag.chunker import chunk_markdown

        chunks = chunk_markdown(markdown, max_tokens=1800, overlap_tokens=150)
        logger.info(
            "Chunked conversation into %d chunks for RAG query",
            len(chunks)
        )

        # Step 3: Query RAG for each chunk
        all_results = query_rag_per_chunk(
            chunks=chunks,
            store=store,
            embedding_model=embedding_model,
            top_k=5,
            min_similarity_threshold=0.7,
            retrieval_mode=retrieval_mode,
            retrieval_nprobe=retrieval_nprobe,
            retrieval_overfetch=retrieval_overfetch,
        )

        if not all_results:
            logger.info("No similar posts found (0 results from all chunks)")
            if return_records:
                return ("", [])
            return Failure(RagErrorReason.NO_HITS)

        # Step 4: Deduplicate (keep top-1 per document)
        deduped = deduplicate_by_document(all_results, n=1)

        # Step 5: Sort by similarity and take top-5
        final_results = sorted(
            deduped,
            key=lambda x: x.get('similarity', 0.0),
            reverse=True
        )[:5]

        logger.info(
            "RAG query complete: %d chunks → %d results → %d deduped → %d final",
            len(chunks),
            len(all_results),
            len(deduped),
            len(final_results)
        )

        # Step 6: Format context (reuse existing formatting logic)
        rag_text = "\n\n## Related Previous Posts (for continuity and linking):\n"
        rag_text += "You can reference these posts in your writing to maintain conversation continuity.\n\n"

        for row in final_results:
            rag_text += f"### [{row['post_title']}] ({row['post_date']})\n"
            rag_text += f"{row['content'][:400]}...\n"
            rag_text += f"- Tags: {(', '.join(row['tags']) if row.get('tags') else 'none')}\n"
            rag_text += f"- Similarity: {row['similarity']:.2f}\n\n"

        if return_records:
            return (rag_text, final_results)
        return Success(RagContext(text=rag_text, records=final_results))

    except Exception as e:
        logger.error("RAG query failed: %s", e, exc_info=True)
        if return_records:
            return ("", [])
        return Failure(RagErrorReason.SYSTEM_ERROR)
```

### Phase 3: Testing

#### 3.1 Unit Tests

**File:** `tests/unit/writer/test_context_builder_chunked.py`

```python
def test_consolidate_messages_to_markdown():
    """Test message consolidation to markdown format."""
    table = ibis.memtable([
        {'timestamp': '2025-01-15 10:30', 'author': 'uuid-123', 'message': 'Hello world'},
        {'timestamp': '2025-01-15 10:35', 'author': 'uuid-456', 'message': 'Hi there'},
    ])

    markdown = consolidate_messages_to_markdown(table)

    assert '## Message 1' in markdown
    assert 'uuid-123' in markdown
    assert 'Hello world' in markdown
    assert '## Message 2' in markdown


def test_deduplicate_by_document():
    """Test document-level deduplication keeps top-1 per document."""
    results = [
        {'document_id': 'post-123', 'similarity': 0.90, 'content': 'chunk 0'},
        {'document_id': 'post-123', 'similarity': 0.85, 'content': 'chunk 1'},
        {'document_id': 'post-456', 'similarity': 0.88, 'content': 'chunk 0'},
        {'document_id': 'post-456', 'similarity': 0.82, 'content': 'chunk 1'},
    ]

    deduped = deduplicate_by_document(results, n=1)

    assert len(deduped) == 2
    assert deduped[0]['document_id'] == 'post-123'
    assert deduped[0]['similarity'] == 0.90
    assert deduped[1]['document_id'] == 'post-456'
    assert deduped[1]['similarity'] == 0.88


def test_deduplicate_by_document_with_n_2():
    """Test deduplication with n=2 keeps top-2 per document."""
    results = [
        {'document_id': 'post-123', 'similarity': 0.90, 'content': 'chunk 0'},
        {'document_id': 'post-123', 'similarity': 0.85, 'content': 'chunk 1'},
        {'document_id': 'post-123', 'similarity': 0.80, 'content': 'chunk 2'},
    ]

    deduped = deduplicate_by_document(results, n=2)

    assert len(deduped) == 2
    assert deduped[0]['similarity'] == 0.90
    assert deduped[1]['similarity'] == 0.85
```

#### 3.2 Integration Tests

**File:** `tests/integration/test_rag_chunked.py`

```python
@pytest.mark.vcr()
def test_chunked_rag_query_multi_topic(tmp_path):
    """Test chunked RAG with multi-topic conversation."""
    # Create conversation with 3 distinct topics
    table = ibis.memtable([
        # Topic 1: Travel (messages 0-9)
        *[{'message': f'Paris trip day {i}', 'author': 'uuid-1', 'timestamp': f'2025-01-15 10:{i:02d}'}
          for i in range(10)],
        # Topic 2: Coding (messages 10-19)
        *[{'message': f'Debugging issue {i}', 'author': 'uuid-2', 'timestamp': f'2025-01-15 11:{i:02d}'}
          for i in range(10)],
        # Topic 3: Recipes (messages 20-29)
        *[{'message': f'Recipe idea {i}', 'author': 'uuid-3', 'timestamp': f'2025-01-15 12:{i:02d}'}
          for i in range(10)],
    ])

    # Setup RAG store with indexed posts
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    # ... index posts about travel, coding, and recipes ...

    # Query using chunked approach
    result = _query_rag_for_context(
        table=table,
        client=get_test_client(),
        rag_dir=rag_dir,
        embedding_model="google-gla:gemini-embedding-001",
    )

    assert isinstance(result, Success)
    context = result.unwrap()

    # Should retrieve posts covering all 3 topics
    assert 'travel' in context.text.lower() or 'paris' in context.text.lower()
    assert 'coding' in context.text.lower() or 'debug' in context.text.lower()
    assert 'recipe' in context.text.lower()
```

#### 3.3 E2E Test

Run full pipeline with real multi-topic conversation and verify writer gets better context coverage.

## Benefits

### 1. Better Topic Coverage

Multi-topic conversations retrieve relevant context for each sub-topic, not just the dominant theme.

### 2. Semantic Alignment

Query chunks match storage chunks (same chunking strategy), improving retrieval quality.

### 3. Scalability

Chunking keeps each query bounded, avoiding token limits and noisy embeddings for very large windows.

### 4. Diversity

Document-level deduplication (n=1) ensures diverse context without redundancy.

## Costs

### 1. Embedding API Calls

**Before:** 1 embedding per conversation window
**After:** N embeddings per conversation window (where N = number of chunks)

**Example:** 500-message window → ~5-10 chunks → 5-10× embedding cost

**Mitigation:** Cost acceptable per project requirements. Can be parallelized for speed.

### 2. Search Complexity

**Before:** 1 search query
**After:** N search queries

**Mitigation:** DuckDB VSS searches are fast (<100ms each). Total latency remains acceptable.

## Configuration

Add to `config/settings.py`:

```python
@dataclass
class RAGSettings:
    """RAG configuration."""

    enabled: bool = True
    top_k: int = 5
    mode: str = "ann"  # "ann" or "exact"
    nprobe: int | None = None
    overfetch: int | None = None

    # NEW (Phase 8): Chunked RAG settings
    chunks_per_query: int = 5  # top-k per chunk query
    dedup_strategy: str = "document"  # "document" or "none"
    dedup_max_per_doc: int = 1  # chunks to keep per document
```

Add to `.egregora/config.yml`:

```yaml
rag:
  enabled: true
  top_k: 5
  mode: ann
  chunks_per_query: 5
  dedup_strategy: document
  dedup_max_per_doc: 1
```

## Migration

### Backward Compatibility

- Same interface as existing `_query_rag_for_context()`
- Existing RAG stores work without changes
- No data migration required

### Observability

Log metrics for monitoring:
- Number of chunks created
- Number of results per chunk
- Deduplication stats (before/after counts)
- Final result count

**Example log output:**
```
INFO: Chunked conversation into 7 chunks for RAG query
INFO: Collected 35 total results from 7 chunks
DEBUG: Deduplication: 35 results → 12 unique documents (n=1 per doc)
INFO: RAG query complete: 7 chunks → 35 results → 12 deduped → 5 final
```

## Future Enhancements

### 1. Hybrid Approach

Combine whole-conversation query with chunked queries:
- Global context: "Overall conversation theme"
- Detailed context: "Specific sub-topic context"

### 2. Adaptive Chunking

Use different chunk sizes based on window size:
- Small windows (<100 messages): Single query
- Large windows (>100 messages): Chunked approach

### 3. MMR (Maximal Marginal Relevance)

Add diversity scoring to balance relevance vs. diversity:
```
score = λ × sim(chunk, query) - (1-λ) × max_sim(chunk, selected_chunks)
```

### 4. Semantic Deduplication

Use embedding similarity instead of document-level dedup for finer-grained control.

## References

- RAG chunking: `src/egregora/agents/shared/rag/chunker.py`
- Current RAG query: `src/egregora/agents/writer/context_builder.py:_query_rag_for_context()`
- Vector store: `src/egregora/agents/shared/rag/store.py`
- Knowledge guide: `docs/guide/knowledge.md`
