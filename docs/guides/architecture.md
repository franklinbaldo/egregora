# Architecture Overview

Egregora is built on a **staged pipeline architecture** that processes WhatsApp conversations through distinct, composable phases.

## Design Philosophy

### Core Principle: Trust the LLM

Instead of micromanaging with complex agent hierarchies, we give the LLM complete context and let it make editorial decisions.

**Before (Agent-based):**
```python
# Complex agent orchestration
filtered = filter_agent.execute(messages)
topics = cluster_agent.execute(filtered)
enriched = enricher_agent.execute(topics)
post = writer_agent.execute(enriched)
```
**Problems:** 2000+ lines, over-engineering, treating LLM like a template engine

**After (Staged Pipeline):**
```python
# Simple functional pipeline
markdown = table.to_markdown()
posts = llm.generate(markdown, tools=[write_post])
```
**Benefits:** ~500 lines (80% reduction), clear data flow, LLM has full editorial control

---

## Staged Pipeline Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Ingestion  │ -> │   Privacy   │ -> │ Augmentation│
└─────────────┘    └─────────────┘    └─────────────┘
      ↓                   ↓                   ↓
   Parse ZIP        Anonymize UUIDs     Enrich context
   Extract media    Detect PII          Build profiles
                    Opt-out mgmt

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Knowledge  │ <- │ Generation  │ -> │ Publication │
└─────────────┘    └─────────────┘    └─────────────┘
      ↑                   ↓                   ↓
   RAG Index        LLM Writer           MkDocs Site
   Annotations      Tool Calling         Templates
   Rankings (Elo)   AI Editor
```

### Why Staged Pipeline?

- **Clearer separation**: Each stage has focused responsibility
- **Acknowledges feedback**: RAG indexes posts for future queries
- **Stateful operations**: Knowledge stage maintains persistent data
- **Better maintainability**: Easier to understand and extend than ETL

---

## Pipeline Stages

### 1. Ingestion (`ingestion/`)

**Purpose:** Parse WhatsApp exports into structured Ibis tables

**Components:**
- `parser.py` - WhatsApp `.zip` to Ibis `Table`

**Flow:**
```python
from egregora.ingestion import parse_whatsapp_export

# Parse ZIP export
table = parse_whatsapp_export(
    zip_path,
    timezone="America/New_York"
)

# Returns Ibis Table with schema:
# - timestamp: Timestamp(timezone='UTC', scale=9)
# - date: Date
# - author: String (real names at this stage)
# - message: String
# - original_line: String
# - tagged_line: String
```

**Features:**
- Handles multiple WhatsApp date formats
- Extracts media references (filenames)
- Filters system messages
- Multi-language support
- Lazy evaluation (stays in DuckDB)

**Documentation:**
- Schema: `core/schema.py::MESSAGE_SCHEMA`
- Code: `ingestion/parser.py`

---

### 2. Privacy (`privacy/`)

**Purpose:** Anonymization and PII protection

**Components:**
- `anonymizer.py` - UUID5-based pseudonymization
- `detector.py` - PII detection (phone, email, addresses)

**Critical:** This is the **privacy boundary**. Real names are converted to UUIDs before any LLM interaction.

**Flow:**
```python
from egregora.privacy import anonymize_table

# Before: Real names
# author: "João Silva"

# After: Deterministic UUIDs
anonymized = anonymize_table(table)
# author: "a1b2c3d4"
```

**Anonymization Properties:**
- ✅ **Deterministic**: Same person → same UUID every time
- ✅ **One-way**: Cannot reverse UUID to real name
- ✅ **Case-insensitive**: "John" and "john" get same UUID
- ✅ **Mention handling**: @João Silva → @a1b2c3d4

**PII Detection:**
```python
from egregora.privacy import detect_pii_in_text

# Scans for:
# - Phone numbers (with country codes)
# - Email addresses
# - Street addresses
# - Social security numbers

pii_found = detect_pii_in_text(message)
if pii_found:
    # Automatically redacted
```

**User Opt-out:**
```python
from egregora.privacy import opt_out_users

# Users can exclude themselves via WhatsApp:
# /egregora opt-out

