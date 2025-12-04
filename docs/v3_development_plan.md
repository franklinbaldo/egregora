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

### 1. Privacy as Optional Agent
**V3 doesn't enforce privacy.** Privacy can be added as an optional agent anywhere in the pipeline. Privacy agents don't need to be LLM-based (can use rule-based anonymization).

**Examples:**
```python
# Privacy before enrichment (anonymize raw data)
Raw Feed → PrivacyAgent → EnricherAgent → WriterAgent

# Privacy after enrichment (keep descriptions, anonymize authors)
Raw Feed → EnricherAgent → PrivacyAgent → WriterAgent

# No privacy (trusted/public data)
Raw Feed → EnricherAgent → WriterAgent
```

**Why:** Maximum flexibility, composable pipeline, removes core complexity, broader use cases.

### 2. Synchronous-First
The core pipeline and internal interfaces are synchronous (`def`). Concurrency is handled explicitly via `ThreadPoolExecutor` for I/O-bound tasks, never `async`/`await` in core logic.

**Why:** Simpler mental model, better for CLI/library use, no event loop required.

### 3. Atom Compliance
All content is modeled using Atom (RFC 4287) vocabulary: `Entry`, `Document`, `Feed`, `Link`, `Author`. This enables RSS/Atom export and interoperability.

**Why:**
- **Standard vocabulary:** Well-defined semantics, easy integration with feed readers
- **Agent clarity:** Entry gives Agents complete context for each item flowing through Feed
  - Not just raw text, but structured metadata: title, authors, dates, links, categories
  - Agents can reason about metadata, not just content
  - Self-contained units with full provenance and context

**Example - Agent receives structured Entry, not raw text:**
```python
# Agent sees complete context
entry = Entry(
    title="Team standup notes",
    content="Discussed API refactoring...",
    authors=[Author(name="Alice")],
    published=datetime(2024, 12, 4),
    categories=["engineering", "standup"],
    links=[Link(rel="enclosure", href="meeting-recording.mp3", type="audio/mpeg")]
)

# Agent can reason:
# - Who said it? (authors)
# - When? (published)
# - What type of content? (categories)
# - Any attachments? (links)
# - Context for generating output (all metadata available)
```

This structured approach is superior to passing raw strings to Agents.

### 4. ContentLibrary Organization
Documents are organized by type-specific repositories via a `ContentLibrary` facade:
```python
# Posts with media attachments (primary pattern)
post = Document(
    doc_type=DocumentType.POST,
    content="Check out this photo!",
    links=[Link(rel="enclosure", href="file://media/photo.jpg", type="image/jpeg")]
)
library.posts.save(post)

# Optional: Index media files separately for tracking/deduplication
library.media.index(path="media/photo.jpg", metadata={...})

# Other document types
library.profiles.save(profile_doc)
library.journal.save(journal_doc)
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
│ Components: Entry, Document, Feed, Context, Ports           │
│ Ports: Agent, InputAdapter, OutputSink, Repository, etc.    │
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
6. **NEW: Implement PipelineContext for request-scoped state**

#### 1.5 Phase 1 Refinements
Before moving to Phase 2, address these design clarifications:

**Media Handling Strategy (Atom-Compliant):**
Follow Atom RFC 4287's enclosure pattern - media is referenced via Links, not embedded:

```python
# Example: Photo post with media attachment
entry = Entry(
    title="Summer Sunset",
    content="Beautiful sunset at the beach",  # Description/caption
    links=[
        Link(
            rel="enclosure",
            href="file://media/photos/sunset-2024.jpg",  # Path or URL
            type="image/jpeg",  # MIME type
            length=245760  # Size in bytes (optional)
        )
    ]
)
```

**Pattern:**
- Entry/Document `content` = description/caption (text)
- Media file referenced via `Link(rel="enclosure")`
- Link attributes: `href` (path/URL), `type` (MIME), `length` (bytes)
- Actual media file stored in filesystem/object storage

**Enrichment Workflow:**
```python
# 1. Entry arrives with media link but minimal description
entry = Entry(
    title="Photo from vacation",
    content="",  # Empty or minimal
    links=[Link(rel="enclosure", href="http://example.org/photo.jpg", type="image/jpeg")]
)

