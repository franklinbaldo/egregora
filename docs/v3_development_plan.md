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

## Design Philosophy

Egregora V3 draws inspiration from the golden age of open, composable feed processing:

### Yahoo Pipes (2007-2015)
The original visual programming environment for RSS/data feeds. Pipes pioneered:
- **Graph-based pipelines** - Drag-and-drop nodes (Fetch, Filter, Sort, Union, Loop)
- **Composable operations** - Complex data transformations without code
- **Declarative flow** - Pipeline structure as visible data
- **Feed in, feed out** - RSS/Atom as universal exchange format

### Google Reader (2005-2013)
The definitive RSS/Atom aggregator that proved feeds could be a universal content layer:
- **Atom/RSS as first-class** - Standardized content model (Entry/Feed)
- **Aggregation at scale** - Unified interface for distributed content
- **State management** - Read/unread, tagging, organization
- **OPML for collections** - Workspace/subscription organization

### V3's Vision: Modern Pipes + Reader

Egregora V3 combines these philosophies for the LLM era:

```
┌─────────────────────────────────────────────────────────────┐
│ Yahoo Pipes (2007)              →  V3 Graph Pipelines       │
│ - Visual node graph             →  Pydantic AI Graph        │
│ - Fetch/Transform/Output        →  Ingest/Process/Publish   │
│ - Composable operators          →  Agents as nodes          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Google Reader (2005)            →  V3 Content Model         │
│ - Atom Entry/Feed primitives    →  Entry/Document/Feed      │
│ - RSS aggregation               →  Multi-source ingestion   │
│ - OPML collections              →  ContentLibrary           │
└─────────────────────────────────────────────────────────────┘

            ↓

    V3 = Pipes + Reader + LLMs

    Graph-based pipelines transforming Atom feeds,
    with AI agents as processing nodes
```

**What this means:**
- **Atom compliance** (Reader) - Entry/Feed as universal content model
- **Graph pipelines** (Pipes) - Composable, declarative transformations
- **Agent nodes** (V3) - LLM-powered processing steps
- **RSS in, RSS out** (Both) - Interoperable with feed ecosystem

**Why it matters:**
1. Proven design patterns (not reinventing the wheel)
2. Familiar mental model for RSS/feed users
3. Interoperability with existing feed ecosystem
4. Graph abstraction enables visual pipeline builders (future)
5. Atom/RSS standard prevents vendor lock-in

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

### 2. Pragmatic Async/Sync - No Dogma
Use `async`/`await` when it provides clear benefits (parallel I/O, LLM calls, streaming). Use sync for pure transformations. No forced patterns - choose what makes sense for each operation.

**Guidelines:**
- **Async for I/O:** LLM calls, HTTP requests, database operations, file I/O
- **Sync for pure transforms:** Data validation, ID generation, XML serialization
- **Async generators:** For streaming large datasets or enabling backpressure
- **Core types stay sync:** Entry, Document, Feed are pure data models (no I/O)

**Why:** Modern Python supports both async and sync well. Fighting async with wrappers adds unnecessary complexity. Use the right tool for each job.

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
│ Graph-based orchestration: Nodes + Edges                    │
│ Components: Graph, PipelineRunner, Batching Utils, CLI      │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Engine (engine/)                                   │
│ LLM interactions, agents, tools - cognitive processing      │
│ Components: WriterAgent, EnricherAgent, ToolRegistry        │
└─────────────────────────────────────────────────────────────┘
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

### Schema Architecture (Updated Dec 2025)

To support efficient storage and "many entries -> same content" deduplication, the persistence schema uses a normalized design:

1.  **`documents` Table:** Stores Entry metadata (`id`, `feed_id`, `title`, `updated`, etc.) but NOT the heavy content body.
2.  **`contents` Table:** Stores unique content blobs, identified by UUIDv5 (hash of content).
3.  **`entry_contents` Table:** Association table linking Entries to Contents.
    *   Enables deduplication: Multiple entries can point to the same content hash.
    *   Enables composition: Future-proofs for entries composed of multiple content blocks.

