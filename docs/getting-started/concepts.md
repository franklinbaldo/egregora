# Core Concepts

Understanding how Egregora works will help you get the most out of it.

## The Pipeline

Egregora follows a simple, linear pipeline:

```
WhatsApp ZIP → Parse → Anonymize → Group → Enrich → LLM → Posts
                          ↓            ↓       ↓       ↓
                    Privacy-first   By date  Context  Editorial
```

Each stage is a pure function operating on a Polars DataFrame. No complex agents, no event sourcing, no microservices.

### 1. Parse

**Input:** WhatsApp export ZIP file
**Output:** Polars DataFrame with columns: `[timestamp, author, message, media]`

The parser handles:
- WhatsApp's text format (multiple languages/date formats)
- Media references
- System messages (joined, left, etc.)
- Special characters and Unicode

**Code:** `src/egregora/parser.py`
**Documentation:** See source code comments

### 2. Anonymize

**Input:** DataFrame with real names
**Output:** DataFrame with UUID5 pseudonyms

**Key features:**
- **Deterministic:** Same person → same UUID every time
- **Case-insensitive:** "João" and "joão" → same UUID
- **Privacy-first:** Happens BEFORE any LLM interaction
- **Mention handling:** WhatsApp @mentions automatically anonymized

**Example:**
```
João Silva → a1b2c3d4
Maria Santos → e5f6g7h8
```

**Code:** `src/egregora/anonymizer.py`
**Documentation:** [Privacy & Anonymization](../features/anonymization.md)

### 3. Group by Period

**Input:** Full DataFrame
**Output:** Dictionary of `{date: DataFrame}` chunks

Messages are grouped by:
- **Day** (default): One chunk per day
- **Week**: One chunk per week (Monday-Sunday)
- **Month**: One chunk per month

This determines how many LLM calls you'll make.

**Example:**
```python
{
    "2025-01-01": DataFrame(100 messages),
    "2025-01-02": DataFrame(150 messages),
    "2025-01-03": DataFrame(80 messages),
}
```

**Code:** `src/egregora/pipeline.py` (grouping logic)

### 4. Enrich (Optional)

**Input:** DataFrame chunk
**Output:** DataFrame with added context rows

The enricher adds context for:
- **URLs:** Fetches page content, summarizes with LLM
- **Media:** OCR for images, transcription for audio (future)

Enrichment is added as **new DataFrame rows** with author `egregora`:

```markdown
| timestamp | author   | message                     |
|-----------|----------|----------------------------|
| 10:00:00  | a1b2c3d4 | Check https://example.com  |
| 10:00:01  | egregora | [URL] Article about AI...  |
```

The LLM sees enrichment context alongside original messages.

**Code:** `src/egregora/enricher.py`
**Documentation:** [RAG Enrichment](../features/rag.md)

### 5. LLM Writer

**Input:** Enriched DataFrame + date + profiles
**Output:** 0-N blog posts (LLM decides)

The LLM is given:
- All messages for the period (as markdown table)
- Author profiles
- Custom instructions (optional)
- `write_post` tool (function calling)

**The LLM decides:**
- ✅ What's worth writing about (ignores noise)
- ✅ How many posts (0 to N per day)
- ✅ How to cluster messages into threads
- ✅ Title, slug, tags, summary for each post
- ✅ Content quality and style

**Example:**
```
Input: 100 messages from Jan 15
LLM decision: "2 posts worth creating"

Output:
- posts/2025-01-15-01-ai-ethics.md
- posts/2025-01-15-02-weekend-plans.md
```

**Code:** `src/egregora/writer.py`
**Documentation:** [Multi-Post Generation](../features/multi-post.md)

## Privacy Model

### UUID5 Pseudonyms

Egregora uses **UUID5** for deterministic hashing:

```python
import uuid

NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def anonymize_author(name: str) -> str:
    normalized = name.strip().lower()
    author_uuid = uuid.uuid5(NAMESPACE, normalized)
    return author_uuid.hex[:8]  # First 8 chars
```