filtered = opt_out_users(table, profiles_dir)
# Removes messages from opted-out authors
```

**Documentation:**
- [Privacy & Anonymization](../features/anonymization.md)
- [User Commands](../features/privacy-commands.md)

---

### 3. Augmentation (`augmentation/`)

**Purpose:** Enrich data with context and metadata (optional)

**Components:**
- `enrichment/` - LLM-powered URL/media descriptions
  - `core.py` - Orchestration
  - `media.py` - Media extraction & replacement
  - `batch.py` - Batch processing utilities
- `profiler.py` - Author profile generation

**Enrichment Flow:**
```python
from egregora.augmentation.enrichment import (
    extract_and_replace_media,
    enrich_table
)

# 1. Extract media from ZIP
table, media_mapping = extract_and_replace_media(
    table, zip_path, docs_dir, posts_dir
)

# 2. Enrich with LLM-generated context
enriched = enrich_table(
    table,
    media_mapping,
    text_batch_client,  # For URLs
    vision_batch_client,  # For images
    cache,
    docs_dir,
    posts_dir
)
```

**Enrichment as Table Rows:**
Instead of metadata, enrichment is added as conversation rows:

```python
# Original message at 10:00
{"timestamp": "10:00", "author": "a1b2c3d4", "message": "Check https://..."}

# Enrichment added at 10:00:01
{"timestamp": "10:00:01", "author": "egregora", "message": "[URL] Article about..."}
```

The LLM sees enrichment inline with original conversation.

**Profiling:**
```python
from egregora.augmentation.profiler import create_or_update_profile

# Generate author profile from conversations
profile = create_or_update_profile(
    author_uuid="a1b2c3d4",
    messages_table=table,
    llm_client=client,
    profiles_dir=profiles_dir
)

# Profile contains:
# - Display name (user-set alias)
# - Bio (user-set or LLM-generated)
# - Writing style analysis
# - Topic preferences
# - Participation stats
```

**Documentation:**
- [Enrichment](../features/rag.md#enrichment)

---

### 4. Knowledge (`knowledge/`)

**Purpose:** Persistent, stateful learning systems

**Components:**
- `rag/` - Retrieval-Augmented Generation
  - `store.py` - DuckDB vector store (HNSW)
  - `embedder.py` - Gemini embeddings
  - `retriever.py` - Index & query
  - `chunker.py` - Document splitting
- `annotations.py` - Conversation metadata
- `ranking/` - Elo-based quality scoring
  - `agent.py` - Comparison agent
  - `elo.py` - Rating calculations
  - `store.py` - DuckDB persistence

**RAG System:**
```python
from egregora.knowledge.rag import VectorStore, query_similar_posts

# Create vector store
store = VectorStore(rag_dir)

# Index a post
store.add_post(
    post_slug="ai-ethics",
    post_title="AI Ethics Discussion",
    content="...",
    embedding=[0.1, 0.2, ...],  # 768-dim vector
)

# Query for context
similar = query_similar_posts(
    query="AI safety",
    store=store,
    top_k=5
)
# Returns: [(post_slug, similarity_score, content), ...]
```

**RAG provides:**
- Context from past discussions
- Consistency across posts
- Thread continuity
- Topic clustering

**Annotations:**
```python
from egregora.knowledge.annotations import AnnotationStore

# Store conversation metadata
store = AnnotationStore(db_path)

# Add annotation
store.add_annotation(
    msg_id="msg_123",
    author="a1b2c3d4",
    commentary="This relates to previous AI safety discussion",
    parent_annotation_id=None  # Threading support
)
```

**Rankings:**
```python
from egregora.knowledge.ranking import compare_posts, get_rankings

# LLM compares posts pairwise
compare_posts(
    post_a="ai-ethics.md",
    post_b="weekend-plans.md",
    llm_client=client,
    store=ranking_store
)

# Get Elo rankings
rankings = get_rankings(store)
# Returns: [(post_id, elo_score, num_comparisons), ...]
```

**Documentation:**
- [RAG Architecture](../features/rag.md)
- [Ranking System](../features/ranking.md)

---

### 5. Generation (`generation/`)

**Purpose:** LLM-powered content creation

**Components:**
- `writer/` - Blog post generation
  - `core.py` - Main orchestration
  - `tools.py` - LLM tool definitions
  - `context.py` - RAG & profile loading
  - `handlers.py` - Tool execution
  - `formatting.py` - Markdown rendering
- `editor/` - Interactive document refinement
  - `agent.py` - RAG-powered editor
  - `document.py` - Document abstraction

**Writer Flow:**
```python
from egregora.generation.writer import write_posts_for_period

# LLM generates 0-N posts
saved_posts = write_posts_for_period(
    table=period_table,
    output_dir=posts_dir,
    date="2025-01-15",
    batch_client=client,
    rag_dir=rag_dir,
    profiles_dir=profiles_dir
)