# 2. EnricherAgent downloads media and processes it
media_path = download_media(entry.links[0].href)
enrichment = enrich_media(media_path)  # Vision model: "Sunset over ocean..."

# 3. Store enrichment result
enrichment_doc = Document(
    doc_type=DocumentType.ENRICHMENT,
    content=enrichment.description,
    metadata={"source_entry_id": entry.id, "model": "gemini-2.0-flash-vision"}
)
library.enrichments.save(enrichment_doc)

# 4. Update entry content directly with enrichment
entry.content = enrichment.description  # "A sunset over the ocean with orange clouds"
```

**Benefits:**
- **Caching:** Process media once, reuse description many times (cheaper/faster)
- **Search/RAG:** Text descriptions are indexable and searchable in vector stores
- **Hybrid approach:** Use enrichment text for quick operations, original file for detailed analysis
- **Fallback:** Works when file unavailable or model doesn't support format
- **Cost optimization:** Not every LLM call needs vision/audio - use cached text when sufficient

**When to use multimodal LLMs directly:**
- Detailed analysis requiring full visual/audio context
- Questions about specific details not captured in enrichment
- Creative tasks needing direct media access (image editing, audio mixing)

**When to use enrichment text:**
- RAG search across large media collections
- Summarization and aggregation tasks
- Cheap/fast operations (filtering, categorization)

**Decision:** `DocumentType.MEDIA` may not be needed - media is Links, not Documents

**Identity Strategy (Hybrid Approach):**
- **Immutable data** (FeedItems, enrichments, vector chunks) → UUIDv5 (content-addressed)
- **Mutable content** (Posts, Profiles) → Semantic IDs (slugs, paths via UrlConvention)
- Rationale: Posts have human-meaningful identity (slug), chunks need deduplication (hash)
- Add `Document.slug` property for mutable types

**Config Loader Hardening:**
- Refactor `EgregoraConfig.load()` to dedicated loader class
- Better error reporting for malformed YAML (line numbers, validation failures)
- Environment variable override support

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

```

**Note:** Privacy is NOT an adapter in V3. Users handle privacy preparation before feeding data to V3.

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

#### 2.4 Output Sinks (Feed → Format Transformation)
Output sinks transform the final Feed into any desired format. Multiple sinks can be used simultaneously.

```python
# egregora_v3/infra/output/mkdocs.py
class MkDocsOutputSink(OutputSink):
    """Generate MkDocs blog: markdown files + navigation."""
    def publish(self, feed: Feed) -> None:
        for entry in feed.entries:
            # Create docs/posts/entry-slug.md
            self._write_markdown(entry)
        # Generate mkdocs.yml navigation
        self._generate_nav(feed)

# egregora_v3/infra/output/atom_xml.py
class AtomXMLOutputSink(OutputSink):
    """Export Atom/RSS XML feed."""
    def publish(self, feed: Feed) -> None:
        xml = feed.to_xml()  # Atom RFC 4287 compliant
        self.path.write_text(xml)

# egregora_v3/infra/output/sqlite.py
class SQLiteOutputSink(OutputSink):
    """Export to SQLite database."""
    def publish(self, feed: Feed) -> None:
        with sqlite3.connect(self.db_path) as conn:
            for entry in feed.entries:
                conn.execute("INSERT INTO entries ...", entry.to_dict())

# egregora_v3/infra/output/csv.py
class CSVOutputSink(OutputSink):
    """Export to CSV files (flat format)."""
    def publish(self, feed: Feed) -> None:
        df = pd.DataFrame([e.to_dict() for e in feed.entries])
        df.to_csv(self.path, index=False)
```

