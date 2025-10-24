# Configuration Guide

Egregora uses `mkdocs.yml` as the single source of truth for both MkDocs and Egregora settings.

## Quick Start

### Minimal Configuration

```yaml
# mkdocs.yml
site_name: My Blog
site_url: https://myblog.com

theme:
  name: material

plugins:
  - blog:
      blog_dir: posts
```

That's all you need! Egregora works with defaults.

### Add Egregora Settings

```yaml
extra:
  egregora:
    group_slug: my-group
    timezone: America/Sao_Paulo
    custom_instructions: |
      Focus on technical depth.
      Prefer concrete examples.
```

## Configuration Reference

### Site Settings

#### site_name

Your blog's name.

```yaml
site_name: My Awesome Blog
```

#### site_url

Public URL where blog will be hosted.

```yaml
site_url: https://myblog.com
```

#### site_description

SEO description.

```yaml
site_description: A blog about AI, philosophy, and coordination
```

### Theme Configuration

Egregora works best with **MkDocs Material**.

#### Basic Theme

```yaml
theme:
  name: material
  language: en
```

#### Custom Colors

```yaml
theme:
  name: material
  palette:
    # Light mode
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode

    # Dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
```

#### Font

```yaml
theme:
  name: material
  font:
    text: Roboto
    code: Roboto Mono
```

### Blog Plugin

MkDocs Material blog plugin configuration.

#### Basic Setup

```yaml
plugins:
  - blog:
      blog_dir: posts
      post_url_format: "{slug}"
```

#### Advanced Blog Settings

```yaml
plugins:
  - blog:
      blog_dir: posts
      blog_toc: true
      post_date_format: full
      post_url_format: "{slug}"
      post_excerpt: required
      post_excerpt_max_authors: 3
      post_slugify: !!python/object/apply:pymdownx.slugs.slugify
        kwds:
          case: lower
      archive: true
      archive_name: Archive
      archive_date_format: MMMM yyyy
      archive_url_format: "archive/{date}"
      categories: true
      categories_name: Categories
      categories_url_format: "category/{slug}"
      categories_slugify: !!python/object/apply:pymdownx.slugs.slugify
        kwds:
          case: lower
```

### Egregora Configuration

All Egregora-specific settings go in `extra.egregora`.

#### group_slug

Identifier for your WhatsApp group.

```yaml
extra:
  egregora:
    group_slug: ai-safety-group
```

Used for:
- Profile namespacing
- RAG context separation (if you have multiple groups)

#### timezone

**Critical:** Timezone for parsing WhatsApp timestamps.

```yaml
extra:
  egregora:
    timezone: America/Sao_Paulo
```

