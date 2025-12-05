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

#### 3.1 Pydantic-AI Integration

V3 uses Pydantic-AI agents directly for LLM interactions. No wrappers needed.

**Key Features:**
- **Structured output:** Use `result_type=Document` to enforce Atom data model
- **Dependency injection:** Tools access `PipelineContext` via `RunContext`
- **Native async:** Agents are async-native, compose naturally with async generators
- **Type safety:** LLM responses validated as Pydantic models

```python
from pydantic_ai import Agent, RunContext

# Agent with structured output
writer_agent = Agent(
    'google-gla:gemini-2.0-flash',
    result_type=Document,  # Enforces Atom schema at LLM boundary
    system_prompt="Generate blog posts..."
)

# Tool with dependency injection
@tool
async def search_prior_work(
    ctx: RunContext[PipelineContext],
    query: str
) -> str:
    """Search past documents via RAG."""
    docs = await ctx.deps.library.vector_store.search(query, top_k=5)
    return format_results(docs)
```

**Benefits:**
- Invalid LLM outputs rejected before entering pipeline
- Type-safe access to ContentLibrary in tools
- Testable with `TestModel` (no live API calls in tests)

#### 3.2 Core Agents (Streaming with Async Generators)

Agents process entry streams using async generators. Each agent can buffer/batch as needed for efficiency.

```python
# egregora_v3/engine/agents/enricher.py
from pydantic_ai import Agent

class EnricherAgent:
    """Enriches entries: media descriptions, URL metadata."""

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
        # Pydantic-AI agent with structured output
        self.agent = Agent(
            'google-gla:gemini-2.0-flash-vision',
            result_type=Entry,
            system_prompt=self._load_system_prompt()
        )

    async def run(
        self,
        entries: AsyncIterator[Entry],
        context: PipelineContext
    ) -> AsyncIterator[Entry]:
        """Stream enriched entries.

        - Buffers entries for parallel processing
        - Downloads media from enclosure links
        - Runs vision models for descriptions
        - Yields enriched entries immediately
        """
        async for batch in abatch(entries, self.batch_size):
            # Check cache first
            uncached = [
                e for e in batch
                if not await context.library.has_enrichment(e.id)
            ]

            if uncached:
                # Process batch in parallel
                tasks = [self._enrich(entry) for entry in uncached]
                enriched = await asyncio.gather(*tasks)
            else:
                enriched = batch

            # Stream results immediately
            for entry in enriched:
                yield entry

# egregora_v3/engine/agents/writer.py
class WriterAgent:
    """Generates blog posts from enriched entries."""

    def __init__(self, batch_size: int = 50):
        """
        Args:
            batch_size: Number of entries to aggregate into one post
        """
        self.batch_size = batch_size
        # Pydantic-AI agent with structured output
        self.agent = Agent(
            'google-gla:gemini-2.0-flash',
            result_type=Document,  # Enforces Atom schema
            system_prompt=self._load_system_prompt()
        )

    async def run(
        self,
        entries: AsyncIterator[Entry],
        context: PipelineContext
    ) -> AsyncIterator[Document]:
        """Generate documents from entry batches.

        Aggregates N entries into one post. Yields posts as generated.
        """
        async for batch in abatch(entries, self.batch_size):
            # Render prompt from Jinja2 template
            prompt = self.post_template.render(
                entries=batch,
                style=context.config.writing_style,
                previous_posts=await context.library.posts.list(limit=5)
            )

            # Generate post (Pydantic-AI guarantees valid Document)
            result = await self.agent.run(prompt, deps=context)
            yield result.data  # Document instance
```

**Key Concepts:**
- **Streaming:** `AsyncIterator[Entry]` → `AsyncIterator[Entry]` pattern
- **Memory efficient:** Process entries as they arrive, don't materialize entire feed
- **Batching:** Use `abatch()` helper to buffer for parallel LLM calls
- **Composable:** Chain generators like Unix pipes
- **Pydantic-AI integration:** Use `result_type` for structured output validation

**Porting Strategy:** Copy V2 agent logic, wrap in async generator pattern with Pydantic-AI.

