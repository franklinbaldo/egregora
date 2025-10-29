# CLI Reference

Complete command-line interface documentation for Egregora.

## Global Options

### --help

Show help message for any command.

```bash
egregora --help
egregora process --help
egregora rank --help
```

## Commands

### egregora init

Initialize a new MkDocs site scaffold for serving Egregora posts.

**Usage:**
```bash
egregora init <output_dir>
```

**Arguments:**
- `output_dir` (required) - Directory path for the new site (e.g., 'my-blog')

**What it creates:**
- `mkdocs.yml` - Site configuration with Material theme + blog plugin
- `docs/` - Documentation pages directory
- `posts/` - Blog posts directory (empty, to be filled by `process`)
- `profiles/` - Author profiles directory (empty, to be filled by `process`)
- `media/` - Media files directory
- `README.md` - Quick start instructions
- `.gitignore` - Python and MkDocs ignore patterns
- Starter pages - Homepage, about, profiles index

**Example:**
```bash
# Create new site
egregora init my-blog

# Change to site directory
cd my-blog

# Install MkDocs Material
pip install 'mkdocs-material[imaging]'

# Serve the site
mkdocs serve
```

**Output:**
```
✅ MkDocs site scaffold initialized successfully!

📁 Site root: /path/to/my-blog
📝 Docs directory: /path/to/my-blog/docs

Next steps:
• Install MkDocs: pip install 'mkdocs-material[imaging]'
• Change to site directory: cd my-blog
• Serve the site: mkdocs serve
• Process WhatsApp export: egregora process export.zip --output=my-blog
```

---

### egregora process

Process WhatsApp export and generate blog posts + author profiles.

**Usage:**
```bash
egregora process <zip_file> [OPTIONS]
```

**Arguments:**
- `zip_file` (required) - Path to WhatsApp export ZIP file

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output` | Path | `output` | Output directory for generated site |
| `--period` | str | `day` | Grouping period: 'day', 'week', or 'month' |
| `--enable-enrichment` | bool | `True` | Enable LLM enrichment for URLs/media |
| `--from-date` | str | None | Only process messages from this date onwards (YYYY-MM-DD) |
| `--to-date` | str | None | Only process messages up to this date (YYYY-MM-DD) |
| `--timezone` | str | None | Timezone for date parsing (e.g., 'America/New_York') |
| `--gemini-key` | str | None | Google Gemini API key (flag overrides GOOGLE_API_KEY env var) |
| `--model` | str | None | Gemini model to use (or configure in mkdocs.yml) |
| `--debug` | bool | `False` | Enable debug logging |

**Examples:**

**Basic usage:**
```bash
egregora process whatsapp-export.zip
```

**Specify output directory:**
```bash
egregora process export.zip --output=./my-blog
```

**Process specific date range (recommended for cost control):**
```bash
egregora process export.zip \
  --from-date=2025-01-01 \
  --to-date=2025-01-31 \
  --timezone='America/Sao_Paulo'
```

**Weekly grouping instead of daily:**
```bash
egregora process export.zip --period=week
```

**Disable enrichment (faster, cheaper):**
```bash
egregora process export.zip --enable-enrichment=False
```

**Use specific model:**
```bash
egregora process export.zip --model=gemini-1.5-pro
```

**Debug mode:**
```bash
egregora process export.zip --debug
```

**Complete example:**
```bash
egregora process whatsapp-export.zip \
  --output=./my-blog \
  --from-date=2025-01-01 \
  --to-date=2025-01-31 \
  --timezone='America/New_York' \
  --period=day \
  --enable-enrichment=True \
  --gemini-key=YOUR_API_KEY \
  --model=models/gemini-flash-latest \
  --debug
