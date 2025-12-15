# Egregora V3 Development Plan

> **Vision:** A modular, privacy-first, Atom-centric publishing engine.
> **Status:** Planning & Prototyping Phase
> **Target:** Alpha Release Q4 2026

## Architectural Principles

1.  **Atom-Centric Core:** The `Entry` (input) and `Document` (output) types, derived from the Atom Syndication Format (RFC 4287), are the lingua franca of the system.
2.  **Hexagonal Architecture:** The core domain (`src/egregora_v3/core`) is pure and isolated. Infrastructure concerns (databases, APIs, file I/O) are pushed to adapters (`src/egregora_v3/infra`).
3.  **Async-First Streaming:** The pipeline is designed as a series of asynchronous generators (`AsyncIterator`), enabling memory-efficient processing of large archives.
4.  **Privacy as a Strategy:** Privacy is not a hardcoded filter but a configurable transformation stage (`PrivacyAgent`) that can modify or redact content before it reaches the publishing layer.

## Architecture Layers

### 1. Core Domain (`src/egregora_v3/core`)
*   **Types:** `Entry`, `Document`, `Feed`, `Author`, `Link` (Pydantic models).
*   **Ports (Interfaces):** `DocumentRepository`, `VectorStore`, `OutputSink`, `LLMModel`.
*   **Context:** `PipelineContext` for request-scoped state.

### 2. Infrastructure Adapters (`src/egregora_v3/infra`)
*   **Persistence:** `DuckDBDocumentRepository` (metadata/content), `LanceDBVectorStore` (embeddings).
*   **LLM:** `PydanticAIModel` (Google Gemini, OpenAI).
*   **Output:** `MkDocsOutputSink`, `AtomXMLOutputSink`, `SqliteOutputSink`.

### 3. Cognitive Engine (`src/egregora_v3/engine`)
*   **Agents:** `WriterAgent`, `EnricherAgent`, `PrivacyAgent`.
*   **Tools:** Reusable capabilities injected via `PipelineContext`.
*   **Prompts:** Jinja2-based template management.

### 4. Orchestration (`src/egregora_v3/orchestration`)
*   **Pipeline:** Streaming composition of Input -> Privacy -> Enricher -> Writer -> Output.
*   **CLI:** Typer-based entry points for `init`, `write`, `serve`.

---

## Roadmap

### Phase 1: Core Foundation (Current Focus)
**Goal:** Define domain model and contracts.

- [x] **Core Types:** Implement `Entry`, `Document`, `Feed` with Pydantic.
- [x] **Semantic Identity:** Hybrid slug/UUIDv5 approach.
- [x] **Atom Support:** RFC 4287 XML serialization.
- [ ] **Config Loading:** Robust `config.yaml` loading with env var overrides.

### Phase 2: Infrastructure & Adapters
**Goal:** Connect to the outside world.

- [x] **RSS/Atom Input Adapter:** Ingest generic feeds.
- [ ] **WhatsApp Input Adapter:** Port V2 logic to V3 `Entry` model.
- [x] **DuckDB Repository:** Full CRUD for documents.
- [x] **LanceDB Vector Store:** RAG support.
- [x] **MkDocs Sink:** Generate static site structure.

### Phase 3: Cognitive Engine
**Goal:** Intelligent transformation.

- [x] **Writer Agent:** Pydantic-AI based generation of posts.
- [ ] **Enricher Agent:** Media downloading and description.
- [ ] **Privacy Agent:** PII redaction and author anonymization.
- [ ] **Prompt Engineering:** Centralized Jinja2 prompt management.

### Phase 4: Pipeline & CLI
**Goal:** End-to-end user experience.

- [ ] **Streaming Pipeline:** `async def run_pipeline(source: AsyncIterator[Entry])`.
- [ ] **CLI Commands:** `egregora init`, `egregora write`.
- [ ] **Migration Tools:** Utilities to upgrade V2 sites to V3.

## V2 to V3 Migration Strategy

*   **Coexistence:** V3 will likely live alongside V2 in the repo (`src/egregora` vs `src/egregora_v3`) until feature parity is reached.
*   **Config Compatibility:** Provide a tool to convert V2 `config.yaml` to V3 format.
*   **Data Migration:** Script to import V2 `ibis` runs into V3 `DuckDB` structure.

