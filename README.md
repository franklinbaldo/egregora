# 🧠 Egregora v2

> **Ultra-simple LLM-powered pipeline: WhatsApp → Blog Posts**

Give the LLM your WhatsApp messages. It decides what's worth writing, creates posts with full metadata, and saves them. That's it.

---

## 🚀 Quick Start

```bash
python run_v2.py process \
  --zip_file=whatsapp-export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY
```

**Done.** Check `./blog/posts/` for your blog posts.

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

## 🔒 Privacy-First

- **Automatic anonymization**: All names → UUID5 pseudonyms BEFORE LLM
- **Deterministic**: Same person → same pseudonym (e.g., "João" → `a1b2c3d4`)
- **WhatsApp mentions**: Auto-detected and anonymized
- **Privacy validation**: Scans output for phone numbers
- **Early application**: Real names NEVER reach the LLM

See [ANONYMIZATION.md](ANONYMIZATION.md) for details.

## 📖 Usage

### Basic

```bash
python run_v2.py process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY
```

### Weekly Posts

```bash
python run_v2.py process \
  --zip_file=export.zip \
  --period=week \
  --gemini_key=YOUR_KEY
```

### Disable Enrichment

```bash
python run_v2.py process \
  --zip_file=export.zip \
  --enable_enrichment=False \
  --gemini_key=YOUR_KEY
```

### Debug Mode

```bash
python run_v2.py process \
  --zip_file=export.zip \
  --debug \
  --gemini_key=YOUR_KEY
```

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

## 📚 Documentation

- [ANONYMIZATION.md](ANONYMIZATION.md) - Privacy implementation
- [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) - Design decisions
- [QUICKSTART_V2.md](QUICKSTART_V2.md) - Detailed guide

## 🤝 Contributing

This is the ultra-simple refactor. Keep it simple. If you're adding complexity, you're doing it wrong.

## 📄 License

MIT

---

**Egregora v2** - Stop overthinking. Let the LLM do its job.
