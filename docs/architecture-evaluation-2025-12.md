# Egregora V3 Architecture: Critical Evaluation & Roadmap
**Date:** December 2025
**Status:** Strategic Planning Document
**Context:** Evaluating V3 vision and providing implementation roadmap

---

## Executive Summary

Egregora V3 represents a **strategic architectural shift** to support broader use cases beyond private chat processing. This evaluation clarifies V3's vision, assesses progress, and provides a concrete roadmap for implementation.

**Key Findings:**
- ✅ **V3 is the future** - Designed to eventually replace V2 with broader capabilities
- ✅ **Privacy is not core** - V3 targets public/privacy-ready data (different from V2's private chat focus)
- ✅ **Atom data model is correct** - Entry/Document/Feed provide good foundation
- ⚠️ **AtomPub is too complex** - Service/Workspace/Collection should be simplified (ContentLibrary pattern is better)
- ✅ **Minimal code is intentional** - V3 is in planning phase, not abandoned

**Strategic Direction:**
V3 will overtime replace V2. Current V2 will continue to be supported but eventually deprecated as V3 reaches feature parity.

---

## 1. V2 vs V3: Design Goals

### 1.1 V2 (Current Production)

**Target Use Case:** Private chat archive processing (WhatsApp, Telegram)

**Core Principles:**
- ✅ **Privacy-First:** Anonymization is architectural invariant
- ✅ **Local CLI:** Single-user, local execution
- ✅ **Functional Pipeline:** Ibis/DuckDB transformations
- ✅ **Specific Domain:** Optimized for chat → blog workflow

**Strengths:**
- Production-ready (123 Python files, comprehensive tests)
- Excellent privacy guarantees (anonymization before LLM)
- Fast and efficient (DuckDB + LanceDB)
- Well-documented and actively maintained

**Limitations:**
- Privacy overhead not needed for public data
- Hard-coded assumptions about private data
- Single workspace (one blog per site)
- Not designed as reusable library

### 1.2 V3 (Strategic Vision)

**Target Use Case:** General-purpose document processing for public/privacy-ready data

**Core Principles:**
- ✅ **Public Data First:** Assumes data is already privacy-ready
- ✅ **Library Design:** Reusable components for diverse applications
- ✅ **Atom Compliance:** Native Atom data model (Entry, Feed, Document)
- ✅ **Multi-Workspace:** Support multiple projects/tenants
- ✅ **Clean Architecture:** Strict layering (Core → Infra → Engine → Pipeline)

**Intended Capabilities:**
- Process public RSS feeds, APIs, archives without privacy overhead
- Serve as library for other applications (not just CLI)
- Multi-tenant deployment (different workspaces)
- Simpler for use cases without privacy requirements

**Current Status:**
- Planning phase (6 Python files in `src/egregora_v3/core/`)
- Core types defined (Entry, Document, Feed)
- Ports/protocols sketched (DocumentRepository, OutputSink)
- Implementation pending

---

## 2. Current V3 State Analysis

### 2.1 What Exists

**Location:** `src/egregora_v3/core/` (6 files)

```
src/egregora_v3/core/
├── __init__.py
├── catalog.py          # ContentLibrary facade (simpler than AtomPub)
├── config.py           # Minimal config stub
├── ports.py            # DocumentRepository protocol
└── types.py            # Atom data model (Entry, Document, Feed, Link, Author)
```

**Tests:** `tests/v3/core/` (4 files with basic coverage)

### 2.2 What's Defined in Planning Docs

**`docs/v3_development_plan.md`:**
- 4-layer architecture (Core → Infra → Engine → Pipeline)
- TDD implementation strategy
- Synchronous-first concurrency model
- Phase breakdown (Foundation → Infrastructure → Engine → Pipeline)

**`docs/development/v3-documents.md`:**
- Atom data model RFC
- Document/Entry/Feed type definitions
- AtomPub-style organization (Service/Workspace/Collection)
- Media handling conventions

### 2.3 What's Been Backported to V2

Several V3 concepts have been integrated into V2:
- ✅ **Semantic Identity** (PR #1100): Slugs for posts/media, UUIDs for authors
- ✅ **ContentLibrary facade**: Simplified repository pattern (replaced AtomPub in both V2 and V3)
- ✅ **Atom Threading**: RFC 4685 `in_reply_to` support
- ✅ **Document enrichment**: Parent/child relationships via `parent_id`

**Analysis:** These backports show V3 concepts are valuable and production-ready. They also mean V2 is already moving toward V3 patterns.

---

## 3. Critical Architectural Decisions

### 3.1 Privacy as Application Concern (Not Core)

**V3 Decision:** Privacy is NOT a core architectural invariant.

**Rationale:**
- V3 targets public data (RSS feeds, APIs, public archives)
- Data is assumed to be **already privacy-ready** when it enters V3
- Privacy is user's **responsibility** - V3 provides optional helper utilities
- Removes complexity: No UUID mapping, no reverse lookups, no namespace management

**V3 Approach - Privacy as Responsibility:**
```python
# V2 approach (privacy enforced by core)
Input → [Core Anonymizes] → Pipeline → Output

# V3 approach (privacy is user's responsibility)
from egregora_v3.utils.privacy import anonymize_entry  # Optional helper

for entry in adapter.read_entries():
    # User decides if/how to anonymize
    if entry_needs_privacy(entry):  # User's logic
        entry = anonymize_entry(entry, namespace="my-project")

    # V3 core assumes data is ready
    yield entry
```

**Contract:** V3 says "give me ready-to-use data." How you prepare it is your business.

### 3.2 Atom Data Model (Keep)

**V3 Decision:** Use Atom (RFC 4287) as foundational data model.

**Why Atom?**
- ✅ Standard vocabulary (Entry, Feed, Link, Author, Category)
- ✅ Well-defined semantics for content syndication
- ✅ Supports threading (RFC 4685) and extensions
- ✅ Enables RSS/Atom feed export naturally
- ✅ Common ground for diverse content types

**Implementation:**
```python
# Core types in src/egregora_v3/core/types.py
class Entry(BaseModel):
    id: str
    title: str
    updated: datetime
    content: str | None
    links: list[Link]
    authors: list[Author]
    # ... Atom standard fields

class Document(Entry):
    """Egregora-specific extension of Entry"""
    doc_type: DocumentType
    status: DocumentStatus
    searchable: bool
    url_path: str | None
```

**V2 Alignment:**
V2's `Document` in `data_primitives/document.py` is already Atom-inspired. V3 formalizes this with full Pydantic models and Atom compliance.

### 3.3 AtomPub is Too Complex (Simplify)

**V3 Original Plan:** Service → Workspace → Collection (AtomPub RFC 5023)

**Revised Decision:** Use simpler **ContentLibrary** pattern.

**Why Simplify?**
- ❌ AtomPub's Service/Workspace discovery is overkill for most use cases
- ❌ 3-4 layers of indirection (Service → Workspace → Collection → Repository)
- ✅ ContentLibrary provides direct, typed access: `library.posts.save(doc)`
- ✅ Easier to understand and use
- ✅ Still supports multi-workspace if needed (pass workspace_id to library constructor)

**What to Keep from AtomPub:**
- ✅ Concept of "collections" for organizing documents by type
- ✅ Media handling conventions (Link with rel="enclosure")
- ✅ Atom XML format for feeds

**What to Drop:**
- ❌ Service Document discovery
- ❌ Workspace hierarchy
- ❌ Full AtomPub protocol (unless/until HTTP API is needed)

### 3.4 Synchronous Core (With ThreadPoolExecutor)

**V3 Decision:** Core pipeline is synchronous. Concurrency via ThreadPoolExecutor for I/O.

**Rationale:**
- ✅ Simpler mental model (no async/await in core logic)
- ✅ Better for CLI and library use (no event loop required)
- ✅ ThreadPoolExecutor provides parallelism for I/O-bound tasks (LLM calls, HTTP, disk)
- ✅ Async only at boundaries (HTTP clients, DB drivers)

**V2 Comparison:**
V2 has async workers (BannerWorker, ProfileWorker). V3 would use:
```python
# V3 style
def process_batch(tasks: list[Task]) -> list[Result]:
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_task, t) for t in tasks]
        return [f.result() for f in as_completed(futures)]
```

### 3.5 Strict Layering (Enforced)

**V3 Decision:** 4-layer architecture with dependency rules enforced by tooling.

```
┌─────────────────────────────────────────┐
│ Layer 4: Pipeline (orchestration)       │ ← Coordinates workflow
├─────────────────────────────────────────┤
│ Layer 3: Engine (agents, cognitive)     │ ← LLM interactions, tools
├─────────────────────────────────────────┤
│ Layer 2: Infrastructure (adapters, DB)  │ ← External I/O
├─────────────────────────────────────────┤
│ Layer 1: Core (types, config, ports)    │ ← Pure domain logic
└─────────────────────────────────────────┘
```

**Dependency Rules:**
- Core depends on nothing
- Infrastructure depends on Core
- Engine depends on Core + Infrastructure
- Pipeline depends on all layers

**Enforcement:**
```toml
# pyproject.toml
[tool.import-linter]
[[tool.import-linter.contracts]]
name = "Core has no dependencies"
type = "forbidden"
source_modules = ["egregora_v3.core"]
forbidden_modules = ["egregora_v3.infra", "egregora_v3.engine", "egregora_v3.pipeline"]
```

---

## 4. V3 Implementation Roadmap

### 4.1 Phase 1: Core Foundation (MOSTLY COMPLETE)

**Status:** ✅ ~80% done

**Deliverables:**
- [x] Atom types (Entry, Document, Feed, Link, Author) - `types.py`
- [x] Core config (EgregoraConfig stub) - `config.py`
- [x] Ports/protocols (DocumentRepository, OutputSink) - `ports.py`
- [x] ContentLibrary facade - `catalog.py`
- [ ] **TODO:** Content-addressed ID generation utilities
- [ ] **TODO:** Comprehensive unit tests for all core types

**Next Steps:**
1. Add `document_id()` generation logic (semantic identity + content-addressed fallback)
2. Implement `documents_to_feed()` aggregation function
3. Add Atom XML serialization (`Feed.to_xml()`)
4. Test Pydantic serialization/deserialization

### 4.2 Phase 2: Infrastructure (NOT STARTED)

**Goal:** Implement adapters, repositories, and external I/O.

**Components:**

**2.1 Input Adapters**
```python
# egregora_v3/infra/adapters/rss.py
class RSSAdapter(InputAdapter):
    """Read RSS/Atom feeds into Entry stream."""
    def read_entries(self) -> Iterator[Entry]: ...

# egregora_v3/infra/adapters/api.py
class APIAdapter(InputAdapter):
    """Generic HTTP API adapter."""
    def read_entries(self) -> Iterator[Entry]: ...

# egregora_v3/infra/adapters/whatsapp.py (V2 migration)
class WhatsAppAdapter(InputAdapter):
    """WhatsApp with optional privacy layer."""
    def __init__(self, privacy_enabled: bool = False): ...
```

**2.2 Document Repository**
```python
# egregora_v3/infra/repository/duckdb.py
class DuckDBDocumentRepository(DocumentRepository):
    def save(self, doc: Document) -> None: ...
    def get(self, doc_id: str) -> Document | None: ...
    def list(self, doc_type: DocumentType | None = None) -> list[Document]: ...
```

**2.3 Vector Store (RAG)**
```python
# egregora_v3/infra/rag/lancedb.py
class LanceDBVectorStore(VectorStore):
    def index_documents(self, docs: list[Document]) -> None: ...
    def search(self, query: str, top_k: int = 5) -> list[Document]: ...
```

**2.4 Output Sinks**
```python
# egregora_v3/infra/output/mkdocs.py
class MkDocsOutputSink(OutputSink):
    def publish(self, feed: Feed) -> None: ...

# egregora_v3/infra/output/atom_xml.py
class AtomXMLOutputSink(OutputSink):
    def publish(self, feed: Feed) -> None:
        xml = feed.to_xml()
        self.path.write_text(xml)
```

**Testing Strategy:**
- Unit tests with in-memory fakes
- Integration tests against real DuckDB/LanceDB
- Contract tests to ensure adapters match protocols

### 4.3 Phase 3: Cognitive Engine (NOT STARTED)

**Goal:** LLM interactions, agents, tools.

**Components:**

**3.1 Synchronous LLM Client**
```python
# egregora_v3/engine/llm/client.py
class SyncLLMClient(LLMModel):
    """Synchronous wrapper for pydantic-ai agents."""
    def __init__(self, agent: Agent): ...
    def run(self, prompt: str, deps: Any) -> str: ...
```

**3.2 Core Agents**
```python
# egregora_v3/engine/agents/writer.py
def create_writer_agent(model: str) -> Agent:
    """Post generation agent."""
    ...

# egregora_v3/engine/agents/enricher.py
def create_enricher_agent(model: str) -> Agent:
    """URL/media enrichment agent."""
    ...
```

**3.3 Tools (Dependency Injection)**
```python
# egregora_v3/engine/tools/search.py
@tool
def search_rag(ctx: RunContext[ContentLibrary], query: str) -> str:
    """Search past documents via RAG."""
    docs = ctx.deps.search(query)
    return format_results(docs)
```

**Testing:**
- Mock LLM responses for unit tests
- Real LLM integration tests (gated behind env var)
- Tool contracts with fake dependencies

### 4.4 Phase 4: Pipeline Orchestration (NOT STARTED)

**Goal:** High-level workflows and CLI.

**Components:**

**4.1 Windowing Engine**
```python
# egregora_v3/pipeline/windowing.py
class WindowingEngine:
    def create_windows(
        self,
        entries: Iterator[Entry],
        strategy: WindowStrategy
    ) -> Iterator[list[Entry]]: ...
```

**4.2 Pipeline Runner**
```python
# egregora_v3/pipeline/runner.py
class PipelineRunner:
    def __init__(self, library: ContentLibrary, agents: AgentRegistry): ...

    def run(
        self,
        adapter: InputAdapter,
        config: PipelineConfig
    ) -> Feed:
        # Ingest → Window → Enrich → Write → Persist
        ...
```

**4.3 CLI**
```python
# egregora_v3/cli/main.py
@app.command()
def write(
    source: Path,
    output: Path,
    config: Path = ".egregora/config.yml"
):
    """Generate documents from input source."""
    ...
```

**Testing:**
- E2E tests with test fixtures
- Mock-free E2E (real DuckDB, fake LLM)
- Performance benchmarks

---

## 5. V2 → V3 Migration Strategy

### 5.1 Timeline

**Phase 1: Coexistence (6-12 months)**
- V3 development in parallel
- V2 remains production system
- V3 reaches alpha (basic pipeline working)

**Phase 2: Feature Parity (6-12 months)**
- V3 implements all critical V2 features
- V2 applications can run on V3 with migration layer
- Beta testing of V3 in production scenarios

**Phase 3: Deprecation (6+ months)**
- V3 becomes recommended for new projects
- V2 receives maintenance only (bug fixes, no new features)
- Documentation focuses on V3

**Phase 4: Sunset**
- V2 archived
- Final V2 release with deprecation notice
- V3 is "Egregora 2.0"

### 5.2 Migration Path for V2 Applications

**WhatsApp Chat → Blog (V2's primary use case)**

In V3, this becomes:
```python
# V3 with privacy helpers (user's responsibility)
from egregora_v3 import PipelineRunner
from egregora_v3.infra.adapters import WhatsAppAdapter
from egregora_v3.utils.privacy import anonymize_entry, detect_pii

# User ensures data is privacy-ready before V3 processes it
whatsapp = WhatsAppAdapter("export.zip")

def privacy_ready_entries():
    for entry in whatsapp.read_entries():
        # User's responsibility to anonymize if needed
        anonymized = anonymize_entry(entry, namespace="my-chat")
        # Could also: detect_pii(entry.content) and redact
        yield anonymized

# Run V3 pipeline with ready-to-use data
runner = PipelineRunner(library, agents)
feed = runner.run(privacy_ready_entries(), config)
```

**Key Points:**
- Privacy is user's **responsibility**, not V3's concern
- V3 provides **helper utilities** (anonymize_entry, detect_pii, etc.)
- User decides when/how/if to use privacy helpers
- V3 core assumes data is already ready to use

### 5.3 Code Reuse

**What Can Be Reused from V2:**
- ✅ Agents (Writer, Enricher, Reader) - Port to V3's synchronous API
- ✅ Input adapters (WhatsApp parser) - Reuse directly
- ✅ RAG backend (LanceDB) - Already synchronous
- ✅ Prompts and templates - Copy directly
- ✅ Tests (logic) - Adapt to V3 structure
- ✅ Privacy utilities - Extract as v3.utils.privacy helpers

**What Needs Rewrite:**
- ❌ Pipeline orchestration - V3 has different layering
- ❌ Context/State management - V3 uses ContentLibrary + dependency injection
- ❌ Privacy enforcement - V3 core doesn't enforce, provides utilities instead
- ❌ Configuration - V3 config will differ

### 5.4 Breaking Changes

**For Users:**
- Config file format may change (`.egregora/config.yml` structure)
- CLI flags might differ (`egregora write` signature)
- Output directory structure could change (V3 uses ContentLibrary routing)

**Migration Tools:**
- Config converter: `egregora migrate-config v2-config.yml v3-config.yml`
- Data importer: `egregora import-v2 ./old-site ./new-site`
- Compatibility layer (temporary): `egregora_v3.compat.v2` module

---

## 6. Clarifications on Design Decisions

### 6.1 Why Privacy is Not Core in V3

**Use Case Difference:**
- **V2:** Private WhatsApp chats (MUST anonymize before LLM)
- **V3:** Public RSS feeds, APIs, archives (already public)

**Architectural Benefit:**
- Removes V2's UUID mapping overhead
- Simpler data model (no reverse lookups)
- Users choose privacy level (not forced)
- Core assumes data is ready-to-use

**When Privacy is Needed:**
V3 provides optional helper utilities:
```python
from egregora_v3.utils.privacy import anonymize_entry, detect_pii

# User's responsibility to prepare data
for entry in rss_adapter.read_entries():
    if has_author_names(entry):
        entry = anonymize_entry(entry, namespace="project-x")
    yield entry
```

### 6.2 Why ContentLibrary Over AtomPub

**AtomPub (RFC 5023) is for HTTP APIs:**
- Service Document (GET /service)
- Collection URIs (POST to create entries)
- ETags, caching, authentication

**Egregora V3 is a library/CLI:**
- No HTTP API (currently)
- Direct function calls, not HTTP
- ContentLibrary's `library.posts.save(doc)` is clearer

**Future HTTP API:**
If V3 becomes a server later, implement AtomPub protocol as HTTP layer on top of ContentLibrary. Don't force it into the core now.

### 6.3 Why Atom Compliance Matters

**Benefits:**
- Standard vocabulary (everyone knows what "Entry" means)
- RSS/Atom feed export is trivial
- Interop with feed readers, aggregators
- Well-defined threading model (RFC 4685)

**Implementation:**
- V3 types extend Atom (Entry → Document)
- Add `to_xml()` method for feed export
- Support Atom extensions (Dublin Core, Media RSS)

### 6.4 Why V3 Will Replace V2 (Not Coexist Forever)

**Maintenance Burden:**
Two codebases = double the maintenance.

**Architectural Clarity:**
V3's cleaner architecture benefits all use cases (including V2's).

**Feature Development:**
New features go to V3. V2 stagnates.

**User Confusion:**
"Which version should I use?" → V3 eventually.

**Timeline:**
Not immediate. V2 supported for 1-2 years during transition.

---

## 7. Revised Recommendations

### 7.1 Immediate Actions (This Quarter)

1. **Keep V3 Documentation**
   - `docs/v3_development_plan.md` - Valuable roadmap
   - `docs/development/v3-documents.md` - Atom data model reference
   - Add preface clarifying V3 is future direction (not current implementation)

2. **Update V3 Planning Docs**
   - Mark AtomPub sections as "Simplified to ContentLibrary"
   - Add this evaluation as `docs/architecture-evaluation-2025-12.md`
   - Clarify privacy is application concern, not core

3. **Complete Phase 1 (Core Foundation)**
   - Finish content-addressed ID generation
   - Add Atom XML serialization
   - 100% test coverage for core types

4. **Create V3 Example**
   - Simple "RSS → Posts" application showing V3 vision
   - Demonstrates ContentLibrary, Atom types, synchronous pipeline
   - Proof of concept for V2 migration

### 7.2 Short-term (Next 6 Months)

1. **Implement Phase 2 (Infrastructure)**
   - RSSAdapter (public feed ingestion)
   - DuckDBDocumentRepository
   - LanceDBVectorStore (port from V2)
   - MkDocsOutputSink

2. **Port V2 Agents to V3**
   - Writer agent (sync API)
   - Enricher agent
   - Test with V3 ContentLibrary

3. **Create Privacy Adapter**
   - Extract V2's privacy logic
   - Make it composable wrapper
   - Test with WhatsAppAdapter

4. **Alpha Release**
   - `egregora_v3 0.1.0` (separate package initially)
   - Basic pipeline working (RSS → Blog)
   - CLI with `write` command

### 7.3 Long-term (Next 12-24 Months)

1. **Feature Parity with V2**
   - All input adapters (WhatsApp, Judicial, etc.)
   - Reader agent (ELO ranking)
   - Banner generation
   - Full RAG integration

2. **V2 Migration Tools**
   - Config converter
   - Data importer
   - Compatibility shims

3. **Beta Testing**
   - Real users on V3
   - Performance benchmarks
   - Stability testing

4. **V3 Goes Stable**
   - `egregora 2.0.0` (V3 becomes main package)
   - V2 deprecated
   - Documentation focuses on V3

---

## 8. Success Metrics

### 8.1 Phase 1 Complete
- [ ] All core types have 100% test coverage
- [ ] Atom XML serialization working
- [ ] ContentLibrary with typed repositories
- [ ] Example application (RSS → Blog) demonstrating V3

### 8.2 Phase 2 Complete (Infrastructure)
- [ ] At least 2 input adapters implemented (RSS + one other)
- [ ] DuckDB repository with full CRUD
- [ ] LanceDB RAG integration
- [ ] MkDocs output sink

### 8.3 Phase 3 Complete (Engine)
- [ ] Writer agent ported and working
- [ ] Enricher agent ported
- [ ] Tool registry with dependency injection
- [ ] Mock-free testing possible

### 8.4 Phase 4 Complete (Pipeline)
- [ ] End-to-end pipeline working (Input → Process → Output)
- [ ] CLI with `init`, `write`, `serve` commands
- [ ] Performance matches V2
- [ ] Alpha release published

### 8.5 Migration Complete
- [ ] V2 applications can run on V3 with minimal changes
- [ ] Migration guide published
- [ ] At least 5 users successfully migrated
- [ ] V3 is recommended for new projects

---

## 9. Conclusion

Egregora V3 is a **strategic architectural evolution**, not a rewrite. It builds on V2's successes while addressing its limitations for broader use cases.

**Key Insights:**
1. **V3 is for public/privacy-ready data** - Different target than V2's private chats
2. **Atom provides good foundation** - Standard vocabulary, extensible, interoperable
3. **AtomPub is too complex** - ContentLibrary is simpler and sufficient
4. **Privacy is application concern** - Not forced on all users, composable when needed
5. **V3 will replace V2 overtime** - Migration path exists, but no rush

**Current Status:**
- Planning phase (intentionally minimal code)
- Core types defined and validated through V2 backports
- Clear roadmap for implementation

**Path Forward:**
- Complete Phase 1 (Core) this quarter
- Implement Phase 2 (Infrastructure) in 6 months
- Alpha release within 12 months
- Feature parity and migration within 24 months

V3's design is sound. The minimal code is intentional (planning phase). Now it's time to execute the implementation roadmap.

---

## Appendix A: V3 Architectural Principles

When developing V3, follow these principles:

1. **Public Data Assumed** - Privacy is adapter concern, not core
2. **Atom Compliant** - Use Atom types, support XML export
3. **Simple Over Complex** - ContentLibrary beats AtomPub
4. **Sync Core** - ThreadPoolExecutor for concurrency, not async/await
5. **Strict Layers** - Core → Infra → Engine → Pipeline (enforced)
6. **Protocol-Oriented** - Depend on interfaces, not implementations
7. **Test-Driven** - Write tests before implementation
8. **Library-First** - CLI is thin wrapper over library

---

## Appendix B: V2 Backport Analysis

These V3 concepts are already in V2 production:

| Concept | V3 Plan | V2 Backport | Status |
|---------|---------|-------------|--------|
| Semantic Identity | Slugs for posts/media | PR #1100 (Dec 2025) | ✅ Production |
| ContentLibrary | Simplified repository | `egregora_v3/core/catalog.py` | ✅ Available (optional in V2) |
| Atom Types | Entry/Document/Feed | `egregora_v3/core/types.py` | ⚠️ Defined but not used in V2 |
| Threading | RFC 4685 `in_reply_to` | V2 Document model | ✅ Production |
| Document Enrichment | Parent/child links | `parent_id` field | ✅ Production |
| RAG Policy | `searchable` flag | V2 Document model | ✅ Production |

**Conclusion:** V3 concepts are validated by V2 production use. The design is proven.

---

**End of Document**