**Multiple Output Formats:**
```python
# Transform final feed into multiple formats simultaneously
output_feed = writer_agent.run(enriched_feed, context)

# Generate blog
mkdocs_sink.publish(output_feed)

# Generate RSS feed
atom_sink.publish(output_feed)

# Export to database
sqlite_sink.publish(output_feed)
```

**Testing:** E2E tests generating actual files, validate structure.

#### 2.5 Privacy Agent (Optional Pipeline Component)
```python
# egregora_v3/infra/agents/privacy.py
class PrivacyAgent:
    """Optional privacy agent - Feed → Feed transformer.

    Not LLM-based - uses rule-based anonymization.
    Can be inserted anywhere in pipeline.
    """

    def __init__(self, namespace: str, strategies: list[PrivacyStrategy]):
        self.namespace = namespace
        self.strategies = strategies  # e.g., AnonymizeAuthors, RedactPII

    def run(self, feed: Feed, context: PipelineContext) -> Feed:
        """Anonymize entries in feed."""
        anonymized_entries = []
        for entry in feed.entries:
            entry = self._anonymize_entry(entry)
            anonymized_entries.append(entry)
        return Feed(entries=anonymized_entries, ...)

    def _anonymize_entry(self, entry: Entry) -> Entry:
        """Apply privacy strategies to entry."""
        # Replace author names with deterministic IDs
        if entry.authors:
            entry.authors = [
                Author(name=self._anonymize_name(a.name))
                for a in entry.authors
            ]
        # Redact PII from content
        entry.content = self._redact_pii(entry.content)
        return entry
```

**Usage Example:**
```python
# Configure pipeline with privacy agent
privacy = PrivacyAgent(
    namespace="my-project",
    strategies=[AnonymizeAuthors(), RedactPII()]
)

# Insert privacy at any point
raw_feed = adapter.read_feed()
anonymized_feed = privacy.run(raw_feed, context)  # Feed → Feed
enriched_feed = enricher.run(anonymized_feed, context)
output_feed = writer.run(enriched_feed, context)
```

**Testing:** Unit tests for privacy strategies, integration tests for Feed transformation.

**Success Criteria:**
- [ ] At least 3 input adapters working (RSS, API, WhatsApp)
- [ ] DuckDB repository with full CRUD + tests
- [ ] LanceDB RAG integration ported from V2
- [ ] MkDocs + AtomXML output sinks functional
- [ ] Privacy utilities documented with examples

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

#### 3.2 Core Agents (Feed → Feed Pattern with Configurable Step Size)
Each agent can configure its own processing step size:

```python
# egregora_v3/engine/agents/enricher.py
class EnricherAgent:
    """Enriches Feed entries: media descriptions, URL metadata."""

    def __init__(self, step_size: int = 10):
        """
        Args:
            step_size: Number of entries to process at once (default: 10)
        """
        self.step_size = step_size

    def run(self, feed: Feed, context: PipelineContext) -> Feed:
        """Transform Feed by enriching entries.

        - Downloads media files from enclosure links
        - Runs vision/audio models to get descriptions
        - Updates entry.content with enrichment
        - Caches results to avoid redundant LLM calls
        """
        enriched_entries = []

        # Process in steps for memory efficiency
        for chunk in batch(feed.entries, self.step_size):
            for entry in chunk:
                # Check cache first
                if cached := context.repository.get_enrichment(entry.id):
                    entry.content = cached.content
                else:
                    # Process media/URLs, update entry.content
                    entry = self._enrich_entry(entry)
                enriched_entries.append(entry)

        return Feed(entries=enriched_entries, ...)

# egregora_v3/engine/agents/writer.py
class WriterAgent:
    """Generates blog posts from enriched entries."""

    def __init__(self, step_size: int = 50):
        """
        Args:
            step_size: Number of entries to aggregate into one post (default: 50)
        """
        self.step_size = step_size

    def run(self, feed: Feed, context: PipelineContext) -> Feed:
        """Transform enriched Feed into output documents.

        Groups entries into steps and generates one post per step.
        Receives entries already enriched by EnricherAgent.
        """
        documents = []

        # Process entries in steps (many entries → one post)
        for step_entries in batch(feed.entries, self.step_size):
            post = self._generate_post(step_entries)  # LLM call
            documents.append(post)

        return Feed(entries=documents, ...)
```

