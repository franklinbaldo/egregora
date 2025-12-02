# Task: Remove Asyncio and Convert to Synchronous

## Background
The user requested to remove all asynchronous code (`async`/`await`) to reduce complexity and simplify debugging. The current codebase uses `asyncio` primarily for:
1.  **RAG**: Asynchronous embedding generation and database insertion.
2.  **Orchestration**: Parallel execution of enrichment tasks using `asyncio.gather`.
3.  **Agents**: Asynchronous tool execution (e.g., banner generation).

## Objective
Convert the entire codebase to use synchronous blocking I/O. Where concurrency is beneficial (e.g., network requests), use `concurrent.futures.ThreadPoolExecutor` instead of `asyncio`.

## Plan
1.- [x] **RAG Layer Conversion**
    - [x] Refactor `src/egregora/rag/embedding_router.py` to use `threading` and `queue.Queue`.
    - [x] Update `src/egregora/rag/lancedb_backend.py` to be synchronous.
    - [x] Update `src/egregora/rag/duckdb_integration.py` to be synchronous.
    - [x] Remove `src/egregora/rag/embeddings_async.py`.

- [x] **Orchestration Layer Conversion**
    - [x] Refactor `src/egregora/orchestration/workers.py` to use `ThreadPoolExecutor`.
    - [x] Remove `asyncio` event loop management.

- [x] **Agent Layer Conversion**
    - [x] Update `src/egregora/agents/writer.py` to use synchronous execution (`agent.run_sync`).
    - [x] Update `src/egregora/agents/writer_tools.py` to be synchronous.
    - [x] Update `src/egregora/agents/capabilities.py` to be synchronous.
    - [x] Refactor `src/egregora/agents/enricher.py` to use `ThreadPoolExecutor` (or remove if unused).
    - [x] Refactor `src/egregora/agents/reader/agent.py` to be synchronous.
    - [x] Refactor `src/egregora/agents/reader/reader_runner.py` to be synchronous.
    - [x] Refactor `src/egregora/agents/tools/skill_injection.py` to be synchronous.

- [x] **Model Layer Conversion**
    - [x] Refactor `src/egregora/models/google_batch.py` to use synchronous `httpx.Client` and blocking I/O.

- [x] **Verification**
    - [x] Run `egregora write` to verify end-to-end functionality.
    - [x] Confirm posts are generated.` event loop management code.

4.  **Cleanup**:
    - Remove any remaining `async def` or `await` keywords.
    - Verify tests pass (or update them).

## Files to Modify
- `src/egregora/rag/backend.py`
- `src/egregora/rag/lancedb_backend.py`
- `src/egregora/rag/embeddings.py`
- `src/egregora/rag/embedding_router.py`
- `src/egregora/orchestration/workers.py`
- `src/egregora/agents/enricher.py`
- `src/egregora/agents/writer_tools.py`
- `src/egregora/agents/capabilities.py`
