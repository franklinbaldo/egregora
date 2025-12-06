# Egregora V3 Development TODO

> **Testing Approach:** We are practicing TDD. Tests for upcoming tasks are added first and may be marked as expected failures until implementations land.

> **Reference:** [V3 Development Plan](docs/v3_development_plan.md)
>
> **Note:** This file is generated from the v3 development plan. To propose substantive changes to the roadmap or implementation strategy, please update `docs/v3_development_plan.md` first to maintain consistency.
>
> **Status:** Planning phase with core types defined
>
> **Target Timeline:** Alpha in 12 months, feature parity in 24 months

---

## Phase 1: Core Foundation ✅ ~80% Complete

**Goal:** Define domain model and contracts
**Reference:** [docs/v3_development_plan.md#phase-1-core-foundation-current](docs/v3_development_plan.md#phase-1-core-foundation-current)

### Remaining Work

- [ ] Complete semantic identity logic in `Document.create()` (Support Slugs)
- [ ] Implement `Feed.to_xml()` for Atom feed export
- [ ] Add `documents_to_feed()` aggregation function
- [ ] 100% unit test coverage for all core types
- [ ] Document threading support (RFC 4685 `in_reply_to`)
- [ ] Implement `PipelineContext` for request-scoped state

### Phase 1.5: Refinements

#### Media Handling Strategy
- [ ] Document media handling via `Link(rel="enclosure")` pattern
- [ ] Implement enrichment workflow for media processing

#### Identity Strategy
- [ ] Implement hybrid identity approach (UUIDv5 + Semantic Slugs)

#### Config Loader ✅ COMPLETE
- [x] Refactor `EgregoraConfig.load()` to dedicated loader class
- [x] Better error reporting for malformed YAML
- [x] Environment variable override support (`EGREGORA_SECTION__KEY`)

---

## Phase 2: Infrastructure 🔄 Not Started

**Goal:** Implement adapters and external I/O (Async-First)
**Reference:** [docs/v3_development_plan.md#phase-2-infrastructure-io](docs/v3_development_plan.md#phase-2-infrastructure-io)

### 2.1 Input Adapters
- [ ] Implement `RSSAdapter` (Async)
- [ ] Implement `JSONAPIAdapter` (Async)
- [ ] Port `WhatsAppAdapter` from V2 (Privacy during ingestion)

### 2.2 Document Repository
- [ ] Implement `DuckDBDocumentRepository` (Single `documents` table)
  - [ ] `save(doc: Document) -> None`
  - [ ] `get(doc_id: str) -> Document | None`
  - [ ] `list(filter) -> list[Document]`
  - [ ] `delete(doc_id: str) -> None`
  - [ ] Async wrapper/integration

### 2.3 Vector Store (RAG)
- [ ] Port `LanceDBVectorStore` from V2 (Async API)

### 2.4 Output Sinks
- [ ] Implement `MkDocsOutputSink`
- [ ] Implement `AtomXMLOutputSink`
- [ ] Implement `SQLiteOutputSink`
- [ ] Implement `CSVOutputSink`

---

## Phase 3: Cognitive Engine 🔄 Not Started

**Goal:** Async Agent Orchestration
**Reference:** [docs/v3_development_plan.md#phase-3-cognitive-engine](docs/v3_development_plan.md#phase-3-cognitive-engine)

### 3.1 Agent Architecture
- [ ] Configure Agent Framework (Pydantic-AI/LlamaIndex)
- [ ] Implement `LLMModel` Async Wrapper
- [ ] Implement Dependency Injection for Tools

### 3.2 Core Agents
- [ ] Implement `EnricherAgent` (Async Generator Pattern)
  - [ ] Streaming results
  - [ ] Parallel batching with `abatch`
- [ ] Implement `WriterAgent` (Async Generator Pattern)
  - [ ] RAG-augmented writing
  - [ ] Streaming results

### 3.3 Prompt Engineering
- [ ] Create prompt directory structure (`engine/prompts/`)
- [ ] Implement Jinja2 Template Loader
- [ ] Achieve 100% Prompt Rendering Coverage

---

## Phase 4: Pipeline Orchestration 🔄 Not Started

**Goal:** Assemble full streaming pipeline with CLI
**Reference:** [docs/v3_development_plan.md#phase-4-pipeline-orchestration](docs/v3_development_plan.md#phase-4-pipeline-orchestration)

### 4.1 Batching Utilities
- [ ] Implement `abatch()` - Buffer async stream into batches
- [ ] Implement `materialize()` - Collect stream to list
- [ ] Implement `afilter()` - Async stream filtering
- [ ] Implement `atake()` - Limit stream items

### 4.2 Orchestrator
- [ ] Implement Streaming Pipeline Runner (Async Generators)
- [ ] Integrate Privacy Stage

### 4.3 CLI
- [ ] Implement `init` command
- [ ] Implement `write` command
- [ ] Implement `read` command
- [ ] Implement `serve` command

---

## Migration Strategy
- [ ] Build `egregora migrate-config` tool
- [ ] Build `egregora import-v2` tool