This separation allows agents to subscribe to feeds and mark entries as read (`agent_read_status` table) without duplicating massive content blobs.

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
6. **Implement PipelineContext** for request-scoped state (used as `RunContext[PipelineContext]` in Pydantic-AI)

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
privacy_agent = PrivacyAgent(
    namespace="egregora-demo",
    strategies=[AnonymizeAuthors(), RedactPII()]
)
feed = privacy_agent.run(raw_feed, context)
```

**Decision:** Privacy is opt-in, not mandatory.

---

### Phase 3: Engine ⚙️ Not Started

**Goal:** Implement LLM-powered agents and tools.

**Components:**
- WriterAgent (Feed → Feed transformer)
- EnricherAgent (Feed → Feed transformer)
- Tool registry and dependency injection
- Prompt templates (Jinja2)

**Testing:** All agents tested with `TestModel` (Pydantic-AI) to avoid live API calls.

**Example:**
```python
from pydantic_ai.models.test import TestModel

async def test_writer_agent_structure():
    test_model = TestModel()
    agent = WriterAgent(model=test_model)
    ...
```

---

### Phase 4: Pipeline 🧬 Not Started

**Goal:** Build graph-based pipeline orchestration.

**Components:**
- Graph runtime (Pydantic AI Graph beta)
- PipelineRunner orchestrating nodes
- CLI commands (`init`, `write`, `serve`)

**Testing:** E2E pipeline tests using fake models/adapters.

---

## Architecture Diagrams

### Layered Architecture
```
┌──────────────┐      ┌────────────┐      ┌──────────────┐      ┌──────────────┐
│  Pipeline    │ ---> │   Engine   │ ---> │  Infra       │ ---> │    Core       │
│ (Graph, CLI) │      │ (Agents)   │      │ (Adapters)   │      │ (Domain)      │
└──────────────┘      └────────────┘      └──────────────┘      └──────────────┘
```

### Example Pipeline (Push vs Pull)

**Pull Model (Chosen):**
```
Input → Privacy? → Enrich → Write → Output
```

**Push Model (Rejected):**
```
Input ↴
Privacy → Enrich → Write → Output
```

**Rationale:** Async generators enable natural pull-based streaming, with optional buffering.

---

## Configuration (Early Draft)

```yaml
# .egregora/config.v3.yml (draft)
debug: false
workspace: "default"

llm:
  provider: openai
  model: gpt-4.2-mini
  temperature: 0.3
  max_tokens: 2000

storage:
  repository: duckdb
  vector_store: lancedb

pipeline:
  batch_size: 10
  privacy_enabled: false
