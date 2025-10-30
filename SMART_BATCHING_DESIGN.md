# Smart Batching Design: Intelligent API Call Strategy

## Problem Statement

Current system **always** uses batch API, even for single items:
- **1 embedding request** → 40+ seconds (batch job overhead)
- **2-3 messages** → 40+ seconds (wasteful)
- **100 messages** → 60 seconds (efficient, but still slow polling)

**Reality**:
- Batch API has ~30-60s overhead (job creation + polling)
- Individual API calls take ~1-3s each
- Small batches waste time, large batches are efficient

## Solution: Smart Adaptive Batching

System **automatically chooses** between:
1. **Individual calls** - for small, urgent requests
2. **Batch API** - for large, bulk operations
3. **Hybrid** - mix both strategies

### Decision Matrix

| Items | Strategy | Reasoning | Time Estimate |
|-------|----------|-----------|---------------|
| 1-3 | Individual | Overhead > benefit | ~1-5s |
| 4-9 | Hybrid (optional) | Depends on latency needs | ~5-15s |
| 10+ | Batch | Amortized cost wins | ~40-90s |

## Architecture

### 1. Smart Client Wrapper

```python
class SmartGeminiClient:
    """Intelligent client that chooses between batch and individual calls."""

    def __init__(
        self,
        client: genai.Client,
        default_model: str,
        batch_threshold: int = 10,  # Items needed to trigger batch
        max_individual_parallel: int = 5,  # Max concurrent individual calls
    ):
        self._client = client
        self._batch_client = GeminiBatchClient(client, default_model)
        self._batch_threshold = batch_threshold
        self._max_parallel = max_individual_parallel

    def embed_content(
        self,
        requests: Sequence[EmbeddingRequest],
        *,
        force_batch: bool = False,
        force_individual: bool = False,
    ) -> list[EmbeddingResult]:
        """Smart embedding with automatic strategy selection."""

        # Allow manual override
        if force_batch:
            return self._embed_batch(requests)
        if force_individual:
            return self._embed_individual(requests)

        # Automatic decision
        if len(requests) < self._batch_threshold:
            logger.info(f"Using individual calls for {len(requests)} items")
            return self._embed_individual(requests)
        else:
            logger.info(f"Using batch API for {len(requests)} items")
            return self._embed_batch(requests)

    def _embed_individual(self, requests):
        """Execute requests individually with parallelism."""
        with ThreadPoolExecutor(max_workers=self._max_parallel) as executor:
            futures = [
                executor.submit(self._embed_one, req)
                for req in requests
            ]
            return [f.result() for f in futures]

    def _embed_one(self, request):
        """Single embedding via direct API."""
        response = self._client.models.embed_content(
            model=request.model,
            content=request.text,
            task_type=request.task_type,
            output_dimensionality=request.output_dimensionality,
        )
        return EmbeddingResult(
            tag=request.tag,
            embedding=list(response.embedding.values),
        )

    def _embed_batch(self, requests):
        """Use batch API."""
        return self._batch_client.embed_content(requests)
```

### 2. Configuration

Add to `mkdocs.yml`:

```yaml
plugins:
  - egregora:
      model:
        embedding: models/gemini-embedding-001
      batching:
        # Smart batching settings
        strategy: auto  # auto | batch | individual
        batch_threshold: 10  # Min items to trigger batch
        max_parallel_individual: 5  # Concurrent individual calls
        prefer_individual_for:
          - rag_query  # Single query embeddings
          - quick_enrichment  # < 5 items
```

### 3. Use Cases & Strategy

#### Use Case 1: RAG Query (1 embedding)
```python
# Before: 40s batch overhead for 1 item!
embedding = embed_query(query)  # 40+ seconds 😢

# After: Direct call
embedding = smart_client.embed_content(
    [EmbeddingRequest(text=query, task_type="RETRIEVAL_QUERY")],
    # Auto-detects: 1 item → individual call
)  # 1-2 seconds ✅
```

#### Use Case 2: Few Media Files (3-5 items)
```python
# Before: Batch API with 40s overhead
embeddings = batch_client.embed_content(media_requests)  # 40s

# After: Parallel individual calls
embeddings = smart_client.embed_content(media_requests)
# Auto-detects: 3 items → 3 parallel calls → ~2-3s total ✅
```

#### Use Case 3: Large Post Index (50 chunks)
```python
# Before: Batch API (correct choice)
embeddings = batch_client.embed_content(chunk_requests)  # 60s

# After: Still uses batch (same strategy)
embeddings = smart_client.embed_content(chunk_requests)
# Auto-detects: 50 items → batch API → ~60s ✅
```

### 4. Hybrid Mode (Advanced)

For medium-sized requests (10-30 items), use **hybrid**:

```python
def _embed_hybrid(self, requests):
    """Split into urgent batch + background batch."""

    # Process first 5 individually (quick results)
    urgent = requests[:5]
    remaining = requests[5:]

    # Start both concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        urgent_future = executor.submit(self._embed_individual, urgent)
        batch_future = executor.submit(self._embed_batch, remaining)

        urgent_results = urgent_future.result()  # ~3s
        batch_results = batch_future.result()    # ~40s

    return urgent_results + batch_results
```

## Implementation Plan

### Phase 1: Core Smart Client
- [ ] Create `SmartGeminiClient` class
- [ ] Implement individual embedding calls with `ThreadPoolExecutor`
- [ ] Add automatic threshold detection
- [ ] Add force_batch/force_individual overrides