#### 3.3 Tools with Dependency Injection

Tools access ContentLibrary and config through `PipelineContext` as `RunContext` dependency.

```python
# egregora_v3/core/context.py
from dataclasses import dataclass

@dataclass
class PipelineContext:
    """Request-scoped state for agent execution."""
    library: ContentLibrary
    config: EgregoraConfig
    request_id: str

# egregora_v3/engine/tools/search.py
from pydantic_ai import RunContext, tool

@tool
async def search_prior_work(
    ctx: RunContext[PipelineContext],
    query: str
) -> str:
    """Search past documents via RAG."""
    docs = await ctx.deps.library.vector_store.search(query, top_k=5)
    return format_results(docs)

@tool
async def get_recent_posts(
    ctx: RunContext[PipelineContext],
    limit: int = 5
) -> str:
    """Get recent posts for context."""
    posts = await ctx.deps.library.posts.list(limit=limit)
    return format_post_summaries(posts)
```

**Pattern:**
- All tools receive `RunContext[PipelineContext]`
- Access repositories via `ctx.deps.library.posts`, `ctx.deps.library.vector_store`, etc.
- Access config via `ctx.deps.config`
- Type-safe dependency injection

#### 3.4 Prompt Management with Jinja2

All agent prompts are managed as **Jinja2 templates** for maintainability and reusability.

**Directory Structure:**
```
src/egregora_v3/engine/
├── agents/
│   ├── writer.py
│   ├── enricher.py
│   └── privacy.py
├── prompts/
│   ├── base.jinja2           # Shared base template
│   ├── writer/
│   │   ├── system.jinja2     # System prompt
│   │   ├── generate_post.jinja2
│   │   └── summarize.jinja2
│   ├── enricher/
│   │   ├── describe_image.jinja2
│   │   ├── describe_audio.jinja2
│   │   └── extract_metadata.jinja2
│   └── privacy/
│       └── detect_pii.jinja2
└── llm/
    └── template_loader.py    # Jinja2 environment
```

**Implementation:**
```python
# egregora_v3/engine/llm/template_loader.py
from jinja2 import Environment, PackageLoader, select_autoescape

# Global template environment
prompt_env = Environment(
    loader=PackageLoader('egregora_v3', 'engine/prompts'),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True
)

# Custom filters for prompts
def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    return dt.strftime(fmt)

prompt_env.filters['datetime'] = format_datetime

# egregora_v3/engine/agents/writer.py
from egregora_v3.engine.llm.template_loader import prompt_env

class WriterAgent:
    def __init__(self, config: AgentConfig):
        # Load templates
        self.system_template = prompt_env.get_template('writer/system.jinja2')
        self.post_template = prompt_env.get_template('writer/generate_post.jinja2')

        # Initialize Pydantic-AI agent with rendered system prompt
        self.agent = Agent(
            'google-gla:gemini-2.0-flash',
            result_type=Document,
            system_prompt=self.system_template.render(
                guidelines=config.writing_guidelines,
                output_format="markdown",
                tone=config.tone
            )
        )

    async def run(
        self,
        entries: AsyncIterator[Entry],
        context: PipelineContext
    ) -> AsyncIterator[Document]:
        """Generate posts from entry batches."""
        async for batch in abatch(entries, self.batch_size):
            # Render prompt from template with context
            prompt = self.post_template.render(
                entries=batch,
                style=context.config.writing_style,
                previous_posts=await context.library.posts.list(limit=5)
            )

            # Execute agent
            result = await self.agent.run(prompt, deps=context)
            yield result.data
```

