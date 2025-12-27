# Quick Start

This guide will walk you through generating your first blog post from a WhatsApp export in under 5 minutes.

## Prerequisites

- You have installed Python 3.12+ and [uv](https://github.com/astral-sh/uv).
- You have a [Google Gemini API key](https://ai.google.dev/gemini-api/docs/api-key).
- You have created the `eg` alias as described in the [Installation guide](installation.md).

## Step 1: Initialize Your Blog

Create a new blog site:

```bash
eg init my-blog
cd my-blog
```

This creates a minimal MkDocs site structure:

```
my-blog/
├── docs/
│   ├── index.md        # Homepage
│   └── posts/          # Generated blog posts go here
└── .egregora/
    ├── mkdocs.yml      # Site configuration
    └── ...             # Egregora state (databases, cache)
```

## Step 2: Export Your WhatsApp Chat

From your WhatsApp:

1. Open the group or individual chat
2. Tap the three dots (⋮) → **More** → **Export chat**
3. Choose **Without media** (for privacy)
4. Save the `.zip` file

!!! tip
    For privacy, we recommend exporting **without media**. Egregora can enrich URLs and media references using LLMs instead.

## Step 3: Set Your API Key

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

## Step 4: Process the Export

```bash
eg write \
  whatsapp-export.zip \
  --output-dir=. \
  --timezone='America/New_York'
```

This will:

1. Parse the WhatsApp export
2. Anonymize all names (real names never reach the AI)
3. Create conversation windows (default: 1 day per window)
4. Generate blog posts using Gemini

!!! info
    The first run may take a few minutes as it:

    - Builds the LanceDB vector index (for RAG retrieval)
    - Embeds all messages for semantic search
    - Generates multiple blog posts

## Step 5: Preview Your Blog

Launch a local preview server:

```bash
# 'eg serve' is a pass-through to 'mkdocs serve'
eg serve -f .egregora/mkdocs.yml
```

Open [http://localhost:8000](http://localhost:8000) in your browser. 🎉

## What Just Happened?

Egregora processed your chat through multiple stages:

1. **Ingestion**: Parsed WhatsApp `.zip` → structured data in DuckDB
2. **Privacy**: Replaced names with UUIDs (e.g., `john` → `a3f2b91c`)
3. **Enrichment**: (Optional) Enriched URLs/media with descriptions
4. **Knowledge**: Built LanceDB RAG index for retrieving similar past posts
5. **Generation**: Gemini generated 0-N blog posts per window
6. **Publication**: Created markdown files in `docs/posts/`

## Next Steps

### Customize Your Blog

Edit `mkdocs.yml` to change:

- Site name, description, theme
- Navigation structure

Edit `.egregora.toml` to customize:

- Models and parameters
- RAG settings
- Enrichment behavior
- Pipeline configuration

See [Configuration Guide](configuration.md) for details.

### Deploy Your Site

Ready to share your archive with the world? See [Deployment Guide](deployment.md).

### Generate More Posts

Process another export or adjust windowing:

```bash
# Daily windowing (default)
eg write another-export.zip --output-dir=. --step-size=1 --step-unit=days

# Hourly windowing for active chats
eg write export.zip --step-size=4 --step-unit=hours

# Message-based windowing
eg write export.zip --step-size=100 --step-unit=messages
```

### Enable Enrichment

Use LLM to enrich URLs and media:

```bash
eg write export.zip --enable-enrichment
```

### Rank Your Content

Use ELO comparisons to identify your best posts:

```bash
eg read rank docs/posts/
eg top --limit=10
```

### Check Pipeline Runs

View pipeline execution history:

```bash
eg runs list
eg runs show <run_id>
```

## Common Options

```bash
# Daily windowing instead of default
eg write export.zip --step-size=1 --step-unit=days

# Enable URL/media enrichment
eg write export.zip --enable-enrichment

# Custom date range
eg write export.zip --from-date=2025-01-01 --to-date=2025-01-31

# Different model
eg write export.zip --model=google-gla:gemini-pro-latest

# Incremental processing (resume previous run)
eg write export.zip --resume

# Invalidate cache tiers
eg write export.zip --refresh=writer  # Regenerate posts
eg write export.zip --refresh=all     # Full rebuild
```

## Troubleshooting

### "No posts were generated"

Check that:

1. Your chat has enough messages (minimum varies by window size)
2. The date range includes your messages
3. The window parameters are appropriate for your chat volume

### Rate Limiting

If you hit API rate limits, Egregora will automatically retry with exponential backoff. You can also configure quota limits in `.egregora.toml`:

```toml
[quota]
daily_llm_requests = 1000
per_second_limit = 1.0
concurrency = 5
```

### LanceDB Permission Issues

In restricted environments, ensure `.egregora/lancedb/` is writable:

```bash
chmod -R u+w .egregora/lancedb/
```

## Learn More

- [Technical Reference](../reference/index.md) - Learn about the architecture and CLI
- [Code of the Weaver](../CLAUDE.md) - Guidelines for contributors
