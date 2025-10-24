# 🧠 Egregora v2

> **Ultra-simple LLM-powered pipeline: WhatsApp → Blog Posts**

Give the LLM your WhatsApp messages. It decides what's worth writing, creates posts with full metadata, and saves them. That's it.

---

## 🚀 Quick Start

### 1. Install

```bash
pip install egregora
```

### 2. Initialize Site

```bash
egregora init my-blog
cd my-blog
pip install 'mkdocs-material[imaging]'
```

### 3. Process WhatsApp Export

```bash
egregora process \
  --zip_file=whatsapp-export.zip \
  --output=. \
  --timezone='America/Sao_Paulo' \
  --from_date=2025-01-01 \
  --to_date=2025-01-31 \
  --gemini_key=YOUR_KEY
```

### 4. Preview

```bash
mkdocs serve
```

**Done.** Check `posts/` for your blog posts.

## ⚡ What It Does

### The Pipeline

```
WhatsApp ZIP → Parse → Anonymize → Group by Period → Enrich → LLM → Posts
                          ↓                             ↓       ↓
                    Privacy-first              Add context  Editorial control
```

### LLM Has Full Control

The LLM is your editor. It decides:
- ✅ **What's worth writing** (ignores noise automatically)
- ✅ **How many posts** (0-N per period)
- ✅ **All metadata** (title, slug, tags, summary, authors)
- ✅ **Content quality** (editorial judgment)

### Example

**Input:** 100 WhatsApp messages from Jan 1, 2025

**LLM decides:** "2 posts worth creating"

**Output:**
```
output/posts/
├── 2025-01-01-ai-ethics-discussion.md
└── 2025-01-01-weekend-meetup.md
```

Each with full front matter:
```yaml
---
title: AI Ethics Discussion
slug: ai-ethics-discussion
date: 2025-01-01
tags: [AI, ethics, coordination]
summary: Group discusses open AI risks and coordination failures
authors: [a1b2c3d4, e5f6g7h8]
---

# Content here...
```

## 📚 Documentation

**New to Egregora?**
- 📖 [Full Documentation](docs/README.md) - Complete guide
- 🚀 [5-Minute Quickstart](docs/getting-started/quickstart.md) - Your first blog
- 💡 [Core Concepts](docs/getting-started/concepts.md) - How it works

**Key Features:**
- 🔒 [Privacy & Anonymization](docs/features/anonymization.md) - UUID5-based privacy
- ⚙️ [User Commands](docs/features/privacy-commands.md) - Control your data
- ⭐ [Post Ranking](docs/features/ranking.md) - ELO-based quality system
- 🧠 [RAG Enrichment](docs/features/rag.md) - Context-aware posts
- ✏️ [AI Editor](docs/features/editor.md) - Autonomous post improvement

**Reference:**
- 💻 [CLI Reference](docs/reference/cli.md) - All commands
- 🔧 [API Reference](docs/reference/api.md) - Python API
- 🎯 [Configuration](docs/guides/configuration.md) - Customize everything
- 🐛 [Troubleshooting](docs/guides/troubleshooting.md) - Common issues

**For Developers:**
- 🏗️ [Architecture](docs/guides/architecture.md) - System design
- 🤝 [Contributing](docs/contributing/development.md) - Development guide

## 🔒 Privacy-First

- **Automatic anonymization**: All names → UUID5 pseudonyms BEFORE LLM
- **Deterministic**: Same person → same pseudonym (e.g., "João" → `a1b2c3d4`)
- **WhatsApp mentions**: Auto-detected and anonymized
- **Privacy validation**: Scans output for phone numbers
- **Early application**: Real names NEVER reach the LLM
- **User control**: In-chat commands for aliases and opt-out
- **PII detection in media**: LLM automatically scans images, videos, and audio for personally identifiable information (faces, IDs, license plates, addresses, etc.) and removes media containing PII while keeping redacted descriptions

See [Privacy Documentation](docs/features/anonymization.md) for details.

### User Control Commands

Users can control their data directly from WhatsApp:

```
/egregora set alias "Franklin"         - Set display name
/egregora set bio "I love Python"      - Set bio
/egregora set twitter "@franklindev"   - Add social link
/egregora set website "https://..."    - Add website
/egregora remove alias                 - Remove alias
/egregora opt-out                      - Exclude from future posts
/egregora opt-in                       - Rejoin (after opt-out)
```

**Important**: Commands affect **new posts only**. Existing published posts are not modified.

### Removing Your Data from Existing Posts

**Opt-out semantics**: The `/egregora opt-out` command only affects **NEW posts** generated after the command. It does not modify or delete existing published posts.

To remove your content from existing published posts:

1. **Delete published posts containing your content**:
   ```bash
   rm posts/2025-01-15-*.md  # Delete specific posts
   ```

2. **Regenerate affected periods**:
   ```bash
   egregora process \
     --zip_file=export.zip \
     --from_date=2025-01-15 \
     --to_date=2025-01-15 \
     --output=my-blog \
     --gemini_key=YOUR_KEY
   ```
   The regenerated posts will respect your opt-out status.

3. **Or contact the blog administrator** to manually edit/remove your content from posts.

**Why this design?**: Egregora is a pipeline tool for content generation, not a content management system. Opt-out controls future processing. Historical content management (editing, deletion) is handled at the file/site level.

## 📖 Usage

### Initialize New Site

```bash
egregora init my-blog
```

Creates a complete MkDocs site structure with:
- `mkdocs.yml` - Single config source for MkDocs + Egregora
- `docs/` - Documentation pages
- `posts/` - Blog posts directory
- `profiles/` - Author profiles
- `media/` - Images, videos, audio