```

**What it does:**

1. **Parses** WhatsApp export into a structured Ibis table
2. **Anonymizes** all names → UUID5 pseudonyms (privacy-first)
3. **Groups** messages by period (day/week/month)
4. **Enriches** messages with URL/media context (if enabled)
5. **Asks LLM** to write blog posts with full editorial control
6. **Generates** 0-N posts per period (LLM decides what's worth writing)
7. **Creates/updates** author profiles for each participant

**Output:**
- `posts/` - Generated blog posts in markdown
- `profiles/` - Author profiles in markdown
- `rag/` - RAG embeddings stored in `chunks.parquet` (if enrichment enabled)
- `enriched/` - Debug CSV files (if debug mode)

**Environment Variables:**
- `GOOGLE_API_KEY` - Gemini API key (alternative to --gemini-key flag)

**Important Notes:**

1. **Always specify timezone** to prevent date grouping errors
2. **Use date filters** to control API costs
3. **First run:** Use `--enable-enrichment=False` (no posts to index yet)
4. **Subsequent runs:** Enable enrichment to build RAG index

---

### egregora rank

Run ELO-based ranking comparisons for blog posts.

**Usage:**
```bash
egregora rank [OPTIONS]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--site-dir` | Path | `.` | Site directory containing posts/ and profiles/ |
| `--comparisons` | int | `1` | Number of comparisons to run |
| `--strategy` | str | `fewest_games` | Selection strategy: 'fewest_games', 'random', etc. |
| `--export-parquet` | bool | `False` | Export rankings to Parquet files |
| `--gemini-key` | str | None | Google Gemini API key (flag overrides GOOGLE_API_KEY env var) |
| `--model` | str | None | Gemini model to use (or configure in mkdocs.yml) |
| `--debug` | bool | `False` | Enable debug logging |

**Examples:**

**Single comparison:**
```bash
egregora rank --site-dir=./my-blog
```

**Multiple comparisons (recommended for bootstrapping):**
```bash
egregora rank --site-dir=./my-blog --comparisons=50
```

**With specific API key:**
```bash
egregora rank \
  --site-dir=./my-blog \
  --comparisons=10 \
  --gemini-key=YOUR_API_KEY
```

**Export to Parquet files:**
```bash
egregora rank \
  --site-dir=./my-blog \
  --comparisons=20 \
  --export-parquet
```

**Debug mode:**
```bash
egregora rank --site-dir=./my-blog --debug
```

**What it does:**

1. **Selects** two posts to compare (based on strategy)
2. **Picks** random author profile to judge
3. **Runs three-turn comparison:**
   - Turn 1: LLM chooses winner
   - Turn 2: LLM comments on post A with star rating
   - Turn 3: LLM comments on post B with star rating
4. **Updates** ELO ratings based on comparison
5. **Stores** comparison history in DuckDB
6. **Repeats** for specified number of comparisons

**Output:**
- `rankings/rankings.duckdb` - DuckDB database with ELO ratings and history
- `rankings/elo_ratings.parquet` - Parquet export (if --export-parquet)
- `rankings/elo_history.parquet` - Parquet export (if --export-parquet)

**Selection Strategies:**
- `fewest_games` (default) - Prioritize posts with fewest comparisons
- `random` - Random post selection
- More strategies may be added in future

**Best Practices:**

1. **Cold start:** Run 50-100 comparisons initially
2. **Ongoing:** Run 5-10 comparisons weekly
3. **Confidence:** Posts need 5-10 games for reliable rankings
4. **Judgment:** Different profiles provide diverse perspectives

See [Ranking Documentation](../features/ranking.md) for details.

---

### egregora edit

Edit a blog post using the LLM-powered Editor Agent.

**Usage:**
```bash
egregora edit <post_path> [OPTIONS]
```

**Arguments:**
- `post_path` (required) - Path to markdown post file

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--rag-dir` | Path | `./rag` | RAG database directory for context |
| `--gemini-key` | str | None | Google Gemini API key (flag overrides GOOGLE_API_KEY env var) |
| `--model` | str | None | Gemini model to use |
| `--custom-instructions` | str | None | Custom editorial instructions |
| `--debug` | bool | `False` | Enable debug logging |

