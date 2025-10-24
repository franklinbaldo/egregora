# Quickstart Tutorial

Create your first blog from WhatsApp messages in 5 minutes.

## Step 1: Initialize a Blog Site

```bash
egregora init my-blog
cd my-blog
```

This creates:
```
my-blog/
├── mkdocs.yml          # Site configuration
├── docs/              # Documentation pages
├── posts/             # Blog posts (will be generated)
├── profiles/          # Author profiles (will be generated)
└── media/             # Uploaded media
```

## Step 2: Install MkDocs Material

```bash
pip install 'mkdocs-material[imaging]'
```

This provides the beautiful blog theme.

## Step 3: Process Your WhatsApp Export

```bash
egregora process \
  --zip_file=../whatsapp-export.zip \
  --output=. \
  --timezone='America/Sao_Paulo' \
  --from_date=2025-01-01 \
  --to_date=2025-01-31 \
  --gemini_key=YOUR_GEMINI_API_KEY
```

**Important flags:**
- `--timezone` - Your timezone (prevents wrong date grouping)
- `--from_date` / `--to_date` - Date range (saves API costs)
- `--gemini_key` - Your Google Gemini API key

Find your timezone: [List of tz database timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

## Step 4: Preview Your Blog

```bash
mkdocs serve
```

Open http://localhost:8000 in your browser. You should see:
- Generated blog posts in the `/blog` section
- Author profiles with anonymized UUIDs
- Media attachments (if included)

## Step 5: Explore the Output

Check what was created:

```bash
# See generated posts
ls -la posts/

# See author profiles
ls -la profiles/

# Read a post
cat posts/2025-01-15-*.md
```

Each post includes:
- **Front matter** - Metadata (title, date, tags, authors)
- **Content** - LLM-generated summary and discussion
- **Media section** - Attached images/videos/audio
- **Privacy** - All names anonymized to UUIDs

## What Just Happened?

Egregora did the following:

1. **Parsed** your WhatsApp export into a structured DataFrame
2. **Anonymized** all names → UUID5 pseudonyms (privacy-first)
3. **Grouped** messages by date (day/week/month)
4. **Enriched** messages with URL/media context (optional)
5. **Asked the LLM** to write blog posts with full editorial control
6. **Generated** 0-N posts per period (LLM decides what's worth writing)
7. **Created** author profiles for each participant

See [Core Concepts](concepts.md) for details on how this works.

## Next Steps

### Customize Your Site

Edit `mkdocs.yml` to change:
- Site name and description
- Theme colors and fonts
- Navigation structure
- Plugin configuration

See the [Configuration Guide](../guides/configuration.md).

### Control Your Privacy

Users can send commands in WhatsApp to control their data:

```
/egregora set alias "Franklin"       # Set display name
/egregora set bio "Python lover"     # Add bio
/egregora opt-out                    # Exclude from future posts
```

See [User Commands](../features/privacy-commands.md) for all available commands.

### Rank Your Posts

Use the ELO-based ranking system to identify your best content:

```bash
egregora rank --site_dir . --comparisons 50
```

See [Post Ranking](../features/ranking.md) for details.

### Process More Dates

Add more blog posts:

```bash
egregora process \
  --zip_file=../whatsapp-export.zip \
  --output=. \
  --from_date=2025-02-01 \
  --to_date=2025-02-28
```

## Cost Estimation

Processing uses Google Gemini API. Approximate costs:

- **Small group (10-50 messages/day)**: $0.01-0.05 per day
- **Active group (100-500 messages/day)**: $0.10-0.50 per day
- **Very active group (1000+ messages/day)**: $1-5 per day

**Cost-saving tips:**
- Use `--from_date` and `--to_date` to process small date ranges
- Use `--enable_enrichment=False` to skip URL/media enrichment
- Process weekly (`--period=week`) instead of daily

## Common Issues

### Wrong Timezone

**Problem:** Posts are dated incorrectly (e.g., messages from Jan 15 appear in Jan 14 post)

**Solution:** Always specify `--timezone` matching your phone's timezone.

### Too Expensive

**Problem:** Processing is using too many API tokens

**Solution:** Use date filters and disable enrichment:
```bash
egregora process \
  --from_date=2025-01-01 \
  --to_date=2025-01-07 \
  --enable_enrichment=False
```

### No Posts Generated

**Problem:** Processing completes but no posts created

**Solution:** The LLM decided nothing was worth writing about. This is by design - the LLM has editorial judgment. Try:
- Process a longer date range
- Check your messages are interesting/substantive
- Enable debug mode (`--debug`) to see LLM reasoning

See [Troubleshooting Guide](../guides/troubleshooting.md) for more help.

## Where to Go Next

- [Core Concepts](concepts.md) - Understand the architecture
- [Privacy & Anonymization](../features/anonymization.md) - How we protect your data
- [Configuration Guide](../guides/configuration.md) - Customize everything
- [Multi-Post Generation](../features/multi-post.md) - How thread detection works