**Key Concept:**
- **Step Size:** Number of entries an agent processes in one iteration
- Different agents have different strategies:
  - `EnricherAgent(step_size=10)`: Process 10 entries at a time
  - `WriterAgent(step_size=50)`: Aggregate 50 entries into 1 post
  - `PrivacyAgent(step_size=100)`: Fast rule-based, larger steps

**Porting Strategy:** Copy V2 agent logic, adapt to **Feed → Feed** pattern.

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

**Pipeline Architecture: Feed Transformations**

The pipeline is a chain of **Feed → Agent → Feed** transformations:

```
Raw Feed (minimal content)
    ↓
EnricherAgent (adds context: media descriptions, URL metadata)
    ↓
Enriched Feed (same entries, enhanced content)
    ↓
WriterAgent (generates posts from enriched entries)
    ↓
Output Feed (final documents)
```

**Key Pattern:**
- Each agent receives a **Feed** as input
- Each agent returns a **Feed** as output
- Database/caching prevents redundant LLM calls (check if entry already enriched)
- Next agent receives already-processed entries
- **Each agent controls its own step_size** for processing:
  - EnricherAgent(step_size=10): Process 10 entries at a time
  - WriterAgent(step_size=50): Aggregate 50 entries into 1 post
  - PrivacyAgent(step_size=100): Fast rule-based processing

**Example - Full Pipeline with Output Transformation:**
```python
# 1. Raw feed from input adapter
raw_feed = adapter.read_feed()  # Entries have minimal content

# 2. Optional: Privacy pass (Feed → Feed)
if config.privacy_enabled:
    raw_feed = privacy_agent.run(raw_feed, context)  # Anonymize authors, redact PII

# 3. Enrichment pass (Feed → Feed)
enriched_feed = enricher_agent.run(raw_feed, context)  # Entries now have descriptions

# 4. Writing pass (Feed → Feed)
output_feed = writer_agent.run(enriched_feed, context)  # Generate blog posts

# 5. Persist to repository (internal storage)
library.save_all(output_feed.entries)

# 6. Transform to desired output formats (Feed → Format)
mkdocs_sink.publish(output_feed)    # Generate blog
atom_sink.publish(output_feed)      # Generate RSS feed
sqlite_sink.publish(output_feed)    # Export to database
```

**Alternative - Privacy after enrichment:**
```python
raw_feed = adapter.read_feed()
enriched_feed = enricher_agent.run(raw_feed, context)
anonymized_feed = privacy_agent.run(enriched_feed, context)  # Keep descriptions, hide authors
output_feed = writer_agent.run(anonymized_feed, context)
```

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

### Property-Based Testing
Use `hypothesis` to verify invariants across random inputs:
- **ID Stability:** Same content → same Document ID (idempotency)
- **Serialization:** Round-trip through JSON preserves data
- **Feed Composition:** Adding entries preserves feed structure
- **Example:** Generate 1000 random Documents, verify `Document.create()` always produces valid UUIDs

### Integration Tests
- **Repository:** Real DuckDB (in-memory)
- **Vector Store:** Real LanceDB (temp directory)
- **Adapters:** Real files (test fixtures)
- **Serialization:** JSON round-trips for all core types (UUID, datetime, Path fields)

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
- Privacy is user's responsibility (V3 provides helpers, not enforcement)

### Migration Guide
Full guide to be written during Phase 3, covering:
- Privacy helpers (extracting V2's anonymization into v3.utils.privacy)
- Config translation
- Custom agent porting
- Data migration
- User responsibility for data preparation

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