**Example Template:**
```jinja2
{# engine/prompts/writer/generate_post.jinja2 #}
{% extends "base.jinja2" %}

{% block task %}
Generate a blog post from {{ entries|length }} conversation entries.
{% endblock %}

{% block instructions %}
Writing style: {{ style }}
Target length: 500-1000 words
Format: Markdown with YAML frontmatter
Tone: Informative and engaging

Requirements:
- Extract key themes and insights
- Maintain chronological flow
- Preserve author attributions
- Include relevant media references
{% endblock %}

{% block context %}
## Recent Posts (for style consistency)
{% for post in previous_posts %}
### {{ post.title }}
Published: {{ post.published|datetime }}
{% endfor %}

## Source Entries
{% for entry in entries %}
---
**{{ entry.title }}**
Published: {{ entry.published|datetime }}
{% if entry.authors %}
Authors: {{ entry.authors|map(attribute='name')|join(', ') }}
{% endif %}

{{ entry.content }}

{% if entry.links %}
**Attachments:**
{% for link in entry.links %}
- [{{ link.type }}] {{ link.href }}
{% endfor %}
{% endif %}
{% endfor %}
{% endblock %}
```

**Benefits:**
- ✅ **Separation of concerns** - Prompts separate from code
- ✅ **Version control friendly** - Easy to diff and review prompt changes
- ✅ **Reusability** - Template inheritance and composition
- ✅ **Testing** - Validate rendering independently of LLM calls
- ✅ **Iteration** - Prompt engineers can edit without touching Python
- ✅ **Context injection** - Dynamic data from PipelineContext

**Success Criteria:**
- [ ] Writer agent generates posts from entries using async generators
- [ ] Enricher agent processes URLs and media with parallel batching
- [ ] All agents use Pydantic-AI with `result_type` for structured output
- [ ] Tool registry with 5+ tools using `RunContext[PipelineContext]`
- [ ] Jinja2 template environment configured with all agent prompts
- [ ] Prompt rendering tests at 100% coverage
- [ ] Mock-free testing with `TestModel` (no live API calls)

**Timeline:** Q3-Q4 2026 (6 months)

---

### Phase 4: Pipeline Orchestration 🔄 Not Started

**Goal:** Assemble full pipeline with CLI using graph-based orchestration.

**Pipeline Architecture: Graph-Based (Inspired by Yahoo Pipes)**

> **Note on "Windowing":** V3 does **not** need a separate `Window` abstraction. Grouping is handled by:
> - **Feed** - Semantic collections of entries (what)
> - **Graph structure** - Logical routing and branching (how)
> - **`abatch()` utility** - Mechanical batching for efficiency (implementation detail)
>
> The graph model is sufficient. Agents batch entries internally as needed.

The pipeline is a **directed graph** of processing nodes, following Yahoo Pipes' composable operator model:

```
                    ┌─────────────┐
                    │   Ingest    │  (Input Adapter)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Privacy?   │  (Conditional Node)
                    └─┬─────────┬─┘
                      │         │
         (if enabled) │         │ (if disabled)
                      │         │
              ┌───────▼──┐   ┌──▼────────┐
              │ Privacy  │   │  Enrich   │
              └───────┬──┘   └──┬────────┘
                      │         │
                      └────┬────┘
                           │
                    ┌──────▼──────┐
                    │   Enrich    │  (Media descriptions, metadata)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    Write    │  (Generate posts)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Persist   │  (Save to ContentLibrary)
                    └─────────────┘
```

**Graph-Based Approach (Pydantic AI Graph):**
- **Nodes** = Processing steps (agents, transforms)
- **Edges** = Data flow + conditions
- **Declarative** = Pipeline structure is data
- **Composable** = Subgraphs can be reused
- **Visualizable** = Can generate diagrams
- **Non-linear** = Branching, merging, parallel paths

**Why Graph > Linear Pipeline:**
- ✅ Conditional execution (privacy only when needed)
- ✅ Parallel processing (enrich media + text simultaneously)
- ✅ Clear visualization (see full pipeline structure)
- ✅ Testable (test nodes + flow separately)
- ✅ Reusable (compose subgraphs)
- ✅ Aligns with Pydantic AI architecture