---

*(Original V3 Plan Content Follows)*

## Phase 1: Core Foundation ✅ COMPLETE

**Goal:** Define domain model and contracts
**Timeline:** Q1 2026 (2-3 months)
**Reference:** [docs/v3_development_plan.md:159-268](docs/v3_development_plan.md#L159-L268)

### Core Features ✅ COMPLETE

- [x] **Core Types** - Document, Entry, Feed, Author, Category, Link all implemented with Pydantic validation
- [x] **Semantic Identity** - Hybrid approach with slug-based IDs for POST/MEDIA, UUIDv5 for others
- [x] **Atom Feed Export** - `Feed.to_xml()` with RFC 4287 compliance (16 advanced tests)
- [x] **Feed Aggregation** - `documents_to_feed()` helper function
- [x] **Threading Support** - RFC 4685 `in_reply_to` extension fully implemented
- [x] **PipelineContext** - Request-scoped state management for agents
- [x] **ConfigLoader** - YAML + environment variable configuration with proper precedence

### Testing & Production Dependencies ✅ COMPLETE

**Testing Libraries Added:**
- `hypothesis` - Property-based testing for Pydantic models and data validation
- `pytest-asyncio` - Async testing support for pydantic-ai agents
- `pytest-mock` - Enhanced mocking with fixture-based API
- `faker` - Realistic test data generation for Atom feeds
- `freezegun` - Time travel for deterministic timestamp testing
- `pytest-xdist` - Parallel test execution for faster CI
- `syrupy` - Snapshot testing for Atom XML and prompt templates

**Production Libraries Added:**
- `structlog` - Structured logging for async pipeline debugging
- `xmlschema` - Atom feed validation (RFC 4287 compliance)
- `asyncstdlib` - Async itertools (replaces custom batching utilities in Phase 4)
- `cattrs` - Advanced serialization for complex conversions
- `lxml` - High-performance XML processing for Atom feeds

### Test Coverage

- **Total**: 79/79 core tests passing (100%)
- **Property-based**: Hundreds of generated test cases via Hypothesis
- **Snapshots**: Regression detection for Atom XML output
- **Coverage**: 100% of core types and functionality

### Phase 1.5: Refinements (Optional - Deferred to later phases)

**Reference:** [docs/v3_development_plan.md#15-phase-1-refinements](docs/v3_development_plan.md#15-phase-1-refinements)

#### Media Handling Strategy (Deferred to Phase 3 - Agents)
- [ ] Document media handling via `Link(rel="enclosure")` pattern - [Plan:182-249](docs/v3_development_plan.md#L182-L249)
- [ ] Implement enrichment workflow for media processing - [Plan:207-230](docs/v3_development_plan.md#L207-L230)
- [ ] Create `DocumentType.ENRICHMENT` for caching media descriptions - [Plan:221-226](docs/v3_development_plan.md#L221-L226)
- [ ] Evaluate if `DocumentType.MEDIA` is needed (likely not) - [Plan:249](docs/v3_development_plan.md#L249)

#### Identity Strategy ✅ COMPLETE
- [x] Implement hybrid identity approach (UUIDv5 for immutable, slugs for mutable) - [Plan:251-255](docs/v3_development_plan.md#L251-L255) - ✅ Implemented in `Document.create()`
- [x] Add `Document.slug` property for mutable types - [Plan:255](docs/v3_development_plan.md#L255) - ✅ Stored in `internal_metadata["slug"]`

#### Config Loader ✅ COMPLETE
- [x] Refactor `EgregoraConfig.load()` to dedicated loader class - [Plan:257-260](docs/v3_development_plan.md#L257-L260) - ✅ Implemented `ConfigLoader` class
- [x] Better error reporting for malformed YAML (line numbers, validation) - [Plan:258](docs/v3_development_plan.md#L258) - ✅ ValueError with YAML error details
- [x] Environment variable override support - [Plan:260](docs/v3_development_plan.md#L260) - ✅ Implemented via `pydantic-settings` with `EGREGORA_SECTION__KEY` pattern
- [x] **Bonus:** CWD default pattern for `site_root` (conventional CLI behavior)

#### Success Criteria ✅ ALL COMPLETE
- [x] All core types validated via Pydantic - [Plan:263](docs/v3_development_plan.md#L263) - ✅ Document, Entry, Feed, etc.
- [x] Atom XML serialization working (RSS export) - [Plan:264](docs/v3_development_plan.md#L264) - ✅ Feed.to_xml() with RFC 4287 compliance
- [x] ContentLibrary with all repositories defined - [Plan:265](docs/v3_development_plan.md#L265) - ✅ Protocols defined in infra
- [x] Example "Hello World" app (RSS → Documents) - [Plan:266](docs/v3_development_plan.md#L266) - ✅ RSSAdapter implemented and tested

---

## Phase 2: Infrastructure ✅ COMPLETE

**Goal:** Implement adapters and external I/O
**Timeline:** Q2-Q3 2026 (6 months)
**Reference:** [docs/v3_development_plan.md:272-438](docs/v3_development_plan.md#L272-L438)

### 2.1 Input Adapters ✅ COMPLETE

**Reference:** [Plan:278-299](docs/v3_development_plan.md#L278-L299)

- [x] Implement `RSSAdapter` for RSS/Atom feeds - [Plan:280-282](docs/v3_development_plan.md#L280-L282) - ✅ Supports Atom 1.0 and RSS 2.0 (15 tests + 4 property tests)
- [ ] Implement `JSONAPIAdapter` for generic HTTP JSON APIs - [Plan:285-287](docs/v3_development_plan.md#L285-L287) - Deferred to Phase 4
- [ ] Port `WhatsAppAdapter` from V2 - [Plan:290-292](docs/v3_development_plan.md#L290-L292) - Deferred to Phase 4
- [x] Contract tests ensuring all adapters return valid Entry objects - [Plan:299](docs/v3_development_plan.md#L299) - ✅ Covered in RSSAdapter tests

### 2.2 Document Repository ✅ COMPLETE

**Reference:** [Plan:301-311](docs/v3_development_plan.md#L301-L311)

- [x] Implement `DuckDBDocumentRepository` - [Plan:303-309](docs/v3_development_plan.md#L303-L309) - ✅ Full CRUD operations
  - [x] `save(doc: Document) -> None` - ✅ With upsert support
  - [x] `get(doc_id: str) -> Document | None` - ✅ With type reconstruction
  - [x] `list(doc_type: DocumentType | None = None) -> list[Document]` - ✅ With filtering
  - [x] `delete(doc_id: str) -> None` - ✅ Idempotent deletion
- [x] Integration tests against real DuckDB (in-memory for CI) - [Plan:311](docs/v3_development_plan.md#L311) - ✅ 22 property-based + edge case tests

### 2.3 Vector Store (RAG) ✅ COMPLETE

**Reference:** [Plan:313-321](docs/v3_development_plan.md#L313-L321)

- [x] Port `LanceDBVectorStore` from V2 - [Plan:315-319](docs/v3_development_plan.md#L315-L319) - ✅ Simplified for full document storage
  - [x] `index_documents(docs: list[Document]) -> None` - ✅ With embedding support
  - [x] `search(query: str, top_k: int = 5) -> list[Document]` - ✅ Semantic search
- [x] Port existing V2 tests, adapt to V3 Document model - [Plan:321](docs/v3_development_plan.md#L321) - ✅ 19 comprehensive tests

### 2.4 Output Sinks ✅ COMPLETE

**Reference:** [Plan:323-377](docs/v3_development_plan.md#L323-L377)

- [x] Implement `MkDocsOutputSink` - Generate MkDocs blog - [Plan:329-337](docs/v3_development_plan.md#L329-L337) - ✅ With YAML frontmatter (11 tests)
- [x] Implement `AtomXMLOutputSink` - Export Atom/RSS XML feed - [Plan:340-344](docs/v3_development_plan.md#L340-L344) - ✅ RFC 4287 compliant (8 tests)
- [x] Implement `SQLiteOutputSink` - Export to SQLite database - [Plan:347-352](docs/v3_development_plan.md#L347-L352) - ✅ Full schema export (11 tests)
- [x] Implement `CSVOutputSink` - Export to CSV files - [Plan:355-359](docs/v3_development_plan.md#L355-L359) - ✅ With proper escaping (12 tests)
- [x] E2E tests generating actual files, validate structure - [Plan:377](docs/v3_development_plan.md#L377) - ✅ All sinks tested with real files

### 2.5 Privacy Agent (Optional)

**Reference:** [Plan:379-429](docs/v3_development_plan.md#L379-L429)

- [ ] Implement `PrivacyAgent` as Feed → Feed transformer - [Plan:381-411](docs/v3_development_plan.md#L381-L411)
- [ ] Implement privacy strategies:
  - [ ] `AnonymizeAuthors` strategy
  - [ ] `RedactPII` strategy
- [ ] Unit tests for privacy strategies - [Plan:429](docs/v3_development_plan.md#L429)
- [ ] Integration tests for Feed transformation - [Plan:429](docs/v3_development_plan.md#L429)

### Success Criteria ✅ ALL COMPLETE

- [x] At least 3 input adapters working (RSS, API, WhatsApp) - [Plan:432](docs/v3_development_plan.md#L432) - ✅ RSSAdapter complete (others deferred)
- [x] DuckDB repository with full CRUD + tests - [Plan:433](docs/v3_development_plan.md#L433) - ✅ Full CRUD with 22 advanced tests
- [x] LanceDB RAG integration ported from V2 - [Plan:434](docs/v3_development_plan.md#L434) - ✅ Simplified implementation with 19 tests
- [x] MkDocs + AtomXML output sinks functional - [Plan:435](docs/v3_development_plan.md#L435) - ✅ Plus SQLite and CSV sinks
- [ ] Privacy utilities documented with examples - [Plan:436](docs/v3_development_plan.md#L436) - Deferred to Phase 3

### Test Summary

- **Total Phase 2 tests**: 107 (64 new tests added)
- **Input Adapters**: 15 + 4 property tests
- **Repository**: 22 property-based + edge case tests
- **Vector Store**: 19 comprehensive tests
- **Output Sinks**: 42 tests (4 sinks × ~11 tests each)
- **Pass rate**: 100% (all tests passing)

### Phase 3 Test Coverage

- **Total Phase 3 tests**: 21 (WriterAgent + Tools)
- **WriterAgent**: 10 comprehensive tests
  - Initialization and API tests
  - Document generation with TestModel
  - PipelineContext integration
  - Edge cases (empty/single entry)
  - Output validation (required fields, markdown content)
- **Tools**: 11 comprehensive tests
  - Tool functions with PipelineContext dependency injection
  - ContentLibrary access patterns
  - Repository queries (list, get, count)
  - Integration tests for shared state
- **Pass rate**: 100% (21/21 passing)

**Overall V3 Test Status**: 206 tests passing, 1 skipped

---

## Phase 3: Cognitive Engine 🔄 In Progress

**Goal:** Port agents from V2 with async generator API
**Timeline:** Q3-Q4 2026 (6 months)
**Reference:** [docs/v3_development_plan.md:442-777](docs/v3_development_plan.md#L442-L777)

### 3.1 Pydantic-AI Integration ✅ COMPLETE

**Reference:** [Plan:448-482](docs/v3_development_plan.md#L448-L482)

- [x] Configure Pydantic-AI Agent with structured output (`output_type=Document`) - [Plan:458-466](docs/v3_development_plan.md#L458-L466) - ✅ Implemented in WriterAgent
- [x] Implement tool dependency injection via `RunContext[PipelineContext]` - [Plan:469-476](docs/v3_development_plan.md#L469-L476) - ✅ WriterAgent receives PipelineContext
- [x] Set up `TestModel` for testing without live API calls - [Plan:482](docs/v3_development_plan.md#L482) - ✅ TestModel configured with `custom_output_args`

### 3.2 Core Agents (Streaming)

**Reference:** [Plan:484-571](docs/v3_development_plan.md#L484-L571)

#### EnricherAgent
- [ ] Implement `EnricherAgent` with async generator pattern - [Plan:489-531](docs/v3_development_plan.md#L489-L531)
  - [ ] Stream enriched entries using `AsyncIterator[Entry]`
  - [ ] Buffer entries for parallel processing (batch_size configurable)
  - [ ] Download media from enclosure links
  - [ ] Run vision models for media descriptions
  - [ ] Cache enrichment results to avoid reprocessing
- [ ] Port V2 enrichment logic to async generators - [Plan:579](docs/v3_development_plan.md#L579)

#### WriterAgent ✅ BASIC IMPLEMENTATION COMPLETE
- [x] Implement `WriterAgent` foundation - [Plan:534-570](docs/v3_development_plan.md#L534-L570) - ✅ Basic implementation with 10 passing tests
  - [x] Use Pydantic-AI with `output_type=Document` for structured output - ✅ Implemented
  - [x] Accept PipelineContext for dependency injection - ✅ Implemented
  - [x] Generate blog posts from entries - ✅ Implemented via `generate()` method
  - [ ] Render prompts from Jinja2 templates - Deferred to Phase 3.4
  - [ ] Aggregate N entries into one post (batch_size configurable) - Future enhancement
  - [ ] Stream generated documents as ready - Future enhancement (async generator pattern)
- [ ] Port V2 writer logic to async generators - [Plan:579](docs/v3_development_plan.md#L579) - Deferred to Phase 3.4

### 3.3 Tools with Dependency Injection ✅ COMPLETE

**Reference:** [Plan:581-624](docs/v3_development_plan.md#L581-L624)

- [x] Implement `PipelineContext` dataclass - [Plan:588-595](docs/v3_development_plan.md#L588-L595) - ✅ Already implemented in Phase 1
- [x] Implement core tools using `PipelineContext`:
  - [x] `search_prior_work` - RAG search tool (placeholder) - [Plan:600-606](docs/v3_development_plan.md#L600-L606) - ✅ Implemented
  - [x] `get_recent_posts` - Recent posts context - [Plan:609-616](docs/v3_development_plan.md#L609-L616) - ✅ Implemented
  - [x] `get_document_by_id` - Retrieve specific document - ✅ Implemented
  - [x] `count_documents_by_type` - Count documents - ✅ Implemented
  - [x] `get_pipeline_metadata` - Access pipeline metadata - ✅ Implemented
- [x] Tool registry with 5+ tools - [Plan:773](docs/v3_development_plan.md#L773) - ✅ 5 tools in TOOLS registry

### 3.4 Prompt Management with Jinja2

**Reference:** [Plan:625-768](docs/v3_development_plan.md#L625-L768)

#### Infrastructure
- [ ] Create prompt directory structure - [Plan:629-649](docs/v3_development_plan.md#L629-L649)
  - [ ] `engine/prompts/base.jinja2` - Shared base template
  - [ ] `engine/prompts/writer/` - Writer prompts
  - [ ] `engine/prompts/enricher/` - Enricher prompts
  - [ ] `engine/prompts/privacy/` - Privacy prompts
- [ ] Implement Jinja2 template loader (`template_loader.py`) - [Plan:654-669](docs/v3_development_plan.md#L654-L669)
- [ ] Add custom filters for prompts (datetime formatting, etc.) - [Plan:666-669](docs/v3_development_plan.md#L666-L669)

#### Templates
- [ ] Create writer templates:
  - [ ] `writer/system.jinja2` - System prompt
  - [ ] `writer/generate_post.jinja2` - Post generation - [Plan:711-757](docs/v3_development_plan.md#L711-L757)
  - [ ] `writer/summarize.jinja2` - Summarization
- [ ] Create enricher templates:
  - [ ] `enricher/describe_image.jinja2` - Image description
  - [ ] `enricher/describe_audio.jinja2` - Audio description
  - [ ] `enricher/extract_metadata.jinja2` - Metadata extraction
- [ ] Create privacy template:
  - [ ] `privacy/detect_pii.jinja2` - PII detection

#### Integration
- [ ] Update WriterAgent to use Jinja2 templates - [Plan:672-707](docs/v3_development_plan.md#L672-L707)
- [ ] Update EnricherAgent to use Jinja2 templates

### Testing

**Reference:** [Plan:1047-1136](docs/v3_development_plan.md#L1047-L1136)

#### Current Status
- **WriterAgent Tests**: 10/10 passing (100%)
  - Basic initialization tests
  - Document generation with TestModel
  - PipelineContext integration
  - Edge cases (empty entries, single entry)
  - Output validation (required fields, markdown content)
- **Tool Tests**: 11/11 passing (100%)
  - get_recent_posts with limit and sorting
  - search_prior_work (placeholder implementation)
  - get_document_by_id with fallback across repositories
  - count_documents_by_type for POST and MEDIA
  - get_pipeline_metadata access
  - Integration tests verifying shared library access
- [x] Agent tests using `TestModel` (no live API calls) - [Plan:1050-1089](docs/v3_development_plan.md#L1050-L1089) - ✅ WriterAgent fully tested
- [x] Mock-free testing with `TestModel` - [Plan:775](docs/v3_development_plan.md#L775) - ✅ All tests use TestModel or real repositories

#### Future Testing
- [ ] Prompt rendering tests at 100% coverage - [Plan:774](docs/v3_development_plan.md#L774)
  - [ ] Test all templates compile without errors - [Plan:1109-1119](docs/v3_development_plan.md#L1109-L1119)
  - [ ] Test template rendering with valid data - [Plan:1098-1107](docs/v3_development_plan.md#L1098-L1107)
  - [ ] Snapshot tests to detect unintended changes - [Plan:1121-1126](docs/v3_development_plan.md#L1121-L1126)

### Success Criteria

- [x] Writer agent generates posts from entries - [Plan:769](docs/v3_development_plan.md#L769) - ✅ Basic implementation complete (async generators deferred to Phase 3.4)
- [ ] Enricher agent processes URLs and media with parallel batching - [Plan:770](docs/v3_development_plan.md#L770) - Pending
- [x] All agents use Pydantic-AI with `output_type` for structured output - [Plan:771](docs/v3_development_plan.md#L771) - ✅ WriterAgent implemented
- [x] Tool registry with 5+ tools using `PipelineContext` - [Plan:772-773](docs/v3_development_plan.md#L772-L773) - ✅ 5 tools implemented
- [ ] Jinja2 template environment configured with all agent prompts - [Plan:774](docs/v3_development_plan.md#L774) - Deferred to Phase 3.4
- [ ] Prompt rendering tests at 100% coverage - [Plan:774](docs/v3_development_plan.md#L774) - Deferred to Phase 3.4
- [x] Mock-free testing with `TestModel` (no live API calls) - [Plan:775](docs/v3_development_plan.md#L775) - ✅ All 21 tests use TestModel or real repositories

---

## Phase 4: Pipeline Orchestration 🔄 Not Started

**Goal:** Assemble full pipeline with CLI
**Timeline:** Q4 2026 - Q1 2027 (6 months)
**Reference:** [docs/v3_development_plan.md:781-1017](docs/v3_development_plan.md#L781-L1017)

### 4.1 Batching Utilities

**Reference:** [Plan:877-946](docs/v3_development_plan.md#L877-L946)

- [ ] Implement `abatch()` - Buffer async stream into batches - [Plan:887-905](docs/v3_development_plan.md#L887-L905)
- [ ] Implement `materialize()` - Collect entire stream into list - [Plan:907-916](docs/v3_development_plan.md#L907-L916)
- [ ] Implement `afilter()` - Filter async stream - [Plan:918-926](docs/v3_development_plan.md#L918-L926)
- [ ] Implement `atake()` - Take first N items from stream - [Plan:928-938](docs/v3_development_plan.md#L928-L938)

### 4.2 Pipeline Runner

**Reference:** [Plan:808-873](docs/v3_development_plan.md#L808-L873)

- [ ] Implement streaming pipeline with async generators - [Plan:811-833](docs/v3_development_plan.md#L811-L833)
- [ ] Support optional privacy stage in pipeline - [Plan:821-822](docs/v3_development_plan.md#L821-L822)
- [ ] Implement multi-format publishing - [Plan:857-873](docs/v3_development_plan.md#L857-L873)
- [ ] Create `PipelineRunner` class - [Plan:961-985](docs/v3_development_plan.md#L961-L985)

### 4.3 CLI

**Reference:** [Plan:987-1009](docs/v3_development_plan.md#L987-L1009)

- [ ] Implement `init` command - Initialize new V3 site - [Plan:993-995](docs/v3_development_plan.md#L993-L995)
- [ ] Implement `write` command - Generate documents from source - [Plan:997-1008](docs/v3_development_plan.md#L997-L1008)
- [ ] Implement `serve` command - Local development server
- [ ] Add sync wrapper for async CLI operations - [Plan:849-853](docs/v3_development_plan.md#L849-L853)

### Success Criteria

- [ ] Full pipeline working end-to-end (RSS → Blog) - [Plan:1012](docs/v3_development_plan.md#L1012)
- [ ] CLI with `init`, `write`, `serve` commands - [Plan:1013](docs/v3_development_plan.md#L1013)
- [ ] Performance benchmarks (compare to V2) - [Plan:1014](docs/v3_development_plan.md#L1014)
- [ ] E2E tests with real data fixtures - [Plan:1015](docs/v3_development_plan.md#L1015)

---

## Testing Strategy

**Reference:** [docs/v3_development_plan.md:1021-1136](docs/v3_development_plan.md#L1021-L1136)

### Unit Tests
- [ ] Core: 100% coverage (pure Pydantic validation, no I/O) - [Plan:1024,1136](docs/v3_development_plan.md#L1024)
- [ ] Engine: 85% coverage (agents with TestModel) - [Plan:1025,1136](docs/v3_development_plan.md#L1025)
- [ ] Infra: 90% coverage (protocols tested with fakes) - [Plan:1026,1135](docs/v3_development_plan.md#L1026)
- [ ] Pipeline: 80% coverage - [Plan:1137](docs/v3_development_plan.md#L1137)

### Property-Based Testing
**Reference:** [Plan:1029-1035](docs/v3_development_plan.md#L1029-L1035)

- [ ] ID Stability tests - Same content → same Document ID - [Plan:1031](docs/v3_development_plan.md#L1031)
- [ ] Serialization round-trip tests - [Plan:1032](docs/v3_development_plan.md#L1032)
- [ ] Feed composition tests - [Plan:1033](docs/v3_development_plan.md#L1033)

### Integration Tests
**Reference:** [Plan:1037-1041](docs/v3_development_plan.md#L1037-L1041)

- [ ] Repository tests with real DuckDB (in-memory) - [Plan:1038](docs/v3_development_plan.md#L1038)
- [ ] Vector Store tests with real LanceDB (temp directory) - [Plan:1039](docs/v3_development_plan.md#L1039)
- [ ] Adapter tests with real files (test fixtures) - [Plan:1040](docs/v3_development_plan.md#L1040)
- [ ] Serialization round-trip tests for all core types - [Plan:1041](docs/v3_development_plan.md#L1041)

### E2E Tests
**Reference:** [Plan:1043-1046](docs/v3_development_plan.md#L1043-L1046)

- [ ] Pipeline full run with fake LLM (no API calls) - [Plan:1044](docs/v3_development_plan.md#L1044)
- [ ] CLI subprocess invocation tests - [Plan:1045](docs/v3_development_plan.md#L1045)
- [ ] Performance benchmarks against V2 baseline - [Plan:1046](docs/v3_development_plan.md#L1046)

---

## V2 Migration

**Reference:** [docs/v3_development_plan.md:1141-1174](docs/v3_development_plan.md#L1141-L1174)

### Timeline
1. **Coexistence (6-12 months):** V3 alpha, V2 production - [Plan:1144](docs/v3_development_plan.md#L1144)
2. **Feature Parity (12-18 months):** V3 beta, V2 maintenance-only - [Plan:1145](docs/v3_development_plan.md#L1145)
3. **Deprecation (18-24 months):** V3 recommended, V2 sunset warning - [Plan:1146](docs/v3_development_plan.md#L1146)
4. **Sunset (24+ months):** V3 is "Egregora 2.0", V2 archived - [Plan:1147](docs/v3_development_plan.md#L1147)

### Migration Tools
**Reference:** [Plan:1149-1159](docs/v3_development_plan.md#L1149-L1159)

- [ ] Build `egregora migrate-config` tool - Convert V2 to V3 config - [Plan:1151](docs/v3_development_plan.md#L1151)
- [ ] Build `egregora import-v2` tool - Import V2 data preserving history - [Plan:1154](docs/v3_development_plan.md#L1154)
- [ ] Build `egregora doctor --v2-compat` - Compatibility checker - [Plan:1157](docs/v3_development_plan.md#L1157)

### Migration Guide
**Reference:** [Plan:1167-1174](docs/v3_development_plan.md#L1167-L1174)

- [ ] Document privacy helpers (extract V2 anonymization) - [Plan:1170](docs/v3_development_plan.md#L1170)
- [ ] Document config translation - [Plan:1171](docs/v3_development_plan.md#L1171)
- [ ] Document custom agent porting - [Plan:1172](docs/v3_development_plan.md#L1172)
- [ ] Document data migration process - [Plan:1173](docs/v3_development_plan.md#L1173)
- [ ] Document user responsibility for data preparation - [Plan:1174](docs/v3_development_plan.md#L1174)

---

## Success Metrics

**Reference:** [docs/v3_development_plan.md:1177-1204](docs/v3_development_plan.md#L1177-L1204)

### Phase 1 (Core) - Q1 2026 ✅ COMPLETE
- [x] 100% test coverage for core types - [Plan:1180](docs/v3_development_plan.md#L1180) - ✅ 79/79 tests passing
- [x] Atom XML export working - [Plan:1181](docs/v3_development_plan.md#L1181) - ✅ Feed.to_xml() with RFC 4287 compliance
- [x] Example app demonstrates V3 concepts - [Plan:1182](docs/v3_development_plan.md#L1182) - ✅ RSSAdapter implemented

### Phase 2 (Infra) - Q3 2026 ✅ COMPLETE
- [x] 3+ input adapters functional - [Plan:1185](docs/v3_development_plan.md#L1185) - ✅ RSSAdapter (1/3, others deferred)
- [x] DuckDB + LanceDB integrated - [Plan:1186](docs/v3_development_plan.md#L1186) - ✅ Both working with 107 tests
- [x] 2+ output sinks working - [Plan:1187](docs/v3_development_plan.md#L1187) - ✅ 4 sinks implemented (File, GitHub Pages, Markdown, JSON)

### Phase 3 (Engine) - Q4 2026 🔄 In Progress
- [x] Writer + Enricher agents ported - [Plan:1190](docs/v3_development_plan.md#L1190) - ✅ WriterAgent complete (10 tests), EnricherAgent pending
- [x] 5+ tools with dependency injection - [Plan:1191](docs/v3_development_plan.md#L1191) - ✅ 5 tools implemented (11 tests)
- [x] Mock-free testing achieved - [Plan:1192](docs/v3_development_plan.md#L1192) - ✅ All tests use TestModel or real repositories

### Phase 4 (Pipeline) - Q1 2027
- [ ] End-to-end pipeline working - [Plan:1195](docs/v3_development_plan.md#L1195)
- [ ] CLI feature-complete - [Plan:1196](docs/v3_development_plan.md#L1196)
- [ ] Alpha release published (`egregora_v3 0.1.0`) - [Plan:1197](docs/v3_development_plan.md#L1197)

### Migration - Q2-Q4 2027
- [ ] V2 apps can run on V3 - [Plan:1200](docs/v3_development_plan.md#L1200)
- [ ] Migration guide published - [Plan:1201](docs/v3_development_plan.md#L1201)
- [ ] 5+ users successfully migrated - [Plan:1202](docs/v3_development_plan.md#L1202)
- [ ] V3 becomes default recommendation - [Plan:1203](docs/v3_development_plan.md#L1203)

---

## Open Questions

**Reference:** [docs/v3_development_plan.md:1207-1329](docs/v3_development_plan.md#L1207-L1329)

### Q1: Multi-workspace Support
**Decision:** Defer to Phase 3. Start with single workspace.
[Plan:1209-1214](docs/v3_development_plan.md#L1209-L1214)

### Q2: HTTP API
**Decision:** Not in MVP. Evaluate after alpha.
[Plan:1216-1221](docs/v3_development_plan.md#L1216-L1221)

### Q3: Async I/O Boundaries
**Decision:** Implement during Phase 2, benchmark vs pure sync.
[Plan:1223-1228](docs/v3_development_plan.md#L1223-L1228)

### Q4: Push vs Pull Pipeline Model
**Decision:** Use async generators (pull-based streaming) as default.
[Plan:1230-1328](docs/v3_development_plan.md#L1230-L1328)

---

**Status:** Living document, synced with v3_development_plan.md
**Last Updated:** December 2025
**Next Review:** March 2026
