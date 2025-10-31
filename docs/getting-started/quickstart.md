# Quick Start

This guide will walk you through generating your first blog post from a WhatsApp export in under 5 minutes.

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) installed
- [Google Gemini API key](https://ai.google.dev/gemini-api/docs/api-key)

## Step 1: Initialize Your Blog

Create a new blog site:

```bash
uvx --from git+https://github.com/franklinbaldo/egregora egregora init my-blog
cd my-blog
```

This creates a minimal MkDocs site structure:

```
my-blog/
├── mkdocs.yml          # Site configuration
├── docs/
│   ├── index.md        # Homepage
│   └── posts/          # Generated blog posts go here
└── .egregora/          # Egregora state (databases, cache)
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
uvx --from git+https://github.com/franklinbaldo/egregora egregora process \
  whatsapp-export.zip \
  --output=. \
  --timezone='America/New_York'
```

This will:

1. Parse the WhatsApp export
2. Anonymize all names (real names never reach the AI)
3. Group messages by time period (default: weekly)
4. Generate blog posts using Gemini

!!! info
    The first run may take a few minutes as it:

    - Downloads DuckDB VSS extension (for vector search)
    - Embeds all messages for RAG retrieval
    - Generates multiple blog posts

## Step 5: Preview Your Blog

Launch a local preview server:

```bash
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

Open [http://localhost:8000](http://localhost:8000) in your browser. 🎉

## What Just Happened?

Egregora processed your chat through multiple stages:

1. **Ingestion**: Parsed WhatsApp `.zip` → structured DataFrame
2. **Privacy**: Replaced names with UUIDs (e.g., `john` → `a3f2b91c`)
3. **Augmentation**: (Optional) Enriched URLs/media with descriptions
4. **Knowledge**: Built RAG index for retrieving similar past posts
5. **Generation**: Gemini generated 0-N blog posts per period
6. **Publication**: Created markdown files in `docs/posts/`

## Next Steps

### Customize Your Blog

Edit `mkdocs.yml` to change:

- Site name, description, theme
- Navigation structure
- Egregora models and parameters

See [Configuration Guide](configuration.md) for details.

### Generate More Posts

Process another time period:

```bash
egregora process another-export.zip --output=. --period=daily
```

### Improve Existing Posts

Use the AI editor to refine posts:

```bash
egregora edit docs/posts/2025-01-15-my-post.md
```

### Rank Your Content

Use Elo comparisons to identify your best posts:

```bash
egregora rank --site-dir=. --comparisons=50
```

## Common Options

```bash
# Daily posts instead of weekly
egregora process export.zip --period=daily

# Enable URL/media enrichment
egregora process export.zip --enrich

# Use exact search (no VSS extension needed)
egregora process export.zip --retrieval-mode=exact

# Custom date range
egregora process export.zip --start-date=2025-01-01 --end-date=2025-01-31

# Different model
egregora process export.zip --model=models/gemini-2.0-flash-exp
```

## Troubleshooting

### "DuckDB VSS extension failed to load"

In restricted environments, use exact search mode:

```bash
egregora process export.zip --retrieval-mode=exact
```

Or pre-install the VSS extension:

```bash
python -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL vss'); conn.execute('LOAD vss')"
```

### "No posts were generated"

Check that:

1. Your chat has enough messages (minimum varies by period)
2. The date range includes your messages
3. Privacy settings allow content generation

### Rate Limiting

If you hit API rate limits, Egregora will automatically retry with exponential backoff. You can also reduce batch sizes in the configuration.

## Learn More

- [Architecture Overview](../guide/architecture.md) - Understand the pipeline
- [Privacy Model](../guide/privacy.md) - How anonymization works
- [API Reference](../api/index.md) - Complete code documentation