**Example - Graph Pipeline:**
```python
# egregora_v3/pipeline/graph.py
from pydantic_ai import Graph, Node

class EgregoraPipeline:
    """Yahoo Pipes-inspired graph pipeline for Egregora V3."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.graph = Graph()

        # Define nodes (processing steps)
        self.graph.add_node("ingest", self._ingest_node)
        self.graph.add_node("privacy", self._privacy_node)
        self.graph.add_node("enrich", self._enrich_node)
        self.graph.add_node("write", self._write_node)
        self.graph.add_node("persist", self._persist_node)

        # Define edges (data flow with conditions)
        # Conditional branching: privacy if enabled
        self.graph.add_edge(
            "ingest", "privacy",
            condition=lambda ctx: ctx.config.privacy_enabled
        )
        self.graph.add_edge(
            "ingest", "enrich",
            condition=lambda ctx: not ctx.config.privacy_enabled
        )

        # Converge after privacy
        self.graph.add_edge("privacy", "enrich")

        # Linear flow after convergence
        self.graph.add_edge("enrich", "write")
        self.graph.add_edge("write", "persist")

    async def _ingest_node(self, adapter: InputAdapter, ctx) -> AsyncIterator[Entry]:
        """Read entries from adapter."""
        async for entry in adapter.read_entries():
            yield entry

    async def _privacy_node(self, entries: AsyncIterator[Entry], ctx) -> AsyncIterator[Entry]:
        """Optional privacy transformation."""
        async for entry in entries:
            anonymized = await ctx.privacy_agent.run(entry)
            yield anonymized

    async def _enrich_node(self, entries: AsyncIterator[Entry], ctx) -> AsyncIterator[Entry]:
        """Enrich with media descriptions, metadata."""
        async for batch in abatch(entries, ctx.config.batch_size):
            enriched = await asyncio.gather(*[
                ctx.enricher_agent.run(entry) for entry in batch
            ])
            for entry in enriched:
                yield entry

    async def _write_node(self, entries: AsyncIterator[Entry], ctx) -> AsyncIterator[Document]:
        """Generate posts from entry batches."""
        async for batch in abatch(entries, ctx.config.posts_per_batch):
            doc = await ctx.writer_agent.run(batch)
            yield doc

    async def _persist_node(self, documents: AsyncIterator[Document], ctx) -> list[Document]:
        """Save documents to ContentLibrary."""
        saved = []
        async for doc in documents:
            await ctx.library.posts.save(doc)
            saved.append(doc)
        return saved

    async def run(
        self,
        adapter: InputAdapter,
        context: PipelineContext
    ) -> list[Document]:
        """Execute the pipeline graph."""
        return await self.graph.run(
            initial_state={"adapter": adapter},
            context=context
        )

# CLI usage
@app.command()
async def write(source: Path, output: Path, config_path: Path = ".egregora/config.yml"):
    """Generate documents from source using graph pipeline."""
    config = load_config(config_path)
    adapter = resolve_adapter(source)
    context = PipelineContext(
        library=ContentLibrary(config),
        config=config,
        privacy_agent=PrivacyAgent(config.privacy),
        enricher_agent=EnricherAgent(config.enricher),
        writer_agent=WriterAgent(config.writer)
    )

    pipeline = EgregoraPipeline(config)
    documents = await pipeline.run(adapter, context)

    print(f"✓ Generated {len(documents)} documents")
    for doc in documents:
        print(f"  - {doc.title}")

# Sync wrapper for CLI
@app.command()
def write_sync(source: Path, output: Path):
    """Sync CLI wrapper."""
    asyncio.run(write(source, output))
```

**Advanced: Parallel Processing Branches**
```python
# Graph with parallel processing (like Yahoo Pipes' "Union" operator)
class AdvancedPipeline:
    def __init__(self, config):
        self.graph = Graph()

        # Split processing by media type
        self.graph.add_node("ingest", self._ingest)
        self.graph.add_node("filter_text", lambda entries: filter(is_text, entries))
        self.graph.add_node("filter_media", lambda entries: filter(has_media, entries))

        # Parallel enrichment paths
        self.graph.add_node("enrich_text", self._enrich_text)  # Fast, no vision model
        self.graph.add_node("enrich_media", self._enrich_media)  # Slow, needs vision

        # Merge branches
        self.graph.add_node("merge", self._merge_streams)
        self.graph.add_node("write", self._write)

        # Define parallel flow
        self.graph.add_edge("ingest", "filter_text")
        self.graph.add_edge("ingest", "filter_media")
        self.graph.add_edge("filter_text", "enrich_text")
        self.graph.add_edge("filter_media", "enrich_media")
        self.graph.add_edge("enrich_text", "merge")
        self.graph.add_edge("enrich_media", "merge")
        self.graph.add_edge("merge", "write")
```

