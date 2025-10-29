# Architecture Overview

Egregora v2 is built on a simple, functional pipeline architecture.

## Design Philosophy

### Before: Micromanage the LLM

Traditional approach with agents:
```python
# We filter
filtered = [m for m in messages if len(m) > 15]

# We cluster
topics = cluster_agent.execute(filtered)

# We enrich
enriched = enricher_agent.execute(topics)

# Finally LLM writes
post = writer_agent.execute(enriched)
```

**Problems:**
- Complex agent hierarchy
- Over-engineering with tool registries
- Treating LLM like a dumb template engine
- 2000+ lines of code for simple task

### After: Trust the LLM

```python
# Just give it the data
markdown = dataframe.to_markdown()

# LLM does everything
posts = llm.generate(markdown, tools=[write_post])
```

**Benefits:**
- ~500 lines of actual code (80% reduction)
- LLM has full editorial control
- Simple, functional pipeline
- Easy to understand and modify

## Pipeline Flow

```
WhatsApp ZIP
    ↓
  Parse (parser.py)
    ↓
  Anonymize (anonymizer.py)  ← Privacy boundary
    ↓
  Group by Period (pipeline.py)
    ↓
  Enrich (enricher.py)  ← Optional: URLs, media, RAG
    ↓
  Write Posts (writer.py)  ← LLM with write_post tool
    ↓
  Blog Posts + Profiles
```

### Key Insight

**The LLM is your editor.** It decides:
- ✅ What's worth writing about
- ✅ How many posts (0-N per period)
- ✅ How to cluster messages into threads
- ✅ Title, slug, tags, summary
- ✅ Content quality and style

We removed all the intermediate agents and just give the LLM the data.

## Components

### 1. Parser (`parser.py`)

**Purpose:** Convert WhatsApp export to a structured Ibis table

**Input:** ZIP file containing `_chat.txt` and media
**Output:** Ibis `Table` with columns `[timestamp, author, message, media, media_metadata]`

**Features:**
- Handles multiple date formats
- Extracts media references
- Filters system messages
- Supports multiple languages

**Documentation:** See code comments in `src/egregora/parser.py`

```python
import ibis
from ibis import memtable
from egregora.parser import parse_export

messages = parse_export(zip_path)
assert isinstance(messages, ibis.expr.types.Table)

# Keep everything lazy until the last responsible moment
first_day = messages.filter(messages.timestamp.date() == "2025-01-01")

# .execute() returns a pandas.DataFrame today when we need interoperability
first_day_pd = first_day.execute()

# Quick experiments without touching disk are easy too
scratch = memtable([
    {"timestamp": "2025-01-01T10:00:00", "author": "Alice", "message": "hi"}
])
```

### 2. Anonymizer (`anonymizer.py`)

**Purpose:** Privacy-first UUID5 pseudonymization

**Input:** Table with real names
**Output:** Table with UUIDs

**How it works:**
```python
def anonymize_author(name: str) -> str:
    normalized = name.strip().lower()
    author_uuid = uuid.uuid5(NAMESPACE, normalized)
    return author_uuid.hex[:8]
```