```

---

## Appendix: Additional Insights from Yahoo Pipes

**Operators to Recreate:**
- Fetch (HTTP, RSS)
- Filter (by field, regex)
- Union (merge streams)
- Sort
- Regex rename
- Loop (map)
- Truncate
- Geo (geocode, bounding box)

**Visual Builder Idea:**
- Pydantic Graph nodes rendered to Mermaid
- Drag-and-drop UI (future)
- Export/import pipeline definitions as JSON/YAML

**User Value:**
- No-code feed manipulation
- Reuse/share pipelines
- Educational (learn by example)

---

## Change Log (Chronological)

### 2024-12-15 - Feed → Feed Transformation Rationale (v0.12)
- Treat Agents as Feed → Feed transformers
- Enricher adds media descriptions and metadata
- Writer converts enriched entries to Posts
- Privacy is optional transformation

### 2024-12-12 - Push vs Pull Model (v0.11)
- Favor async generators (pull) over callbacks (push)
- Add `abatch`, `materialize` utilities

### 2024-12-10 - Privacy Reframed (v0.10)
- Privacy as optional agent, not adapter
- Agent receives `Entry` with full context

### 2024-12-05 - Atom Alignment (v0.9)
- Use Atom Entry/Feed as canonical data model
- Support RFC 4685 threading (in_reply_to)

### 2024-12-01 - Initial Draft (v0.8)
- Layered architecture and phases

---

## Roadmap (Quarterly)

- **Q1 2026:** Core completion (Atom export, 100% tests)
- **Q2 2026:** Infra adapters (RSS, JSON API, WhatsApp)
- **Q3 2026:** Repos + vector store (DuckDB, LanceDB)
- **Q4 2026:** Agents (Writer, Enricher) with Pydantic-AI
- **Q1 2027:** Graph pipeline, CLI
- **Q2-Q4 2027:** Migration tools, V2 parity

---

## FAQ

**Q: Is privacy required?**
A: No. V3 assumes input data is already privacy-ready. Privacy can be added via optional agent.

**Q: Why Atom instead of JSON?**
A: Atom provides standardized vocabulary and compatibility with feed readers. JSON serialization is supported, but Atom is canonical.

**Q: Will V2 be deprecated?**
A: Eventually, after V3 reaches parity and migration tools are available.

**Q: How does V3 handle media?**
A: Media is referenced via Links (`rel="enclosure"`), following Atom. Use EnricherAgent to generate descriptions.

**Q: Do I need async everywhere?**
A: No. Use async for I/O-heavy tasks; keep core types sync.

---

## Future Work (Brainstorm)

- Visual pipeline builder (Mermaid → web UI)
- Plugin system for third-party adapters
- Schema registry for adapters (e.g., JSON schema validation)
- Incremental processing (resume from checkpoints)
- Caching layer for LLM responses
- Multi-tenant ContentLibrary
- Observability (OpenTelemetry spans, metrics)
- Live reload for prompts/templates
- Offline mode for fully local processing
- Feature flags for experimental agents

---

## References

- Atom RFC 4287: https://datatracker.ietf.org/doc/html/rfc4287
- Yahoo Pipes (archived): https://en.wikipedia.org/wiki/Yahoo!_Pipes
- Google Reader: https://en.wikipedia.org/wiki/Google_Reader
- Pydantic AI Graph: https://ai.pydantic.dev/graph/beta/

---

## Extended Exploration: Atom-Aligned Content Model

### Atom as Universal Interchange
Atom (RFC 4287) defines a standard vocabulary for web syndication. Using Atom as the internal model ensures compatibility with existing tools and simplifies export/import.

**Key Atom Elements:**
- `feed`: Collection of entries
- `entry`: Individual item with metadata
- `title`, `id`, `updated`, `published`
- `author`, `link`, `category`

**Egregora Mapping:**
- `Entry` maps directly to Atom `entry`
- `Feed` maps to Atom `feed`
- `Document` extends `Entry` with doc_type and metadata
- `ContentLibrary` organizes Documents by type

### Threading (RFC 4685)
Threading allows hierarchical discussions via `in-reply-to` links.

**Example:**
```xml
<entry>
  <id>tag:example.org,2024:1</id>
  <title>Parent Post</title>
  <content>...</content>
  <link rel="in-reply-to" href="tag:example.org,2024:0" />
</entry>
```

V3 should support threading by allowing `Entry` to include `in_reply_to` metadata, enabling conversation trees.

### Semantic Identity
Human-readable identifiers improve UX (slugs), while UUIDv5 ensures content-addressable stability.

**Hybrid ID Approach:**
- Mutable docs: slug-based IDs
- Immutable docs: UUIDv5

### Feed Serialization
Implement `Feed.to_xml()` to produce Atom-compliant XML. Consider using `xml.etree.ElementTree` or `defusedxml` for safety.

**Pseudo-steps:**
1. Create `<feed>` with namespace `http://www.w3.org/2005/Atom`
2. Add required elements: `id`, `title`, `updated`
3. Iterate entries, serialize each to `<entry>`
4. Include links, authors, categories
5. Return `ElementTree.tostring()` as string