**Multiple Output Formats:**
```python
# Add output nodes to graph
pipeline.graph.add_node("output_mkdocs", mkdocs_sink.publish)
pipeline.graph.add_node("output_atom", atom_sink.publish)
pipeline.graph.add_node("output_sqlite", sqlite_sink.publish)

# All outputs run in parallel after write
pipeline.graph.add_edge("write", "output_mkdocs")
pipeline.graph.add_edge("write", "output_atom")
pipeline.graph.add_edge("write", "output_sqlite")
```

**Components:**

#### 4.0 Graph Runtime (Pydantic AI Graph)

**Reference:** https://ai.pydantic.dev/graph/beta/

The graph runtime provides:
- **Node execution** - Run async functions as nodes
- **Edge routing** - Conditional data flow between nodes
- **State management** - Pass context through graph
- **Error handling** - Retry and fallback strategies
- **Visualization** - Generate Mermaid/DOT diagrams

This is the foundation for Yahoo Pipes-style composability.

#### 4.1 Batching Utilities

Helper functions for working with async generators:

```python
# egregora_v3/pipeline/utils.py
from typing import AsyncIterator, TypeVar

T = TypeVar('T')

async def abatch(
    stream: AsyncIterator[T],
    size: int
) -> AsyncIterator[list[T]]:
    """Buffer async stream into batches.

    Example:
        async for batch in abatch(entries, size=10):
            # Process 10 entries at a time
            results = await asyncio.gather(*[process(e) for e in batch])
    """
    batch = []
    async for item in stream:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

async def materialize(stream: AsyncIterator[T]) -> list[T]:
    """Collect entire stream into list.

    Use when agent needs full context (e.g., ranking all entries).

    Example:
        all_entries = await materialize(entries)
        ranked = elo_rank(all_entries)
    """
    return [item async for item in stream]

async def afilter(
    stream: AsyncIterator[T],
    predicate: callable
) -> AsyncIterator[T]:
    """Filter async stream.

    Example:
        images_only = afilter(entries, lambda e: has_media(e))
    """
    async for item in stream:
        if predicate(item):
            yield item

async def atake(
    stream: AsyncIterator[T],
    n: int
) -> AsyncIterator[T]:
    """Take first N items from stream.

    Example:
        first_100 = atake(entries, 100)
    """
    count = 0
    async for item in stream:
        if count >= n:
            break
        yield item
        count += 1
```

#### 4.2 CLI
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
- **Engine:** Agents with `TestModel` (Pydantic-AI test utilities)
- **Infra:** Protocols tested with fakes
- **Prompts:** Template rendering validation

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

### Pydantic-AI Testing
All agent tests MUST use `TestModel` or `FunctionModel` - **no live API calls in unit tests**.

```python
from pydantic_ai.models.test import TestModel, FunctionModel

async def test_writer_agent_structure():
    """Verify WriterAgent returns valid Documents."""
    test_model = TestModel()
    agent = WriterAgent(model=test_model)

    # Create test stream
    entries = async_iter([Entry(...), Entry(...)])

    # Collect results
    documents = [doc async for doc in agent.run(entries, context)]

    # Verify structure, not content
    assert all(isinstance(d, Document) for d in documents)
    assert all(d.doc_type == DocumentType.POST for d in documents)
    assert all(d.title and d.content for d in documents)

async def test_enricher_calls_tools():
    """Verify EnricherAgent calls expected tools."""
    # Mock tool responses
    def mock_tool_handler(tool_name: str, **kwargs):
        if tool_name == "describe_image":
            return "A sunset over the ocean"
        return ""

    test_model = FunctionModel(function=mock_tool_handler)
    agent = EnricherAgent(model=test_model)

    entries = async_iter([Entry(links=[Link(rel="enclosure", href="photo.jpg")])])
    enriched = [e async for e in agent.run(entries, context)]

    assert enriched[0].content == "A sunset over the ocean"
```

