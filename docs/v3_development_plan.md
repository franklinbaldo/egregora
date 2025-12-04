# Egregora V3 Development Plan

> **📋 Strategic Architecture Plan**
>
> This document outlines the roadmap for **Egregora V3**, the next-generation architecture designed for public/privacy-ready data processing. V3 will eventually replace V2, which is optimized for private chat archives.
>
> **Current Status:** Planning phase with core types defined in `src/egregora_v3/core/`. V2 remains the production system (`src/egregora/`).
>
> **Target Timeline:** Alpha in 12 months, feature parity in 24 months.

---

## Project Goal

Build a general-purpose document processing library (`src/egregora_v3`) that supports diverse use cases beyond private chat processing. V3 targets public data sources (RSS feeds, APIs, public archives) and provides a clean, synchronous, modular architecture following Test-Driven Development (TDD).

**Key Differences from V2:**
- **Privacy:** Optional application concern (not core) - V3 assumes data is already privacy-ready
- **Scope:** General-purpose library (not just chat → blog)
- **Architecture:** Strict 4-layer design with enforced dependencies
- **Organization:** ContentLibrary pattern (simpler than AtomPub)

---

## Core Principles

### 1. Public Data First
**V3 assumes data is already privacy-ready or public.** Applications needing anonymization use a composable `PrivacyAdapter` wrapper, not core pipeline logic.

**Why:** Removes UUID mapping overhead, simpler data model, broader use cases.

### 2. Synchronous-First
The core pipeline and internal interfaces are synchronous (`def`). Concurrency is handled explicitly via `ThreadPoolExecutor` for I/O-bound tasks, never `async`/`await` in core logic.

**Why:** Simpler mental model, better for CLI/library use, no event loop required.

### 3. Atom Compliance
All content is modeled using Atom (RFC 4287) vocabulary: `Entry`, `Document`, `Feed`, `Link`, `Author`. This enables RSS/Atom export and interoperability.

**Why:** Standard vocabulary, well-defined semantics, easy integration with feed readers.

### 4. ContentLibrary Organization
Documents are organized by type-specific repositories via a `ContentLibrary` facade:
```python
library.posts.save(post_doc)
library.media.save(media_doc)
library.profiles.save(profile_doc)
```

**Why:** Simpler and more direct than AtomPub's Service/Workspace/Collection hierarchy. AtomPub can be layered on top for HTTP APIs if needed later.

### 5. Strict Layering
Dependencies flow inward only: `Pipeline → Engine → Infra → Core`. The Core layer has zero dependencies on outer layers. Enforced via import linter.

**Why:** Clear separation of concerns, testable in isolation, prevents circular dependencies.

### 6. Protocol-Oriented Design
Infrastructure dependencies are defined as protocols (structural typing), not concrete classes. This enables testing with fakes instead of mocks.