### Process WhatsApp Export

#### Basic (All Messages)

```bash
egregora process \
  --zip_file=export.zip \
  --output=./my-blog \
  --timezone='America/Sao_Paulo' \
  --gemini_key=YOUR_KEY
```

⚠️ **Warning**: Processing all messages can be expensive. Use date filters for cost control.

#### Date-Filtered (Recommended)

```bash
egregora process \
  --zip_file=export.zip \
  --output=./my-blog \
  --from_date=2025-01-01 \
  --to_date=2025-01-31 \
  --timezone='America/Sao_Paulo' \
  --gemini_key=YOUR_KEY
```

#### Weekly Posts

```bash
egregora process \
  --zip_file=export.zip \
  --output=./my-blog \
  --period=week \
  --timezone='Europe/London' \
  --gemini_key=YOUR_KEY
```

#### Disable Enrichment

```bash
egregora process \
  --zip_file=export.zip \
  --output=./my-blog \
  --enable_enrichment=False \
  --gemini_key=YOUR_KEY
```

#### Debug Mode

```bash
egregora process \
  --zip_file=export.zip \
  --output=./my-blog \
  --debug \
  --gemini_key=YOUR_KEY
```

### Important Flags

- `--timezone` - **Critical**: WhatsApp exports use your phone's local timezone. Without this, messages may be grouped into wrong dates. Find your timezone: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
  - Examples: `America/Sao_Paulo`, `America/New_York`, `Europe/London`
- `--from_date` / `--to_date` - Filter messages by date (YYYY-MM-DD) for cost control
- `--period` - Group by `day` (default), `week`, or `month`
- `--enable_enrichment` - Add URL/media context (default: `True`)

## 🧩 Architecture

### Ultra-Simple Design

```
src/egregora/
├── parser.py          # ZIP → DataFrame
├── anonymizer.py      # Privacy (UUID5)
├── enricher.py        # Media/URL → LLM → Context rows
├── write_post.py      # Save posts with front matter (CMS tool)
├── writer.py          # LLM with write_post tool
├── pipeline.py        # Orchestrate: parse → enrich → write
├── cli.py             # CLI interface
├── privacy.py         # Privacy validation
└── rag/               # Optional RAG (future)
```

**That's it.** ~500 lines of actual code.

### What We Deleted

Compared to "v2 agent-based" we deleted **80%** of the code:

- ❌ CuratorAgent (LLM filters automatically)
- ❌ EnricherAgent (simple function now)
- ❌ WriterAgent (simple function now)
- ❌ ProfilerAgent (unnecessary)
- ❌ Message/Topic/Post classes (work with DataFrames)
- ❌ Tool registry (over-engineered)
- ❌ Agent base classes (complexity)

### Key Insights

1. **LLM decides quality** - Don't filter with dumb heuristics
2. **LLM clusters topics** - Don't overthink with agents
3. **DataFrames all the way** - No object conversions
4. **Enrichment = DataFrame rows** - Add context as data
5. **write_post tool** - LLM as CMS user

## 🛠️ How It Works

### 1. Parse & Anonymize

```python
df = parse_export(zip_file)  # WhatsApp → DataFrame
df = anonymize_dataframe(df)  # Privacy-first
```

### 2. Group by Period

```python
# Daily, weekly, or monthly
periods = group_by_period(df, period="day")
# {"2025-01-01": DataFrame, "2025-01-02": DataFrame, ...}
```

### 3. Enrich (Optional)

```python
# Add URL/media context as new DataFrame rows
enriched = await enrich_dataframe(df, client)

# Original:
# | 10:00 | a1b2c3d4 | Check this https://example.com |

# Enriched:
# | 10:00    | a1b2c3d4 | Check this https://example.com |
# | 10:00:01 | egregora | [URL Context] Article about AI ethics... |
```

### 4. LLM Writes (with write_post tool)

```python
prompt = f"""
You're a blog editor reviewing messages from {date}.

Messages:
{dataframe_as_markdown}

Decide:
- Is this worth writing about?
- How many posts (0-N)?
- What metadata for each?

Use write_post tool to save posts.
"""

# LLM calls write_post 0-N times
await llm.generate(prompt, tools=[write_post])
```

### 5. Output

```
output/
├── posts/
│   ├── 2025-01-01-ai-ethics.md
│   └── 2025-01-01-meetup.md
└── enriched/
    └── 2025-01-01-enriched.csv  (for debugging)
```

## 💡 Philosophy

### Before: Micromanage the LLM

```python
# We decide what's good
filtered = [m for m in messages if len(m) > 15]

# We cluster
topics = cluster_agent.execute(filtered)

# We enrich
enriched = enricher_agent.execute(topics)

# Finally LLM writes
post = writer_agent.execute(enriched)
```

**Problem:** We're treating the LLM like a dumb template engine.

### After: Trust the LLM

```python
# Just give it the data
markdown = dataframe.write_markdown()

# LLM does everything
posts = llm.generate(f"Write posts from:\n{markdown}", tools=[write_post])
```

**Key:** The LLM is smarter than our heuristics. Let it decide.

## 📚 More Information

For complete documentation, see [docs/README.md](docs/README.md).

**Quick Links:**
- [Installation Guide](docs/getting-started/installation.md)
- [Full Quickstart](docs/getting-started/quickstart.md)
- [Architecture Overview](docs/guides/architecture.md)
- [All Features](docs/features/)

## 🤝 Contributing

This is the ultra-simple refactor. Keep it simple. If you're adding complexity, you're doing it wrong.

## 📄 License

MIT

---

**Egregora v2** - Stop overthinking. Let the LLM do its job.