### ContentLibrary Pattern
ContentLibrary acts as a facade over multiple repositories, each managing a document type.

**Benefits:**
- Clear separation by doc_type
- Specialized indexing/search per type
- Consistent interface for applications

### Privacy Considerations
Even though privacy is optional, V3 should provide helper utilities:
- PII detectors (regex, ML)
- Redaction/anonymization transformers
- Audit logs for privacy actions

---

## Extended Pipeline Notes

### Pull vs Push Detailed Comparison

**Pull (Async Generators):**
- Natural backpressure
- Stream-based
- Easier composition (`async for`)
- Works with Python's `asyncio`

**Push (Callbacks/Events):**
- Requires event bus or callbacks
- Harder to reason about backpressure
- Less idiomatic in modern Python

**Decision:** Use pull-based streaming as default, allow push adapters if needed.

### Batching Strategies
- Static batch size (configurable)
- Adaptive batching based on latency/cost
- Separate batch sizes per agent (privacy/enrich/write)

### Error Handling
- Retry strategies per node
- Dead-letter queue for failed entries
- Partial failure handling (continue on error)

### Observability
- Metrics: throughput, latency, cost per entry
- Tracing: spans per agent call
- Logging: structured logs with entry IDs

### Performance Targets
- Handle 1M entries/day
- Sub-1s latency per entry for enrichment
- Cost ceiling per 1000 entries

---

## Potential Integrations

- **DuckDB** for local-first analytics
- **LanceDB** for vector search
- **FastAPI** for HTTP API layer
- **MkDocs** for static site generation
- **SQLite** for lightweight persistence
- **S3/MinIO** for media storage
- **Ray/Dask** for distributed processing (future)

---

## Security Considerations

- Validate all input adapters (schema validation)
- Sanitize HTML content in entries
- Use `defusedxml` for XML parsing
- Config-driven allowlists for outbound network calls

---

## Developer Experience (DX)

- Rich CLI with autocomplete and templates
- Hot reload for prompts and templates
- Clear error messages with remediation suggestions
- Sample pipelines and fixtures

---

## Migration Helpers

- Config converter (V2 → V3)
- Data importer with history preservation
- Compatibility checker (`egregora doctor`)

---

## Appendix: Pydantic AI Graph Notes

- Graph nodes are async functions
- Edges can have conditions (predicates)
- State carries context between nodes
- Supports visualization (Mermaid/DOT)
- Beta API - subject to change

---

## Example Graph Definition (Pseudocode)

```python
from pydantic_ai import Graph

class EgregoraGraph:
    def __init__(self):
        self.graph = Graph()
        self.graph.add_node("ingest", self.ingest)
        self.graph.add_node("privacy", self.privacy)
        self.graph.add_node("enrich", self.enrich)
        self.graph.add_node("write", self.write)

        self.graph.add_edge("ingest", "privacy", condition=lambda ctx: ctx.privacy_enabled)
        self.graph.add_edge("ingest", "enrich", condition=lambda ctx: not ctx.privacy_enabled)
        self.graph.add_edge("privacy", "enrich")
        self.graph.add_edge("enrich", "write")

    async def ingest(self, ctx, adapter):
        async for entry in adapter.read_entries():
            yield entry
```

---

## Notes on Testing Philosophy

- Prefer property-based tests for invariants
- Use fake models/tools; avoid network calls
- Snapshot prompts to detect regressions
- Measure performance and cost in CI

---

## Closing

Egregora V3 aims to be the **Pipes + Reader** for the LLM era—composable feed processing with modern AI capabilities. This plan serves as a living document guiding architecture, implementation, and testing.

**Status:** Living document, updated quarterly.
**Last Updated:** December 2025
**Next Review:** March 2026