**Why:** Better testability, flexibility, dependency inversion.

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Pipeline (pipeline/)                               │
│ Orchestrates workflow: Ingest → Window → Enrich → Write     │
│ Components: PipelineRunner, WindowingEngine, CLI            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Engine (engine/)                                   │
│ LLM interactions, agents, tools - cognitive processing      │
│ Components: WriterAgent, EnricherAgent, ToolRegistry        │
└─────────────────────────────────────────────────────────────┐
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Infrastructure (infra/)                            │
│ External I/O: adapters, databases, vector stores            │
│ Components: Adapters, DuckDBRepo, LanceDB, OutputSinks      │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Core Domain (core/)                                │
│ Pure domain logic: types, config, protocols                 │
│ Components: Entry, Document, Feed, Ports (NO I/O)           │
└─────────────────────────────────────────────────────────────┘
```

**Dependency Rules (Enforced):**
- Core depends on nothing (pure domain)
- Infra depends on Core only
- Engine depends on Core + Infra
- Pipeline depends on all layers

---

## Implementation Phases

### Phase 1: Core Foundation ✅ ~80% Complete

**Goal:** Define domain model and contracts.

**Status:**
- ✅ Atom types (Entry, Document, Feed, Link, Author, Category)
- ✅ Ports/protocols (DocumentRepository, InputAdapter, OutputSink, VectorStore)
- ✅ ContentLibrary facade (typed repositories)
- ✅ Config stub (EgregoraConfig)
- ⚠️ Partial: Semantic identity (slug-based IDs for posts/media)
- ⚠️ Partial: Test coverage (~60%, target 100%)

**Remaining Work:**
1. Complete semantic identity logic in `Document.create()`
2. Implement `Feed.to_xml()` for Atom feed export
3. Add `documents_to_feed()` aggregation function
4. 100% unit test coverage for all core types
5. Document threading support (RFC 4685 `in_reply_to`)

**Success Criteria:**
- [ ] All core types validated via Pydantic
- [ ] Atom XML serialization working (RSS export)
- [ ] ContentLibrary with all repositories defined
- [ ] Example "Hello World" app (RSS → Documents)

**Timeline:** Q1 2026 (2-3 months)

---

### Phase 2: Infrastructure 🔄 Not Started

**Goal:** Implement adapters and external I/O.

**Components:**

#### 2.1 Input Adapters
```python
# egregora_v3/infra/adapters/rss.py
class RSSAdapter(InputAdapter):
    """Parse RSS/Atom feeds into Entry stream."""
    def read_entries(self) -> Iterator[Entry]: ...

# egregora_v3/infra/adapters/json_api.py
class JSONAPIAdapter(InputAdapter):
    """Generic HTTP JSON API adapter."""
    def read_entries(self) -> Iterator[Entry]: ...

# egregora_v3/infra/adapters/whatsapp.py
class WhatsAppAdapter(InputAdapter):
    """WhatsApp parser (reused from V2)."""
    def read_entries(self) -> Iterator[Entry]: ...

# egregora_v3/infra/adapters/privacy.py
class PrivacyAdapter(InputAdapter):
    """Composable wrapper for anonymization."""
    def __init__(self, upstream: InputAdapter, anonymize: bool = True): ...
```

**Testing:** Contract tests ensuring all adapters return valid Entry objects.

#### 2.2 Document Repository
```python
# egregora_v3/infra/repository/duckdb.py
class DuckDBDocumentRepository(DocumentRepository):
    """DuckDB-backed document storage."""
    def save(self, doc: Document) -> None: ...
    def get(self, doc_id: str) -> Document | None: ...
    def list(self, doc_type: DocumentType | None = None) -> list[Document]: ...
    def delete(self, doc_id: str) -> None: ...
```

**Testing:** Integration tests against real DuckDB (in-memory for CI).

#### 2.3 Vector Store (RAG)
```python
# egregora_v3/infra/rag/lancedb.py
class LanceDBVectorStore(VectorStore):
    """Port from V2 (already synchronous)."""
    def index_documents(self, docs: list[Document]) -> None: ...
    def search(self, query: str, top_k: int = 5) -> list[Document]: ...
```

**Testing:** Port existing V2 tests, adapt to V3 Document model.

#### 2.4 Output Sinks
```python
# egregora_v3/infra/output/mkdocs.py
class MkDocsOutputSink(OutputSink):
    """Generate MkDocs site structure."""
    def publish(self, feed: Feed) -> None: ...

# egregora_v3/infra/output/atom_xml.py
class AtomXMLOutputSink(OutputSink):
    """Export Atom XML feeds."""
    def publish(self, feed: Feed) -> None:
        xml = feed.to_xml()
        self.path.write_text(xml)
