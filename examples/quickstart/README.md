# Quickstart Example

This example demonstrates the complete Egregora workflow from WhatsApp export to published blog.

## Prerequisites

- Python 3.11+
- Google Gemini API key
- WhatsApp chat export

## Steps

### 1. Install Egregora

```bash
pip install egregora
```

### 2. Set API Key

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

### 3. Run the Example Script

```bash
./run-example.sh
```

Or manually:

```bash
# Initialize site
egregora init my-blog
cd my-blog

# Install MkDocs
pip install 'mkdocs-material[imaging]'

# Process your WhatsApp export
egregora process \
  /path/to/your/whatsapp-export.zip \
  --output=. \
  --timezone='America/Sao_Paulo' \
  --from-date=2025-01-01 \
  --to-date=2025-01-31

# Preview the site
mkdocs serve
```

### 4. Expected Output

After processing, you should have:

```
my-blog/
├── mkdocs.yml              # Site configuration
├── posts/                  # Generated blog posts
│   ├── 2025-01-15-ai-ethics.md
│   └── 2025-01-16-weekend-plans.md
├── profiles/               # Author profiles
│   ├── a1b2c3d4.md
│   └── e5f6g7h8.md
├── rag/                    # RAG embeddings (Parquet)
│   └── chunks.parquet
└── docs/                   # Site pages
    └── index.md
```

### 5. View Your Blog

Open http://localhost:8000 in your browser.

## What's Happening?

1. **Parse** - Egregora reads your WhatsApp export
2. **Anonymize** - All names replaced with UUIDs (privacy-first)
3. **Group** - Messages grouped by day
4. **Enrich** - URLs and media context added (optional)
5. **Generate** - LLM writes blog posts with full editorial control
6. **Output** - Markdown posts with front matter

## Next Steps

- **Customize:** Edit `mkdocs.yml` to change site settings
- **Rank Posts:** Run `egregora rank --site-dir=. --comparisons=50`
- **Edit Posts:** Run `egregora edit posts/2025-01-15-ai-ethics.md`
- **Add More Data:** Process additional date ranges

## Troubleshooting

### No posts generated

The LLM decided nothing was worth writing about. Try:
- Processing a longer date range
- Checking messages contain substantive discussions
- Running with `--debug` to see LLM reasoning

### Wrong dates

Always specify `--timezone` matching your phone's timezone.

### API errors

Check your API key:
```bash
curl -H "x-goog-api-key: $GOOGLE_API_KEY" \
  https://generativelanguage.googleapis.com/v1/models
```

## Full Documentation

See [docs/](../../docs/README.md) for complete documentation.