**Properties:**
- ✅ Same input → same output
- ✅ One-way (can't reverse UUID → name)
- ✅ Collision-resistant (namespace-based)

### When Anonymization Happens

```
Parse → [REAL NAMES] → Anonymize → [UUIDS ONLY] → Rest of pipeline
                            ↑
                    Privacy boundary
                    (No PII beyond here)
```

**Critical:** Real names NEVER reach the LLM.

### User Control

Users can control their data via in-chat commands:

```
/egregora opt-out              # Exclude from future posts
/egregora set alias "Franklin" # Display name (optional)
/egregora set bio "..."        # Profile bio
```

Commands affect **future processing only**. Existing posts are not modified.

**Documentation:** [User Commands](../features/privacy-commands.md)

## Editorial Control (LLM Decision-Making)

### Philosophy: Trust the LLM

Traditional approach (micromanagement):
```python
# We filter
filtered = [m for m in messages if len(m) > 15]

# We cluster
topics = cluster_algorithm(filtered)

# We decide importance
important = [t for t in topics if t.score > 0.7]

# Finally, LLM writes
post = llm.write(important)
```

**Egregora approach (trust):**
```python
# Just give it the data
markdown = dataframe.to_markdown()

# LLM does everything
posts = llm.generate(markdown, tools=[write_post])
```

**Why this works:**
- LLMs are smarter than our heuristics
- LLMs understand context we'd miss
- LLMs can make editorial judgments
- No need to overthink with agents

### What the LLM Sees

When processing January 15, 2025:

```markdown
**Messages from 2025-01-15:**

| Time  | Author   | Message                                |
|-------|----------|----------------------------------------|
| 09:15 | a1b2c3d4 | Did you see the new AI paper?         |
| 09:17 | e5f6g7h8 | Yes! The part about alignment is key  |
| 09:20 | egregora | [URL] Paper: "Scalable Oversight..." |
| ...   | ...      | ...                                    |

**Author Profiles:**
- a1b2c3d4: Technical background, writes about AI
- e5f6g7h8: Philosophy enthusiast, cares about ethics

**Instructions:**
Review these messages and decide what's worth writing about.
Call write_post for each thread you identify.
```

### What the LLM Outputs

Using function calling, the LLM calls `write_post`:

```json
{
  "name": "write_post",
  "args": {
    "title": "AI Alignment Discussion",
    "slug": "ai-alignment-discussion",
    "content": "---\ntitle: AI Alignment Discussion\ndate: 2025-01-15\ntags: [AI, ethics]\n...",
    "authors": ["a1b2c3d4", "e5f6g7h8"]
  }
}
```

The tool saves the post to disk with proper formatting.

**Documentation:** [Multi-Post Generation](../features/multi-post.md)

## Post Structure

Every generated post follows this structure:

```markdown
---
title: AI Ethics Discussion
slug: ai-ethics-discussion
date: 2025-01-15
tags: [AI, ethics, coordination]
summary: Group discusses AI alignment and coordination failures
authors: [a1b2c3d4, e5f6g7h8]
---

# AI Ethics Discussion

[LLM-generated content here...]

## Key Points
- Point 1
- Point 2

## Discussion
...

## Media
[Attached images/videos if any]
```

### Front Matter

- `title` - Human-readable title
- `slug` - URL-friendly identifier
- `date` - Post date (YYYY-MM-DD)
- `tags` - Topics/themes
- `summary` - One-sentence description
- `authors` - UUIDs of participants

### Content

LLM-generated markdown following Scott Alexander style:
- Concrete hooks (not abstract)
- Clear section headers
- Quotes from interesting messages
- Balanced perspective

### Media Section

If media was shared on this day:
```markdown
## Mídias Compartilhadas

**Image 1** (shared by a1b2c3d4 at 14:30)
![Description](/media/IMG_1234.jpg)
[Enriched context from LLM...]
```

## How Posts are Named

### Single Post Per Day

```
posts/2025-01-15-ai-discussion.md
```

Format: `{date}-{slug}.md`

### Multiple Posts Per Day

```
posts/2025-01-15-01-ai-alignment.md
posts/2025-01-15-02-weekend-plans.md
posts/2025-01-15-03-book-club.md
```

Format: `{date}-{sequence:02d}-{slug}.md`

The LLM generates the slug based on the thread topic.

## Architecture Philosophy

### What We Deleted

Egregora v2 deleted **80% of the code** by removing:

- ❌ CuratorAgent (LLM filters automatically)
- ❌ EnricherAgent (simple function now)
- ❌ WriterAgent (simple function now)
- ❌ Message/Topic/Post classes (work with DataFrames)
- ❌ Tool registry (over-engineered)
- ❌ Agent base classes (complexity)

**Result:** ~500 lines of actual code.

### Key Design Principles

1. **LLM decides quality** - Don't filter with dumb heuristics
2. **LLM clusters topics** - Don't overthink with algorithms
3. **DataFrames all the way** - No object conversions
4. **Enrichment = DataFrame rows** - Add context as data
5. **write_post tool** - LLM as CMS user

**Documentation:** [Architecture Overview](../guides/architecture.md)

## Configuration

Egregora uses `mkdocs.yml` as the single source of truth:

```yaml
site_name: My Blog
site_url: https://myblog.com

plugins:
  - blog:
      blog_dir: posts
  - egregora:
      group_slug: my-group
      timezone: America/Sao_Paulo

extra:
  egregora:
    custom_instructions: |
      Focus on technical depth.
      Prefer concrete examples over abstract theory.
```

**Documentation:** [Configuration Guide](../guides/configuration.md)

## Next Steps

Now that you understand the concepts:

- [Try the Quickstart](quickstart.md) - Build your first blog
- [Learn about Privacy](../features/anonymization.md) - Deep dive into anonymization
- [Explore Features](../features/ranking.md) - Post ranking, RAG, etc.
- [Read the Architecture](../guides/architecture.md) - System design details