**Properties:**
- ✅ Deterministic (same person → same UUID)
- ✅ Case-insensitive
- ✅ One-way (can't reverse)
- ✅ Handles WhatsApp mentions

**Documentation:** [Privacy & Anonymization](../features/anonymization.md)

**Critical:** Anonymization happens BEFORE any LLM interaction. Real names never reach the LLM.

### 3. Grouping (`pipeline.py`)

**Purpose:** Split messages into periods for processing

**Input:** Full Table
**Output:** Dictionary of `{date: Table}`

**Grouping strategies:**
- **Day** (default): One chunk per day
- **Week**: Monday-Sunday chunks
- **Month**: Monthly chunks

```python
periods = {
    "2025-01-01": Table(100 messages),
    "2025-01-02": Table(150 messages),
}
```

This determines how many LLM calls you make.

### 4. Enricher (`enricher.py`)

**Purpose:** Add context for URLs and media (optional)

**Input:** Table chunk
**Output:** Table with added context rows

**Enrichment types:**
- **URLs:** Fetch content, summarize with LLM
- **Images:** OCR text extraction (future: vision models)
- **RAG:** Search past posts for related context

**How it works:**
Enrichment is added as new table rows with author `egregora`:

```python
import ibis

enrichment_rows = ibis.memtable([
    {
        "timestamp": "2025-01-01T10:00:01",
        "author": "egregora",
        "message": "[URL] Article about AI...",
        "media": None,
        "media_metadata": None,
    }
])

augmented = chunk.union(enrichment_rows, distinct=False)
```

The LLM sees enrichment context alongside original messages.

**Documentation:** [RAG Enrichment](../features/rag.md)

### 5. Writer (`writer.py`)

**Purpose:** LLM generates blog posts with editorial control

**Input:**
- Table (messages + enrichment)
- Date
- Author profiles
- Custom instructions (optional)

**Output:** 0-N blog posts (LLM decides)

**How it works:**

1. **Prepare prompt** with markdown table of messages
2. **Call LLM** with `write_post` tool (function calling)
3. **LLM calls write_post** 0-N times (one per thread)
4. **Save posts** to disk with front matter

**Example LLM behavior:**
```
Input: 100 messages from Jan 15
LLM decision: "2 posts worth creating"

LLM calls:
write_post(title="AI Ethics", slug="ai-ethics", content="...", authors=[...])
write_post(title="Weekend Plans", slug="weekend-plans", content="...", authors=[...])

Output:
posts/2025-01-15-01-ai-ethics.md
posts/2025-01-15-02-weekend-plans.md
```

**Documentation:** [Multi-Post Generation](../features/multi-post.md)

### 6. Profiler (`profiler.py`)

**Purpose:** Generate and update author profiles

**Input:** Messages + generated posts
**Output:** Markdown profiles for each author

**Profile content:**
- Writing style
- Common topics
- Participation stats
- User-set metadata (alias, bio, links)

**Example profile:**
```markdown
# Profile: a1b2c3d4

## Display Preferences
- Alias: "Franklin" (set on 2025-01-15)

## User Bio
Python enthusiast, data nerd

## Writing Style
[LLM-generated analysis of writing patterns]

## Topics
- AI ethics (15 posts)
- Python programming (10 posts)
```

**Documentation:** [User Commands](../features/privacy-commands.md)

## File Structure

### Source Code

```
src/egregora/
├── parser.py           # WhatsApp → Ibis Table
├── anonymizer.py       # Privacy (UUID5)
├── enricher.py         # URL/media → context
├── writer.py           # LLM → posts
├── pipeline.py         # Orchestrator
├── profiler.py         # Author profiles
├── privacy.py          # Validation (phone numbers, etc.)
├── write_post.py       # Tool for LLM to save posts
├── cli.py              # CLI interface
├── rag/               # RAG system
│   ├── store.py       # DuckDB vector store
│   ├── retriever.py   # Indexing/querying
│   ├── embedder.py    # Gemini embeddings
│   └── chunker.py     # Document chunking
├── ranking/           # ELO ranking system
│   ├── agent.py       # Comparison agent
│   ├── elo.py         # ELO calculations
│   └── store.py       # DuckDB storage
└── editor_agent.py    # Post editing agent
```

**Total:** ~500 lines of core pipeline code

### Output Structure

```
my-blog/
├── mkdocs.yml          # Site + Egregora config
├── docs/              # Documentation pages
├── posts/             # Generated blog posts
│   ├── 2025-01-15-01-ai-ethics.md
│   └── 2025-01-15-02-weekend-plans.md
├── profiles/          # Author profiles
│   ├── a1b2c3d4.md
│   └── e5f6g7h8.md
├── media/             # Uploaded media
├── rag/               # RAG embeddings (Parquet)
│   └── chunks.parquet
└── rankings/          # ELO rankings
    └── rankings.duckdb
```

## What We Deleted

Compared to the agent-based v2 architecture, we deleted:

### ❌ Agent System (700+ lines)

- `CuratorAgent` - LLM now filters automatically
- `EnricherAgent` - Simple function now
- `WriterAgent` - Simple function now
- `ProfilerAgent` - Simple function now
- `Agent` base class - No need for abstraction

### ❌ Data Models (300+ lines)

- `Message` class - Work with Ibis Tables
- `Topic` class - LLM clusters dynamically
- `Post` class - Direct markdown output
- Complex type hierarchies

### ❌ Tool Registry (200+ lines)

- `ToolRegistry` - Over-engineered
- Plugin system - Not needed
- Dynamic tool loading

### ❌ Event Sourcing (500+ lines)

- Event bus
- Event replay
- Snapshots
- Complexity we didn't need

**Total deleted:** ~1700 lines (80% of codebase)
**Remaining:** ~500 lines (actual pipeline)

## Key Design Decisions

### 1. Ibis Tables All the Way

**Why:** Keep everything in DuckDB until we absolutely need a pandas object

```python
# Parse → Table
table = parse_export(zip_file)

# Anonymize → Table
table = anonymize_dataframe(table)

# Enrich → Table (add rows lazily)
table = enrich_dataframe(
    table,
    media_mapping,
    text_batch_client,
    vision_batch_client,
    enrichment_cache,
    docs_dir,
    posts_dir,
)

# Write → Markdown table from pandas (temporary bridge)
pandas_df = table.execute()  # pandas conversion happens here today
markdown = pandas_df.to_markdown(index=False)
```

Benefits:
- Fast vectorial operations (DuckDB + Ibis expressions)
- No serialization/deserialization until the boundary
- Easy to inspect and debug with `.limit().execute()`
- Familiar to data engineers coming from SQL or pandas

### 2. Enrichment as Table Rows

**Why:** Keep data in same structure

Instead of:
```python
# ❌ Separate data structure
message.enrichment = {"url": "...", "content": "..."}
```

We do:
```python
# ✅ Add enrichment as rows
df.append({"author": "egregora", "message": "[URL] ..."})
```

The LLM sees enrichment inline with messages.

### 3. write_post Tool (Function Calling)

**Why:** Let LLM decide post boundaries

Instead of:
```python
# ❌ We decide clustering
topics = cluster_algorithm(messages)
for topic in topics:
    post = llm.write(topic)
```

We do:
```python
# ✅ LLM decides clustering
llm.generate(messages, tools=[write_post])
# LLM calls write_post N times
```

The LLM uses its understanding to segment threads.

### 4. Privacy Boundary at Parse Time

**Why:** Never expose PII to LLM

```
Parse → [REAL NAMES] → Anonymize → [UUIDs] → Rest of pipeline
                            ↑
                    Privacy boundary
```

**Critical:** Real names are lost after anonymization. Cannot be recovered.

### 5. Single Config File (mkdocs.yml)

**Why:** One source of truth

```yaml
site_name: My Blog

plugins:
  - blog
  - egregora:
      group_slug: my-group
      timezone: America/Sao_Paulo

extra:
  egregora:
    custom_instructions: |
      Focus on technical depth.
```

No separate config for Egregora. Everything in `mkdocs.yml`.

**Documentation:** [Configuration Guide](configuration.md)

## Data Flow Example

### Input

WhatsApp export:
```
10:00 - João Silva: Did you see the AI paper?
10:01 - Maria Santos: Yes! The alignment part is key
10:02 - João Silva: https://example.com/paper
10:03 - Pedro Costa: This relates to our discussion last week
```

### After Parse

```python
import ibis

parsed = ibis.memtable([
    {"timestamp": "2025-01-15 10:00", "author": "João Silva", "message": "Did you see..."},
    {"timestamp": "2025-01-15 10:01", "author": "Maria Santos", "message": "Yes! The alignment..."},
    # ... more rows kept lazily in DuckDB
])
```

### After Anonymize

```python
from egregora.anonymizer import anonymize_dataframe

anonymized = anonymize_dataframe(parsed)
```

### After Enrich

```python
enriched = anonymized.union(
    ibis.memtable([
        {
            "timestamp": "2025-01-15 10:02:01",
            "author": "egregora",
            "message": "[URL] Paper: Scalable AI Alignment...",
        }
    ]),
    distinct=False,
)
```

### LLM Input

We call `.execute()` on the table to get a pandas DataFrame before rendering
markdown for the prompt (this is one of the few pandas conversions that still
exist today).

```markdown
**Messages from 2025-01-15:**

| Time     | Author   | Message                              |
|----------|----------|--------------------------------------|
| 10:00:00 | a1b2c3d4 | Did you see the AI paper?           |
| 10:01:00 | e5f6g7h8 | Yes! The alignment part is key      |
| 10:02:00 | a1b2c3d4 | https://example.com/paper           |
| 10:02:01 | egregora | [URL] Paper: Scalable AI Alignment...|
| 10:03:00 | f9g0h1i2 | This relates to our discussion...    |

**Instructions:** Review and decide what's worth writing. Call write_post for each thread.
```

### LLM Output (Function Call)

```json
{
  "name": "write_post",
  "args": {
    "title": "AI Alignment Paper Discussion",
    "slug": "ai-alignment-paper",
    "content": "---\ntitle: AI Alignment Paper Discussion\n...",
    "authors": ["a1b2c3d4", "e5f6g7h8", "f9g0h1i2"]
  }
}
```

### Final Output

```markdown
---
title: AI Alignment Paper Discussion
slug: ai-alignment-paper
date: 2025-01-15
tags: [AI, alignment, papers]
summary: Group discusses new scalable AI alignment paper
authors: [a1b2c3d4, e5f6g7h8, f9g0h1i2]
---

# AI Alignment Paper Discussion

The group engaged in a thoughtful discussion about a new paper
on scalable AI alignment...

[LLM-generated content]
```

## Technology Stack

- **Python 3.11+** - Modern Python features
- **Ibis + DuckDB** - Columnar analytics with lazy tables
- **Google Gemini** - LLM API (2.5 Flash)
- **DuckDB** - Embedded database (RAG, rankings)
- **MkDocs Material** - Static site generator
- **Pydantic** - Data validation
- **Click** - CLI framework

## Performance Characteristics

### Speed

- **Parsing:** ~1000 messages/second
- **Anonymization:** ~10,000 messages/second (vectorized)
- **Enrichment:** ~0.5s per URL (LLM call)
- **Writing:** ~2-5s per day (LLM call)

### Cost (Gemini 2.5 Flash)

- **Input:** ~$0.10 per 1M tokens
- **Output:** ~$0.50 per 1M tokens

**Approximate:**
- Small group (10-50 msg/day): $0.01-0.05/day
- Active group (100-500 msg/day): $0.10-0.50/day
- Very active (1000+ msg/day): $1-5/day

### Memory Usage

- **Parsing:** ~10 MB per 10k messages
- **Processing:** ~50 MB per day
- **RAG:** ~12 KB per chunk (in DuckDB)

Very efficient for local machines.

## Comparison: Before vs After

| Metric | Agent-based v2 | Pipeline v2 (Current) |
|--------|----------------|----------------------|
| Lines of code | ~2000 | ~500 |
| Core concepts | 15+ (agents, tools, events) | 5 (parse, anonymize, enrich, write) |
| Dependencies | 20+ | 10 |
| Complexity | High (event sourcing, tool registry) | Low (functional pipeline) |
| Maintainability | Hard (many abstractions) | Easy (straightforward flow) |
| Performance | Similar | Similar |
| Flexibility | High (pluggable agents) | Medium (simple functions) |
| Debuggability | Hard (event replay needed) | Easy (inspect tables via `.limit().execute()`) |

## Future Directions

### Planned

1. **Incremental RAG** - Only index new posts
2. **Multi-modal enrichment** - Vision models for images
3. **Streaming generation** - Real-time post updates
4. **Quality metrics** - Automated post scoring

### Maybe

- **Plugin system** - Custom enrichment sources
- **Multi-LLM support** - OpenAI, Anthropic, etc.
- **Distributed processing** - Handle millions of messages

**Philosophy:** Only add complexity if absolutely necessary. Keep it simple.

## Related Documentation

- [Core Concepts](../getting-started/concepts.md) - High-level overview
- [Privacy Model](../features/anonymization.md) - Anonymization details
- [RAG System](../features/rag.md) - RAG architecture
- [Configuration](configuration.md) - Setup and config

## Further Reading

- Source code: `src/egregora/`
- Tests: `tests/`
- Examples: `examples/`
