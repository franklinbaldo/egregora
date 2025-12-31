# Quick Start

This guide will walk you through generating your first blog post from a WhatsApp export in under 5 minutes.

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) installed
- [Google Gemini API key](https://ai.google.dev/gemini-api/docs/api-key)

## Step 1: Install Egregora

Install the latest version from GitHub:

```bash
uv tool install git+https://github.com/franklinbaldo/egregora
```

## Step 2: Initialize Your Blog

First, install Egregora if you haven't already:
```bash
uv tool install git+https://github.com/franklinbaldo/egregora
```

Now, create a new blog site:
```bash
egregora init my-blog
cd my-blog
```

Running `egregora init` or the next `egregora write` call will automatically create `.egregora` (mkdocs config plus cache/RAG/LanceDB paths). If you ever need to rehydrate the scaffolding manually, run `python scripts/bootstrap_site.py ./my-blog` from the repo root or `python ../scripts/bootstrap_site.py .` from within the site directory.

This creates a minimal MkDocs site structure:

```
my-blog/
├── .egregora/
│   ├── mkdocs.yml      # Site configuration
│   └── ...             # Egregora state (databases, cache)
└── docs/
    ├── index.md        # Homepage
    └── posts/          # Generated blog posts go here
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
egregora write whatsapp-export.zip --output-dir=. --timezone='America/New_York'
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
# 1. Install doc dependencies (if you haven't already)
uv sync --all-extras

# 2. Preview your site
uv run mkdocs serve -f .egregora/mkdocs.yml
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
egregora write another-export.zip --output-dir=. --step-size=1 --step-unit=days

# Hourly windowing for active chats
egregora write export.zip --step-size=4 --step-unit=hours

# Message-based windowing
egregora write export.zip --step-size=100 --step-unit=messages
```

### Enable Enrichment

Use LLM to enrich URLs and media:

```bash
egregora write export.zip --enable-enrichment
```

### Rank Your Content

Use ELO comparisons to identify your best posts:

```bash
egregora read rank docs/posts/
egregora top --limit=10
```

### Check Pipeline Runs

View pipeline execution history:

```bash
egregora runs list
egregora runs show <run_id>
```

## Common Options

```bash
# Daily windowing instead of default
egregora write export.zip --step-size=1 --step-unit=days

# Enable URL/media enrichment
egregora write export.zip --enable-enrichment

# Custom date range
egregora write export.zip --from-date=2025-01-01 --to-date=2025-01-31

# Different model
egregora write export.zip --model=google-gla:gemini-pro-latest

# Incremental processing (resume previous run)
egregora write export.zip --resume

# Invalidate cache tiers
egregora write export.zip --refresh=writer  # Regenerate posts
egregora write export.zip --refresh=all     # Full rebuild
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

- [Architecture Overview](../../v3/architecture/index.md) - Understand the pipeline
- [API Reference](../../v3/api-reference/index.md) - Complete code documentation