```

**Testing:** E2E tests generating actual files, validate structure.

**Success Criteria:**
- [ ] At least 3 input adapters working (RSS, API, WhatsApp)
- [ ] DuckDB repository with full CRUD + tests
- [ ] LanceDB RAG integration ported from V2
- [ ] MkDocs + AtomXML output sinks functional

**Timeline:** Q2-Q3 2026 (6 months)

---

### Phase 3: Cognitive Engine 🔄 Not Started

**Goal:** Port agents from V2 with synchronous API.

**Components:**

#### 3.1 Synchronous LLM Client
```python
# egregora_v3/engine/llm/sync_client.py
class SyncLLMClient:
    """Synchronous wrapper for pydantic-ai agents."""
    def __init__(self, agent: Agent, model: str): ...

    def run(self, prompt: str, deps: Any) -> str:
        """Execute agent synchronously using ThreadPoolExecutor internally."""
        ...
```

**Why:** Pydantic-AI agents can run in threads. V3 core stays sync, concurrency handled internally.

#### 3.2 Core Agents
```python
# egregora_v3/engine/agents/writer.py
def create_writer_agent(model: str) -> Agent:
    """Generate blog posts from entry windows."""
    ...

# egregora_v3/engine/agents/enricher.py
def create_enricher_agent(model: str) -> Agent:
    """Enrich URLs and media with descriptions."""
    ...
```

**Porting Strategy:** Copy V2 agent logic, adapt to V3's Entry/Document types.

#### 3.3 Tools with Dependency Injection
```python
# egregora_v3/engine/tools/search.py
@tool
def search_rag(ctx: RunContext[ContentLibrary], query: str) -> str:
    """Search past documents."""
    docs = ctx.deps.vector_store.search(query)
    return format_results(docs)
```

**Pattern:** Tools receive ContentLibrary as dependency, access typed repositories.

**Success Criteria:**
- [ ] Writer agent generates posts from entries
- [ ] Enricher agent processes URLs and media
- [ ] Tool registry with 5+ tools (search, write, read, etc.)
- [ ] Mock-free testing (use fake dependencies)

**Timeline:** Q3-Q4 2026 (6 months)

---

### Phase 4: Pipeline Orchestration 🔄 Not Started

**Goal:** Assemble full pipeline with CLI.

**Components:**

#### 4.1 Windowing Engine
```python
# egregora_v3/pipeline/windowing.py
class WindowingEngine:
    """Split entry streams into processable windows."""
    def create_windows(
        self,
        entries: Iterator[Entry],
        strategy: WindowStrategy  # time-based, count-based, semantic
    ) -> Iterator[list[Entry]]: ...
```

#### 4.2 Pipeline Runner
```python
# egregora_v3/pipeline/runner.py
class PipelineRunner:
    def __init__(
        self,
        library: ContentLibrary,
        agents: dict[str, Agent],
        config: PipelineConfig
    ): ...

    def run(self, adapter: InputAdapter) -> Feed:
        """Execute full pipeline: Ingest → Window → Enrich → Write → Persist."""
        entries = adapter.read_entries()
        windows = self.windowing.create_windows(entries)

        documents = []
        for window in windows:
            enriched = self.enrich_window(window)
            post = self.writer_agent.generate(enriched)
            documents.append(post)

        feed = documents_to_feed(documents)
        self.library.save_all(documents)
        return feed
```

#### 4.3 CLI
```python
# egregora_v3/cli/main.py
app = typer.Typer()

@app.command()
def init(path: Path):
    """Initialize new V3 site."""
    ...

@app.command()
def write(
    source: Path,
    output: Path,
    config: Path = ".egregora/config.yml"
):
    """Generate documents from source."""
    cfg = load_config(config)
    adapter = resolve_adapter(source)
    runner = PipelineRunner(cfg)
    feed = runner.run(adapter)
    print(f"Generated {len(feed.entries)} documents")