Find yours: [List of tz database timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

Common values:
- `America/New_York` - US Eastern
- `America/Los_Angeles` - US Pacific
- `America/Sao_Paulo` - Brazil
- `Europe/London` - UK
- `Europe/Paris` - Central Europe
- `Asia/Tokyo` - Japan
- `Australia/Sydney` - Australia

#### custom_instructions

Custom editorial instructions for the LLM.

```yaml
extra:
  egregora:
    custom_instructions: |
      ### Writing Style
      - Focus on technical depth and precision
      - Prefer concrete examples over abstract theory
      - Include relevant quotes from participants
      - Use Scott Alexander-style concrete hooks

      ### Topic Selection
      - Prioritize discussions about AI safety and coordination
      - Skip purely social chit-chat
      - Include philosophical debates

      ### Formatting
      - Use subheadings for different discussion threads
      - Add "Key Points" section at the end
      - Include participant UUIDs when quoting
```

#### enable_rag

Enable RAG enrichment (default: true).

```yaml
extra:
  egregora:
    enable_rag: true
```

Set to `false` to disable RAG (faster, cheaper).

#### rag_top_k

Number of RAG results to retrieve (default: 5).

```yaml
extra:
  egregora:
    rag_top_k: 10
```

Higher values provide more context but cost more tokens.

#### model

LLM model to use (default: "gemini-2.0-flash-exp").

```yaml
extra:
  egregora:
    model: gemini-2.0-flash-exp
```

Options:
- `gemini-2.0-flash-exp` - Fastest, cheapest (recommended)
- `gemini-1.5-pro` - Higher quality, slower, more expensive
- `gemini-1.5-flash` - Older fast model

#### temperature

LLM temperature (default: 0.7).

```yaml
extra:
  egregora:
    temperature: 0.9
```

- `0.0` - Deterministic, focused
- `0.7` - Balanced (recommended)
- `1.0` - More creative, diverse

### Navigation

Configure site navigation manually:

```yaml
nav:
  - Home: index.md
  - Blog:
      - posts/index.md
  - About: about.md
```

Or let MkDocs auto-generate from file structure.

### Plugins

#### Search

```yaml
plugins:
  - search:
      lang: en
```

#### Tags

```yaml
plugins:
  - tags:
      tags_file: tags.md
```

Creates a tags index page.

#### RSS Feed

```yaml
plugins:
  - rss:
      match_path: posts/.*
      date_from_meta:
        as_creation: date
      categories:
        - tags
```

### Extensions

Markdown extensions for better formatting:

```yaml
markdown_extensions:
  # Python Markdown
  - toc:
      permalink: true
  - attr_list
  - def_list
  - tables
  - abbr
  - footnotes
  - md_in_html

  # Python Markdown Extensions
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.tasklist:
      custom_checkbox: true
  - pymdownx.emoji:
      emoji_index: !!python/name:material.extensions.emoji.twemoji
      emoji_generator: !!python/name:material.extensions.emoji.to_svg
```

## CLI Configuration

### Environment Variables

#### GOOGLE_API_KEY

Gemini API key (required).

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Or create `.env` file:
```bash
GOOGLE_API_KEY=your-api-key-here
```

### CLI Flags

Override configuration via command-line flags.

#### --timezone

```bash
egregora process --timezone='America/New_York'
```

#### --from_date / --to_date

Process specific date range:

```bash
egregora process \
  --from_date=2025-01-01 \
  --to_date=2025-01-31
```

Format: `YYYY-MM-DD`

#### --period

Group messages by day/week/month:

```bash
egregora process --period=week
```

Options: `day`, `week`, `month`

#### --enable_enrichment

Enable/disable enrichment:

```bash
egregora process --enable_enrichment=False
```

#### --gemini_key

Pass API key directly:

```bash
egregora process --gemini_key=YOUR_KEY
```

#### --model

Override model:

```bash
egregora process --model=gemini-1.5-pro
```

#### --debug

Enable debug output:

```bash
egregora process --debug
```

Shows:
- LLM prompts and responses
- Token usage
- API call details

## Complete Example

### Production Configuration

```yaml
# mkdocs.yml
site_name: AI Safety Discussion Group Blog
site_url: https://aisafety.blog
site_description: Insights from our AI safety coordination group

theme:
  name: material
  language: en
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: deep purple
      accent: deep purple
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: deep purple
      accent: deep purple
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  font:
    text: Roboto
    code: Roboto Mono
  features:
    - navigation.instant
    - navigation.tracking
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy

plugins:
  - search
  - blog:
      blog_dir: posts
      blog_toc: true
      post_date_format: full
      post_url_format: "{slug}"
      archive: true
      categories: true
  - tags:
      tags_file: tags.md
  - rss:
      match_path: posts/.*
      date_from_meta:
        as_creation: date
      categories:
        - tags

markdown_extensions:
  - toc:
      permalink: true
  - attr_list
  - def_list
  - tables
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.emoji:
      emoji_index: !!python/name:material.extensions.emoji.twemoji
      emoji_generator: !!python/name:material.extensions.emoji.to_svg

extra:
  egregora:
    group_slug: ai-safety-group
    timezone: America/New_York
    enable_rag: true
    rag_top_k: 5
    model: gemini-2.0-flash-exp
    temperature: 0.7
    custom_instructions: |
      ### Writing Style
      - Focus on technical accuracy and depth
      - Use concrete examples and specific scenarios
      - Include relevant quotes from participants
      - Adopt Scott Alexander's style of concrete hooks

      ### Topic Selection
      - Prioritize: AI alignment, coordination problems, existential risk
      - Include: Philosophy, decision theory, game theory
      - Skip: Pure social chitchat, scheduling logistics

      ### Formatting
      - Use subheadings (##) for distinct discussion threads
      - Add "Key Points" section summarizing main takeaways
      - Include participant UUIDs when quoting
      - Link to referenced papers/articles

      ### Tone
      - Thoughtful and analytical
      - Acknowledge uncertainty and disagreement
      - Respectful of diverse perspectives

nav:
  - Home: index.md
  - Blog:
      - posts/index.md
  - Tags: tags.md
  - About: about.md

copyright: |
  &copy; 2025 AI Safety Discussion Group<br>
  Generated with <a href="https://github.com/franklinbaldo/egregora">Egregora</a>
```

### Development Configuration

```yaml
# mkdocs.yml
site_name: Test Blog
site_url: http://localhost:8000

theme:
  name: material

plugins:
  - blog:
      blog_dir: posts

extra:
  egregora:
    group_slug: test-group
    timezone: America/Sao_Paulo
    enable_rag: false  # Faster for testing
    model: gemini-2.0-flash-exp
    temperature: 0.7
```

## Configuration Best Practices

### 1. Always Specify Timezone

**Do:**
```yaml
extra:
  egregora:
    timezone: America/Sao_Paulo
```

**Don't:**
```yaml
# Missing timezone - messages may be dated wrong!
```

### 2. Use Custom Instructions

Generic posts are boring. Give the LLM editorial guidance:

```yaml
extra:
  egregora:
    custom_instructions: |
      Focus on [your topic].
      Skip [things you don't want].
      Style: [your preferred style].
```

### 3. Start with RAG Disabled

For first run, disable RAG (no posts to index yet):

```bash
egregora process --enable_enrichment=False
```

After you have posts, enable RAG:

```bash
egregora process --enable_enrichment=True
```

### 4. Use Date Filters

Don't process everything at once:

```bash
# Process one month at a time
egregora process \
  --from_date=2025-01-01 \
  --to_date=2025-01-31
```

This saves API costs and lets you iterate faster.

### 5. Version Control Your Config

```bash
git add mkdocs.yml
git commit -m "Update Egregora configuration"
```

Track changes over time.

## Validation

### Check Configuration

```bash
# Validate mkdocs.yml
mkdocs build --strict

# Test Egregora settings
egregora process --debug --dry-run
```

### Common Mistakes

**Missing quotes on timezone:**
```yaml
# ❌ Wrong
timezone: America/Sao_Paulo

# ✅ Correct
timezone: 'America/Sao_Paulo'
```

**Invalid YAML indentation:**
```yaml
# ❌ Wrong
extra:
egregora:
  timezone: ...

# ✅ Correct
extra:
  egregora:
    timezone: ...
```

**Duplicate keys:**
```yaml
# ❌ Wrong
plugins:
  - blog
plugins:
  - search

# ✅ Correct
plugins:
  - blog
  - search
```

## Related Documentation

- [Quickstart Tutorial](../getting-started/quickstart.md) - First-time setup
- [Architecture](architecture.md) - How configuration is used
- [Troubleshooting](troubleshooting.md) - Common config errors