# LLM makes ALL editorial decisions:
# - What's worth writing about?
# - How many posts to create?
# - How to cluster messages into threads?
# - Title, slug, tags, summary
# - Content quality and style
```

**Tool Calling:**
The LLM has access to tools via function calling:

```python
# Tools defined in writer/tools.py
tools = [
    "write_post",          # Save a blog post
    "read_profile",        # Get author context
    "write_profile",       # Update profile
    "search_media",        # Find images/videos
    "annotate_conversation"  # Add metadata
]

# Example LLM call:
llm.generate(
    messages_markdown,
    tools=tools,
    system_prompt=writer_system_prompt
)

# LLM response:
{
  "name": "write_post",
  "args": {
    "content": "...",
    "metadata": {
      "title": "AI Ethics Discussion",
      "slug": "ai-ethics",
      "tags": ["AI", "ethics"],
      "authors": ["a1b2c3d4", "e5f6g7h8"]
    }
  }
}
```

**Editor:**
```python
from egregora.generation.editor import run_editor_session

# Interactive AI editing
run_editor_session(
    document_path="posts/ai-ethics.md",
    rag_dir=rag_dir,
    llm_client=client,
    user_goal="Improve technical depth"
)

# Editor has access to:
# - RAG for context retrieval
# - Line-level edit operations
# - Meta-LLM for planning
```

**Documentation:**
- [Multi-Post Generation](../features/multi-post.md)
- [Editor](../features/editor.md)

---

### 6. Publication (`publication/`)

**Purpose:** Site scaffolding and output generation

**Components:**
- `site/` - MkDocs project structure
  - `scaffolding.py` - Site initialization
  - `templates/` - Jinja2 templates

**Site Creation:**
```python
from egregora.publication.site import ensure_mkdocs_project

# Create MkDocs project
site_paths = ensure_mkdocs_project(
    site_root=Path("my-blog"),
    group_slug="ai-safety",
    timezone="America/New_York"
)

# Creates:
# - mkdocs.yml (site config)
# - docs/ (documentation)
# - posts/ (blog posts directory)
# - profiles/ (author profiles)
# - media/ (images, videos, etc.)
```

**Templates:**
- `homepage.md.jinja2` - Landing page
- `about.md.jinja2` - About section
- `posts_index.md.jinja2` - Blog index
- `profiles_index.md.jinja2` - Contributors
- `mkdocs.yml.jinja2` - Site configuration

**Documentation:**
- [Configuration](configuration.md)

---

## Orchestration (`orchestration/`)

**Purpose:** Pipeline coordination and CLI

**Components:**
- `pipeline.py` - Main pipeline orchestrator
- `cli.py` - Typer-based CLI
- `logging_setup.py` - Structured logging
- `write_post.py` - Post persistence tool

**Pipeline Orchestration:**
```python
from egregora.orchestration import process_whatsapp_export

# Run full pipeline
process_whatsapp_export(
    zip_path=Path("whatsapp.zip"),
    output_dir=Path("my-blog"),
    timezone="America/New_York",
    period="day",  # or "week", "month"
    enrichment_enabled=True,
    rag_enabled=True,
    gemini_key="..."
)
```

**Pipeline Steps:**
1. **Parse** - Extract from ZIP
2. **Anonymize** - Privacy protection
3. **Extract media** - Pull images/videos from ZIP
4. **Group by period** - Split into chunks (day/week/month)
5. **Process each period:**
   - Enrich with URLs/media (optional)
   - Query RAG for context (optional)
   - Load author profiles
   - Generate posts (LLM with tools)
   - Index posts in RAG
   - Update profiles
6. **Generate site** - Create MkDocs structure

**CLI:**
```bash
# Initialize site
egregora init my-blog

# Process export
egregora process whatsapp.zip --output=my-blog

# Rank posts
egregora rank --site-dir=my-blog

# Edit post
egregora edit posts/ai-ethics.md
```

---

## Core Components (`core/`)

**Purpose:** Shared data structures and schemas

**Components:**
- `models.py` - Domain models (WhatsAppExport, Conversation, Message)
- `schema.py` - Ibis schemas for ephemeral data
- `database_schema.py` - Ibis schemas for persistent tables
- `types.py` - Custom types (GroupSlug, etc.)

**Schemas:**
```python
from egregora.core import database_schema

# Ephemeral (in-memory only, privacy-first)
database_schema.CONVERSATION_SCHEMA

