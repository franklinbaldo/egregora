# Implementation Plan - De-async Refactor

## Goal Description
Refactor the entire codebase to remove `asyncio` usage and replace it with synchronous code. This aims to simplify debugging and remove complexity related to event loop management. Concurrency for I/O-bound tasks (enrichment, embeddings) will be handled via `concurrent.futures.ThreadPoolExecutor`.

## User Review Required
> [!IMPORTANT]
> This is a major architectural change. All async entry points will become blocking.
> - **Performance**: Parallelism will be thread-based instead of coroutine-based. This is generally fine for I/O bound tasks but has higher overhead per "task".
> - **APIs**: Internal APIs will change from `async def` to `def`.

## Proposed Changes

### RAG Layer
#### [MODIFY] [backend.py](file:///home/frank/workspace/egregora/src/egregora/rag/backend.py)
- Remove `async` from `RAGBackend` protocol methods (`index_documents`, `query`).

#### [MODIFY] [lancedb_backend.py](file:///home/frank/workspace/egregora/src/egregora/rag/lancedb_backend.py)
- Convert `LanceDBRAGBackend` methods to synchronous.
- Use synchronous `lancedb` API (if available) or wrap async calls if strictly necessary (but LanceDB has sync API).

#### [MODIFY] [embeddings.py](file:///home/frank/workspace/egregora/src/egregora/rag/embeddings.py)
- Ensure `EmbeddingGenerator` protocol and implementations are synchronous.

#### [DELETE] [embeddings_async.py](file:///home/frank/workspace/egregora/src/egregora/rag/embeddings_async.py)
- Remove this file as it's no longer needed.

#### [MODIFY] [embedding_router.py](file:///home/frank/workspace/egregora/src/egregora/rag/embedding_router.py)
- Convert `EmbeddingRouter` to use `ThreadPoolExecutor` for parallel embedding generation instead of `asyncio.gather`.

### Orchestration
#### [MODIFY] [workers.py](file:///home/frank/workspace/egregora/src/egregora/orchestration/workers.py)
- Convert `EnrichmentWorker` and `BannerWorker` to use `ThreadPoolExecutor` for parallel processing.
- Remove `asyncio` loop management code.

### Agents
#### [MODIFY] [enricher.py](file:///home/frank/workspace/egregora/src/egregora/agents/enricher.py)
- Remove `async` from tool definitions.

#### [MODIFY] [writer_tools.py](file:///home/frank/workspace/egregora/src/egregora/agents/writer_tools.py)
- Remove `async` from `AsyncBannerCapability` (rename to `BannerCapability` or merge).

#### [MODIFY] [capabilities.py](file:///home/frank/workspace/egregora/src/egregora/agents/capabilities.py)
- Update capability interfaces to be synchronous.

## Verification Plan
### Automated Tests
- Run `egregora write` end-to-end to verify the pipeline runs without `asyncio` errors.
- Verify concurrency still works (enrichment should still happen in parallel threads).

### Manual Verification
- Check logs to ensure no "Event loop" errors appear.
- Verify `blog-test` output contains generated posts.
