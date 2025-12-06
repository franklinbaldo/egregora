# Egregora V3 Development Plan

> **Note:** This document is the authoritative source for V3 architectural decisions and roadmap.

## Vision: The "Atom-Centric" & "Streaming" Engine

Egregora V3 prioritizes standard data structures (Atom), deterministic pipeline processing, and efficient I/O handling via streaming.

### Core Architectural Tenets

1.  **Atom-Centric & Single-Table:**
    - The entire data model is based on the Atom Syndication Format (RFC 4287).
    - All data (`Entry`, `Document`) is stored in a **single DuckDB table** (`documents`), ensuring a unified, queryable history.
    - No separate tables for "runs" or "threads"; everything is an Entry.

2.  **Async-First & Streaming:**
    - The core pipeline uses **Async Generators** (`AsyncIterator[Entry]`) to stream data between stages.
    - Concurrency is managed via `asyncio`.
    - Components (Agents, Adapters) expose async interfaces to prevent blocking the event loop during I/O.
    - Batching utilities (`abatch`) are used to optimize LLM and Database calls.

3.  **No-Defensive Programming:**
    - **Trust the Types:** We rely on Pydantic and Python's type system.
    - **Parse, Don't Validate:** Validation happens at the boundaries (Input Adapters). Once data is internal, we assume it is correct.
    - No redundant runtime checks (e.g., `if x is None` where type hint says `x: str`).

4.  **Parse-And-Project:**
    - Input Adapters *parse* raw data into a standard `Entry`.
    - Output Sinks *project* `Entry` objects into target formats (Static Site, RSS, etc.).

---

## Phase 1: Core Foundation (Current)

**Goal:** Define domain model, protocols, and configuration.

### 1.1 Core Types
- [x] Define `Entry` and `Document` models (Atom RFC 4287 compliant).
- [x] Define `Feed` model for aggregation.
- [ ] Complete semantic identity logic in `Document.create()` (Support Slugs).
- [ ] Implement `Feed.to_xml()` for Atom feed export.
- [ ] Add `documents_to_feed()` aggregation function.
- [ ] Document threading support (RFC 4685 `in_reply_to`).

### 1.2 Configuration
- [x] Implement `EgregoraConfig` with Pydantic V2.
- [x] Implement `ConfigLoader` with environment variable support (`EGREGORA_SECTION__KEY`).
- [x] Implement `PipelineContext` for request-scoped state.

### 1.3 Refinements
- [ ] **Media Handling:** `Link(rel="enclosure")` pattern.
- [ ] **Identity Strategy:** Hybrid approach (UUIDv5 + Semantic Slugs).

---

## Phase 2: Infrastructure (I/O)

**Goal:** Implement adapters, repositories, and sinks (Async).

### 2.1 Input Adapters
- [ ] **RSSAdapter:** Consume RSS/Atom feeds (Async).
- [ ] **JSONAPIAdapter:** Generic HTTP JSON API consumer (Async).
- [ ] **WhatsAppAdapter:** Port V2 logic, parse to `Entry`.
    - *Note:* Privacy/Anonymization happens here, during ingestion.

### 2.2 Document Repository
- [ ] **DuckDBDocumentRepository:**
    - Single table: `documents`.
    - Interface: `save(doc)`, `get(id)`, `list(filter)`, `delete(id)`.
    - Async wrappers around DuckDB/Ibis operations where applicable (or thread-offloaded).

### 2.3 Vector Store (RAG)
- [ ] **LanceDBVectorStore:**
    - Port V2 logic.
    - `index_documents(docs)`, `search(query)`.
    - Async API.

### 2.4 Output Sinks
- [ ] **MkDocsOutputSink:** Generate static site.
- [ ] **AtomXMLOutputSink:** Export standard Atom feed.
- [ ] **SQLiteOutputSink:** Export to SQLite (for analytics/archival).
- [ ] **CSVOutputSink:** Export to CSV.

---

## Phase 3: Cognitive Engine

**Goal:** Async Agent Orchestration.

### 3.1 Agent Architecture
- [ ] **Framework:** Pydantic-AI (primary) or LlamaIndex (library mode).
- [ ] **Interface:** `LLMModel` (Async Wrapper).
- [ ] **Dependency Injection:** Inject `PipelineContext` into Tools.

### 3.2 Core Agents
- [ ] **EnricherAgent:**
    - Fetch metadata/media descriptions.
    - **Async Generator** pattern for streaming results.
    - Parallel batching via `abatch`.
- [ ] **WriterAgent:**
    - RAG-augmented writing.
    - Jinja2 prompt rendering.
    - **Async Generator** pattern.

### 3.3 Prompt Engineering
- [ ] **Jinja2 Management:** `engine/prompts/` directory structure.
- [ ] **Testing:** 100% prompt rendering coverage.
- [ ] **Golden Fixtures:** Record/Replay for deterministic tests.

---

## Phase 4: Pipeline Orchestration

**Goal:** The `egregora` CLI and Streaming Pipeline.

### 4.1 Batching Utilities
- [ ] `abatch()`: Buffer async stream into batches.
- [ ] `materialize()`: Collect stream to list.
- [ ] `afilter()`: Async stream filtering.
- [ ] `atake()`: Limit stream items.

### 4.2 Orchestrator
- [ ] **Streaming Pipeline:**
    - `Source (AsyncIter) -> Adapter -> [Privacy] -> Repo -> [Enricher (AsyncIter) -> Repo] -> [Writer (AsyncIter) -> Repo] -> Sink`.
- [ ] **CLI Commands:**
    - `init`: Scaffold site.
    - `write`: Ingest -> Process -> Publish.
    - `read`: Read/Evaluate content.
- [ ] **Runner:** `PipelineRunner` class managing the async flow.

---

## Migration Strategy

- **Coexistence:** V3 and V2 run side-by-side.
- **Tools:** `egregora migrate-config`, `import-v2`.
- **Documentation:** "V3 for V2 Users" guide.