# Persistent (DuckDB tables)
database_schema.RAG_CHUNKS_SCHEMA
database_schema.ANNOTATIONS_SCHEMA
database_schema.ELO_RATINGS_SCHEMA
```

**Why Both?**
- **Ephemeral**: Conversations never persisted (privacy)
- **Persistent**: RAG, annotations, rankings stored in DuckDB

**Benefits:**
- Type safety for transformations
- Documentation of data contracts
- Ibis optimization for vectorized operations
- Validation capabilities

---

## Configuration (`config/`)

**Purpose:** Centralized configuration management

**Components:**
- `model.py` - Gemini model configuration
- `site.py` - Site paths and MkDocs config
- `types.py` - Config data structures

**Model Configuration:**
```python
from egregora.config import ModelConfig

config = ModelConfig(site_config=mkdocs_config)

# Get model for each stage
writer_model = config.get_model("writer")
enricher_model = config.get_model("enricher")
embedding_model = config.get_model("embedding")

# Priority: CLI flag > mkdocs.yml > defaults
```

**Site Configuration:**
All configuration in `mkdocs.yml`:
```yaml
site_name: My AI Blog

plugins:
  - egregora:
      group_slug: ai-safety
      timezone: America/New_York

extra:
  egregora:
    models:
      writer: models/gemini-2.0-flash-exp
      enricher: models/gemini-1.5-flash
    custom_instructions: |
      Focus on technical depth.
```

---

## Utilities (`utils/`)

**Purpose:** Cross-cutting concerns

**Components:**
- `batch.py` - Gemini Batch API client
- `cache.py` - Enrichment caching
- `checkpoints.py` - Pipeline checkpoints
- `genai.py` - Gemini utilities
- `zip.py` - ZIP validation

**Batch Processing:**
```python
from egregora.utils import GeminiBatchClient

client = GeminiBatchClient(api_key="...")

# Batch LLM calls (cost-effective)
responses = client.generate_content(
    requests=[...],
    display_name="Egregora Enrichment"
)
```

**Caching:**
```python
from egregora.utils import EnrichmentCache

cache = EnrichmentCache(cache_dir)

# Cache enrichment results
cache.store("url:https://...", {"markdown": "..."})

# Retrieve cached
result = cache.load("url:https://...")
```

---

## File Structure

### Source Code

```
src/egregora/
├── ingestion/          # Parse WhatsApp exports
│   ├── __init__.py
│   └── parser.py
├── privacy/            # Anonymization & PII
│   ├── __init__.py
│   ├── anonymizer.py
│   └── detector.py
├── augmentation/       # Enrichment & profiling
│   ├── __init__.py
│   ├── enrichment/
│   │   ├── core.py
│   │   ├── media.py
│   │   └── batch.py
│   └── profiler.py
├── knowledge/          # RAG, annotations, rankings
│   ├── __init__.py
│   ├── rag/
│   ├── annotations.py
│   └── ranking/
├── generation/         # LLM writer & editor
│   ├── __init__.py
│   ├── writer/
│   └── editor/
├── publication/        # Site scaffolding
│   ├── __init__.py
│   └── site/
├── core/               # Shared models & schemas
│   ├── __init__.py
│   ├── models.py
│   ├── schema.py
│   ├── database_schema.py
│   └── types.py
├── orchestration/      # CLI & pipeline
│   ├── __init__.py
│   ├── pipeline.py
│   ├── cli.py
│   ├── logging_setup.py
│   └── write_post.py
├── config/             # Configuration
│   ├── __init__.py
│   ├── model.py
│   ├── site.py
│   └── types.py
├── utils/              # Utilities
│   ├── __init__.py
│   ├── batch.py
│   ├── cache.py
│   ├── checkpoints.py
│   ├── genai.py
│   └── zip.py
└── prompts/            # Jinja2 templates
    ├── writer_system.jinja
    ├── enricher_url.jinja
    └── enricher_media.jinja
```

### Output Structure

```
my-blog/
├── mkdocs.yml          # Site + Egregora config
├── docs/               # Documentation pages
├── posts/              # Generated blog posts
│   ├── 2025-01-15-ai-ethics.md
│   └── 2025-01-16-weekend-plans.md
├── profiles/           # Author profiles
│   ├── a1b2c3d4.md
│   └── e5f6g7h8.md
├── media/              # Media files
│   ├── images/
│   ├── videos/
│   └── urls/
├── rag/                # RAG vector store
│   ├── chunks.parquet
│   └── chunks.duckdb
└── rankings/           # Elo rankings
    └── rankings.duckdb