```

**Success Criteria:**
- [ ] Full pipeline working end-to-end (RSS → Blog)
- [ ] CLI with `init`, `write`, `serve` commands
- [ ] Performance benchmarks (compare to V2)
- [ ] E2E tests with real data fixtures

**Timeline:** Q4 2026 - Q1 2027 (6 months)

---

## Testing Strategy

### Unit Tests
- **Core:** Pure Pydantic validation, no I/O
- **Engine:** Agents with mocked LLM responses
- **Infra:** Protocols tested with fakes

### Integration Tests
- **Repository:** Real DuckDB (in-memory)
- **Vector Store:** Real LanceDB (temp directory)
- **Adapters:** Real files (test fixtures)

### E2E Tests
- **Pipeline:** Full run with fake LLM (no API calls)
- **CLI:** Subprocess invocation, validate outputs
- **Performance:** Benchmark against V2 baseline

### Test Coverage Target
- Core: 100%
- Infra: 90%
- Engine: 85%
- Pipeline: 80%

---

## V2 Migration Strategy

### Timeline
1. **Coexistence (6-12 months):** V3 alpha, V2 production
2. **Feature Parity (12-18 months):** V3 beta, V2 maintenance-only
3. **Deprecation (18-24 months):** V3 recommended, V2 sunset warning
4. **Sunset (24+ months):** V3 is "Egregora 2.0", V2 archived

### Migration Tools
```bash
# Config converter
egregora migrate-config v2-config.yml v3-config.yml

# Data importer (preserves history)
egregora import-v2 ./old-site ./new-site

# Compatibility check
egregora doctor --v2-compat
```

### Breaking Changes
- Config format (`.egregora/config.yml` structure)
- CLI flags (`--refresh` becomes `--cache-policy`)
- Output directory structure (ContentLibrary routing)
- Privacy is opt-in via adapter (not automatic)

### Migration Guide
Full guide to be written during Phase 3, covering:
- Adapter wrapping (WhatsApp + PrivacyAdapter)
- Config translation
- Custom agent porting
- Data migration

---

## Success Metrics

### Phase 1 (Core) - Q1 2026
- [ ] 100% test coverage for core types
- [ ] Atom XML export working
- [ ] Example app demonstrates V3 concepts

### Phase 2 (Infra) - Q3 2026
- [ ] 3+ input adapters functional
- [ ] DuckDB + LanceDB integrated
- [ ] 2+ output sinks working

### Phase 3 (Engine) - Q4 2026
- [ ] Writer + Enricher agents ported
- [ ] 5+ tools with dependency injection
- [ ] Mock-free testing achieved

### Phase 4 (Pipeline) - Q1 2027
- [ ] End-to-end pipeline working
- [ ] CLI feature-complete
- [ ] Alpha release published (`egregora_v3 0.1.0`)

### Migration - Q2-Q4 2027
- [ ] V2 apps can run on V3
- [ ] Migration guide published
- [ ] 5+ users successfully migrated
- [ ] V3 becomes default recommendation

---

## Open Questions

### Q1: Multi-workspace Support
**Question:** Should ContentLibrary support multiple workspaces (e.g., "public blog" + "private journal")?

**Proposal:** Pass `workspace_id` to ContentLibrary constructor. Repositories namespace by workspace.

**Decision:** Defer to Phase 3. Start with single workspace.

### Q2: HTTP API
**Question:** Should V3 expose HTTP API (AtomPub protocol)?

**Proposal:** Optional in Phase 4+. ContentLibrary as backend, FastAPI frontend.

**Decision:** Not in MVP. Evaluate after alpha.

### Q3: Async I/O Boundaries
**Question:** Should HTTP clients / DB drivers use async?

**Proposal:** Yes, but wrapped synchronously via `asyncio.run()`. Core stays sync.

**Decision:** Implement during Phase 2, benchmark vs pure sync.

---

## Conclusion

V3 is a strategic evolution targeting broader use cases than V2's private chat focus. By removing privacy as a core constraint and simplifying organization (ContentLibrary vs AtomPub), V3 becomes a general-purpose document processing library.

**Next Steps:**
1. Complete Phase 1 (Core Foundation) - Q1 2026
2. Create example app demonstrating V3 architecture
3. Begin Phase 2 (Infrastructure) implementation
4. Publish alpha release and gather feedback

**Timeline:** 12 months to alpha, 24 months to V2 feature parity.

---

**Status:** Living document, updated quarterly.
**Last Updated:** December 2025
**Next Review:** March 2026