### Phase 2: Integration
- [ ] Update `embedder.py` to use `SmartGeminiClient`
- [ ] Update `pipeline.py` to instantiate smart client
- [ ] Add configuration to `ModelConfig`
- [ ] Maintain backward compatibility

### Phase 3: Generation Support
- [ ] Extend smart client for `generate_content()`
- [ ] Add streaming support for individual calls
- [ ] Optimize writer to use individual calls for single posts

### Phase 4: Monitoring & Tuning
- [ ] Add metrics (strategy chosen, time saved)
- [ ] Log strategy decisions for analysis
- [ ] Auto-tune threshold based on actual latencies
- [ ] Add `--batching-strategy` CLI flag for override

## Benefits

### Performance Improvements

| Scenario | Before (Batch) | After (Smart) | Improvement |
|----------|---------------|---------------|-------------|
| Single RAG query | 40s | 2s | **20x faster** |
| 3 media enrichments | 45s | 3s | **15x faster** |
| 10 chunk embeddings | 50s | 12s (individual) or 50s (batch) | **4x faster** or same |
| 100 chunk embeddings | 90s | 90s (batch) | Same (correct) |

### Development Experience

- **Faster iteration** during development (small datasets)
- **Faster tests** with mock bypassing strategy
- **Production-ready** scaling for large exports

### Cost Efficiency

- **Batch API**: $0.00002 per 1K tokens (50% discount)
- **Individual API**: $0.00004 per 1K tokens
- **Smart choice**: Use individual when time matters, batch when cost matters

For small requests, **time savings >> cost difference**

## Configuration Examples

### Development (fast, small datasets)
```yaml
batching:
  strategy: individual  # Force individual for speed
  max_parallel_individual: 10
```

### Production (cost-optimized)
```yaml
batching:
  strategy: auto
  batch_threshold: 5  # Lower threshold = more batching
  max_parallel_individual: 3
```

### Aggressive Speed (willing to pay more)
```yaml
batching:
  strategy: individual  # Always individual
  max_parallel_individual: 20  # High parallelism
```

## Migration Path

### Backward Compatible

```python
# Old code still works
batch_client = GeminiBatchClient(client, model)
embeddings = batch_client.embed_content(requests)  # Still batch

# New code gets smart behavior
smart_client = SmartGeminiClient(client, model)
embeddings = smart_client.embed_content(requests)  # Auto-decides
```

### Gradual Rollout

1. Week 1: Add `SmartGeminiClient` (opt-in)
2. Week 2: Update embedder to use smart client
3. Week 3: Monitor production metrics
4. Week 4: Deprecate direct `GeminiBatchClient` usage

## Monitoring & Observability

### Metrics to Track

```python
@dataclass
class BatchingMetrics:
    total_requests: int
    individual_calls: int
    batch_calls: int
    time_saved_estimate: float  # vs always-batch
    cost_delta: float  # vs always-batch

    def log_summary(self):
        logger.info(
            f"Batching stats: {self.individual_calls} individual, "
            f"{self.batch_calls} batch. Saved ~{self.time_saved_estimate:.0f}s"
        )
```

### Log Examples

```
[INFO] Smart batching: 2 items → individual calls (~2s vs 40s batch)
[INFO] Smart batching: 50 items → batch API (efficient)
[INFO] Session summary: 15 individual, 3 batch. Saved ~180s total.
```

## Future Enhancements

### 1. Dynamic Threshold Tuning

```python
class AdaptiveSmartClient(SmartGeminiClient):
    """Auto-tune threshold based on observed latencies."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._latency_history = []

    def _update_threshold(self, strategy, items, latency):
        """Learn from actual performance."""
        self._latency_history.append((strategy, items, latency))

        # Adjust threshold if individual is consistently faster
        if self._should_adjust():
            self._batch_threshold = self._calculate_optimal_threshold()
```

### 2. Request Coalescing

```python
class CoalescingSmartClient(SmartGeminiClient):
    """Automatically combine nearby requests into batches."""

    def __init__(self, *args, coalesce_window=1.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending = []
        self._coalesce_window = coalesce_window

    async def embed_content(self, requests):
        """Wait briefly to collect more requests."""
        self._pending.extend(requests)
        await asyncio.sleep(self._coalesce_window)

        batch = self._pending
        self._pending = []
        return await super().embed_content(batch)
```

### 3. Streaming Support

```python
def generate_content_stream(self, prompt):
    """Stream responses for individual calls."""
    if self._should_use_individual([prompt]):
        # Stream directly
        return self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            stream=True,
        )
    else:
        # Batch doesn't support streaming - fallback
        return self._batch_client.generate_content([prompt])
```

## Success Criteria

- [ ] Single RAG queries complete in <3s (down from 40s)
- [ ] Small enrichments (1-5 items) complete in <5s
- [ ] Large batches (100+ items) still use efficient batch API
- [ ] Zero breaking changes to existing code
- [ ] Clear logging of strategy decisions
- [ ] Cost increase <10% (mostly on small requests)
- [ ] Developer happiness increased significantly

## Related

- **Golden Fixtures** (#feature/golden-test-fixtures) - Testing infrastructure
- **Mock Clients** (tests/mock_batch_client.py) - Fast tests without API
- **Batch API** (src/egregora/utils/batch.py) - Current implementation