**Examples:**

**Edit single post:**
```bash
egregora edit posts/2025-01-15-ai-ethics.md
```

**With RAG context:**
```bash
egregora edit posts/2025-01-15-ai-ethics.md --rag-dir=./my-blog/rag
```

**Custom instructions:**
```bash
egregora edit posts/2025-01-15-ai-ethics.md \
  --custom-instructions="Fix typos and improve clarity in section 2"
```

**Batch editing:**
```bash
# Edit all posts from January
for post in posts/2025-01-*.md; do
    egregora edit "$post" --rag-dir=./rag
done
```

**What it does:**

1. **Loads** post into line-by-line editing interface
2. **Reviews** post quality and clarity
3. **Queries RAG** for relevant context (if available)
4. **Makes edits** using line edits or full rewrites
5. **Saves** edited post back to disk
6. **Returns** decision (publish/hold) and editorial notes

**Editor Tools:**
- `edit_line` - Replace single line
- `full_rewrite` - Rewrite entire post
- `query_rag` - Search past posts
- `ask_llm` - Consult meta-LLM for ideas
- `finish` - Mark as done (publish/hold)

See [Editor Documentation](../features/editor.md) for details.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (validation, API, processing, etc.) |

## Environment Variables

### GOOGLE_API_KEY

Google Gemini API key. Alternative to passing `--gemini-key` flag.

```bash
export GOOGLE_API_KEY="your-api-key-here"
egregora process export.zip
```

Or in `.env` file:
```bash
GOOGLE_API_KEY=your-api-key-here
```

## Configuration Files

### mkdocs.yml

Primary configuration file. See [Configuration Guide](../guides/configuration.md).

```yaml
extra:
  egregora:
    group_slug: my-group
    timezone: America/Sao_Paulo
    model: models/gemini-flash-latest
    temperature: 0.7
    custom_instructions: |
      Focus on technical depth.
```

## Common Workflows

### First-Time Setup

```bash
# 1. Initialize site
egregora init my-blog
cd my-blog

# 2. Install MkDocs
pip install 'mkdocs-material[imaging]'

# 3. Process WhatsApp export
egregora process ../whatsapp-export.zip \
  --output=. \
  --from-date=2025-01-01 \
  --to-date=2025-01-31 \
  --timezone='America/Sao_Paulo'

# 4. Preview site
mkdocs serve
```

### Regular Updates

```bash
# Process new month
egregora process export.zip \
  --output=./my-blog \
  --from-date=2025-02-01 \
  --to-date=2025-02-28 \
  --enable-enrichment=True

# Rank new posts
egregora rank --site-dir=./my-blog --comparisons=10

# Review and publish
mkdocs build
mkdocs gh-deploy  # Deploy to GitHub Pages
```

### Quality Improvement

```bash
# Rank all posts
egregora rank --site-dir=./my-blog --comparisons=50

# Edit low-ranked posts
# (Find posts with ELO < 1400 from rankings database)

for post in posts/2025-01-*-low-quality-topic.md; do
    egregora edit "$post" --rag-dir=./rag
done

# Re-rank after edits
egregora rank --site-dir=./my-blog --comparisons=20
```

## Debugging

### Enable Debug Mode

```bash
# See detailed logs
egregora process export.zip --debug

# Capture logs to file
egregora process export.zip --debug 2>&1 | tee egregora.log
```

### Check What Went Wrong

```bash
# Validate ZIP file
unzip -t export.zip

# Check date range
unzip -p export.zip _chat.txt | head -20

# Test API key
curl -H "x-goog-api-key: YOUR_KEY" \
  https://generativelanguage.googleapis.com/v1/models
```

## Related Documentation

- [Quickstart Tutorial](../getting-started/quickstart.md) - First-time usage
- [Configuration Guide](../guides/configuration.md) - Detailed config options
- [Troubleshooting](../guides/troubleshooting.md) - Common issues
- [Feature Documentation](../features/) - Detailed feature guides