**Requirements:**
- Deterministic tests (no fuzzy text matching)
- Verify tool calls and structured outputs
- No API keys or live LLM calls required for CI

### Prompt Testing

Validate template rendering and detect unintended prompt changes.

```python
from egregora_v3.engine.llm.template_loader import prompt_env

def test_writer_prompt_renders():
    """Verify writer template renders with valid data."""
    template = prompt_env.get_template('writer/generate_post.jinja2')

    entries = [Entry(id="1", title="Test", content="Content", updated=datetime.now(UTC))]
    prompt = template.render(entries=entries, style="casual", previous_posts=[])

    assert "Test" in prompt
    assert "casual" in prompt
    assert len(prompt) > 100  # Sanity check

def test_all_templates_compile():
    """Ensure all templates compile without syntax errors."""
    templates = [
        'writer/system.jinja2',
        'writer/generate_post.jinja2',
        'enricher/describe_image.jinja2',
    ]

    for name in templates:
        template = prompt_env.get_template(name)
        assert template is not None

def test_prompt_snapshot(snapshot):
    """Detect unintended prompt changes (using syrupy or pytest-snapshot)."""
    template = prompt_env.get_template('writer/generate_post.jinja2')
    prompt = template.render(entries=FIXTURE_ENTRIES, style="casual", previous_posts=[])
    assert prompt == snapshot
```

**Benefits:**
- Catch template syntax errors early
- Detect unintended prompt changes in code review
- Validate rendering with edge cases (empty lists, missing fields)

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

### Q4: Push vs Pull Pipeline Model
**Decision:** **Use async generators (pull-based streaming) as the default pattern.**

**Rationale:**
- V3 adopts pragmatic async approach (no sync dogma)
- Async generators are idiomatic Python for streaming
- Memory efficient for large feeds (1M+ entries)
- Natural composition via async iteration
- Batching via buffering utilities (see Section 4.1)

**Agent Pattern:**
```python
class Agent(Protocol):
    async def run(
        self,
        entries: AsyncIterator[Entry],
        context: PipelineContext
    ) -> AsyncIterator[Entry]:
        """Transform entry stream."""
        ...
```

**Streaming Example:**
```python
# Lazy streaming - process entries as they arrive
class EnricherAgent:
    async def run(
        self,
        entries: AsyncIterator[Entry],
        context: PipelineContext
    ) -> AsyncIterator[Entry]:
        """Stream enriched entries."""
        async for batch in abatch(entries, 10):
            # Process batch in parallel
            tasks = [self._enrich(e) for e in batch]
            enriched = await asyncio.gather(*tasks)

            # Yield immediately
            for entry in enriched:
                yield entry
```

**Materialization When Needed:**
```python
# Agent needing full context (e.g., ranking all entries)
class ReaderAgent:
    async def run(
        self,
        entries: AsyncIterator[Entry],
        context: PipelineContext
    ) -> AsyncIterator[Entry]:
        # Materialize only for this agent
        all_entries = await materialize(entries)
        ranked = self._elo_rank(all_entries)

        # Stream results
        for entry in ranked:
            yield entry
```

**Selective Buffering:**
```python
# Buffer images, stream text
class EnricherAgent:
    async def run(
        self,
        entries: AsyncIterator[Entry],
        context: PipelineContext
    ) -> AsyncIterator[Entry]:
        """Smart buffering by entry type."""
        image_buffer = []

        async for entry in entries:
            if has_media(entry):
                image_buffer.append(entry)

                # Process 10 images in parallel
                if len(image_buffer) >= 10:
                    enriched = await self._enrich_batch(image_buffer)
                    for e in enriched:
                        yield e
                    image_buffer.clear()
            else:
                # Text entries pass through immediately
                yield entry

        # Flush remaining
        if image_buffer:
            enriched = await self._enrich_batch(image_buffer)
            for e in enriched:
                yield e
```

**Benefits:**
- Memory efficient (stream, don't materialize)
- Low latency (start downstream immediately)
- Natural backpressure (slow consumers control rate)
- Composable (`entries |> privacy |> enricher |> writer`)
- Flexible (agents can materialize when needed)

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