```

---

## Technology Stack

- **Python 3.12+** - Modern Python features
- **Ibis** - DataFrame abstraction
- **DuckDB** - Embedded analytics database
- **DuckDB VSS** - Vector similarity search (HNSW)
- **Google Gemini** - LLM API
- **MkDocs Material** - Static site generator
- **Pydantic** - Data validation
- **Typer** - CLI framework
- **Jinja2** - Template engine
- **uv** - Package management

---

## Performance Characteristics

### Speed
- **Parsing**: ~1000 messages/second
- **Anonymization**: ~10,000 messages/second (vectorized)
- **Enrichment**: ~0.5s per URL (LLM call)
- **Writing**: ~2-5s per period (LLM call)

### Cost (Gemini Flash)
- **Small group** (10-50 msg/day): $0.01-0.05/day
- **Active group** (100-500 msg/day): $0.10-0.50/day
- **Very active** (1000+ msg/day): $1-5/day

### Memory
- **Parsing**: ~10 MB per 10k messages
- **Processing**: ~50 MB per period
- **RAG**: ~12 KB per chunk (in DuckDB)

Very efficient for local machines.

---

## Key Design Decisions

### 1. Staged Pipeline > ETL

**Why:** Better reflects actual workflow
- Acknowledges feedback loops (RAG)
- Separates stateful operations (knowledge)
- Clearer responsibilities per stage

### 2. Ibis Tables All the Way

**Why:** Keep data in DuckDB until absolutely needed
```python
# Lazy evaluation throughout
table = parse_export(zip_file)
table = anonymize_table(table)
table = enrich_table(table, ...)

# Only materialize for LLM prompt
markdown = table.execute().to_markdown()
```

### 3. Enrichment as Table Rows

**Why:** Keep data in same structure
```python
# ✅ Enrichment inline
messages = messages.union(enrichment_rows)

# ❌ NOT separate metadata
# message.enrichment = {...}
```

### 4. write_post Tool (Function Calling)

**Why:** Let LLM decide post boundaries
```python
# ✅ LLM clusters dynamically
llm.generate(messages, tools=[write_post])

# ❌ NOT pre-clustering
# topics = cluster_algorithm(messages)
```

### 5. Privacy Boundary at Parse

**Why:** Never expose PII to LLM
```
Parse → [REAL NAMES] → Anonymize → [UUIDs] → Rest of pipeline
                            ↑
                    Privacy boundary
```

Real names are lost after anonymization. Cannot be recovered.

### 6. Single Config File

**Why:** One source of truth - `mkdocs.yml` contains everything

---

## Data Flow Example

### Input (WhatsApp)
```
10:00 - João Silva: Did you see the AI paper?
10:01 - Maria Santos: Yes! The alignment part is key
10:02 - João Silva: https://example.com/paper
```

### After Ingestion
```python
{"timestamp": "2025-01-15 10:00", "author": "João Silva", "message": "..."}
```

### After Privacy
```python
{"timestamp": "2025-01-15 10:00", "author": "a1b2c3d4", "message": "..."}
```

### After Augmentation
```python
# Original + enrichment
{"timestamp": "10:00", "author": "a1b2c3d4", "message": "..."}
{"timestamp": "10:00:01", "author": "egregora", "message": "[URL] Paper..."}
```

### LLM Input (Markdown)
```markdown
| Time     | Author   | Message                    |
|----------|----------|----------------------------|
| 10:00:00 | a1b2c3d4 | Did you see the AI paper? |
| 10:01:00 | e5f6g7h8 | Yes! The alignment...     |
| 10:00:01 | egregora | [URL] Paper: Scalable...  |
```

### LLM Output (Tool Call)
```json
{
  "name": "write_post",
  "args": {
    "title": "AI Alignment Discussion",
    "slug": "ai-alignment",
    "content": "...",
    "authors": ["a1b2c3d4", "e5f6g7h8"]
  }
}
```

### Final Output
```markdown
---
title: AI Alignment Discussion
slug: ai-alignment
date: 2025-01-15
authors: [a1b2c3d4, e5f6g7h8]
---

# AI Alignment Discussion

The group engaged in a discussion about...
```

---

## Related Documentation

- [Core Concepts](../getting-started/concepts.md)
- [Privacy Model](../features/anonymization.md)
- [RAG System](../features/rag.md)
- [Configuration](configuration.md)
- [API Reference](../reference/api.md)
