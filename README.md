# Egregora 🤖 → 📝

**Emergent Group Reflection Engine Generating Organized Relevant Articles**

> **Turn your group chat into a magazine.**

Transform messy WhatsApp conversations into beautifully written blog posts. An AI-powered publishing system that synthesizes your group's collective intelligence into coherent, insightful articles—while keeping everyone's privacy intact.

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Powered by uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## 💡 What Does It Do?

Egregora transforms informal group conversations into polished blog posts. Here's what happens:

**Input:** Your WhatsApp group discussing AI, philosophy, or that article someone shared
**Output:** A thoughtful blog post like ["The License to Exist: What Happens When the System Says 'Write Anything You Want'?"](tests/fixtures/golden/expected_output/posts/2025-10-28-the-license-to-exist-emergent-agency-in-a-test-environment.md) with proper formatting, citations, and metadata

### ✨ Key Features

<table>
<tr>
<td width="50%">

**🧠 Emergent Intelligence**
AI synthesizes scattered messages into coherent narratives, finding patterns and themes you didn't know existed

**🛡️ Privacy-First Architecture**
Real names → deterministic UUIDs before any AI processing. No PII ever reaches the LLM.

**📊 Context-Aware Writing**
RAG retrieval ensures posts reference past discussions, creating a coherent knowledge base over time

</td>
<td width="50%">

**⚙️ Zero Configuration**
Run directly with `uvx` - no installation, no setup, just works

**🎯 Quality Ranking**
Built-in Elo system helps identify your best content

**✏️ AI Editor**
Interactive refinement of generated posts with conversational AI

</td>
</tr>
</table>

### 🎯 Perfect For

- **Research groups** turning discussions into publication drafts
- **Reading clubs** synthesizing book conversations into essays
- **Remote teams** creating knowledge bases from Slack/WhatsApp
- **Personal archiving** preserving meaningful conversations as structured content
- **Content creators** finding story angles in community discussions

## 🚀 Quick Start

Get your AI-powered blog running in under 5 minutes:

### Step 1: Get a Gemini API Key (Free)

1. Visit [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key)
2. Click "Get API key" → Create API key
3. Copy the key

```bash
# Set the API key
export GOOGLE_API_KEY="your-api-key-here"
```

### Step 2: Export Your WhatsApp Chat

On WhatsApp:
1. Open the group chat
2. Tap **⋮** (menu) → **More** → **Export chat**
3. Choose **"Without media"** (recommended for privacy)
4. Save the `.zip` file

### Step 3: Run Egregora

```bash
# Install uv (one-time, ~30 seconds)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Process your chat (creates a blog in ./my-blog)
uvx --from git+https://github.com/franklinbaldo/egregora \
    egregora process whatsapp-export.zip --output=./my-blog

# Serve locally
cd my-blog
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

**That's it!** Open [http://localhost:8000](http://localhost:8000) to see your blog.

### What Just Happened?

```
WhatsApp Export → Privacy Filter → AI Analysis → Blog Posts
                  (anonymize)     (find themes)  (write articles)
```

Egregora:
1. ✅ Parsed your messages into structured data
2. ✅ Anonymized all real names to UUIDs
3. ✅ Found interesting conversation threads
4. ✅ Generated 0-N blog posts per time period
5. ✅ Created a beautiful static site with MkDocs

**No tracking, no cloud storage, everything runs locally.**

---

## 🤖 Running with GitHub Actions

Automate blog generation whenever you push new WhatsApp exports to your repository:

<details>
<summary><b>Click to see GitHub Actions setup</b></summary>

Create `.github/workflows/egregora.yml`:

```yaml
name: Generate Blog

on:
  push:
    paths:
      - 'exports/*.zip'  # Trigger when new exports are added
  workflow_dispatch:     # Manual trigger

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Process WhatsApp export
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
        run: |
          uvx --from git+https://github.com/franklinbaldo/egregora \
            egregora process exports/latest.zip --output=./blog

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./blog/site
```

**Setup:**
1. Add your WhatsApp export to `exports/latest.zip`
2. Add your Gemini API key to GitHub Secrets:
   - Go to repository Settings → Secrets and variables → Actions
   - Create secret `GOOGLE_API_KEY` with your API key
3. Push changes - the workflow runs automatically
4. Your blog is published to `https://[username].github.io/[repo]/`

**Benefits:**
- ✅ Fully automated blog updates
- ✅ No local setup required
- ✅ Free hosting on GitHub Pages
- ✅ Version control for all exports and generated content

</details>

---

## 🛡️ Privacy & Security

Egregora is designed with privacy as a core architectural principle:

### How Privacy Works

| Stage | What Happens | Example |
|-------|--------------|---------|
| **1. Ingestion** | Parse WhatsApp export locally | "Alice: Let's discuss that AI paper" |
| **2. Anonymization** | Replace real names with UUIDs | "`a3f2b91c`: Let's discuss that AI paper" |
| **3. PII Detection** | Scan for phone numbers, emails | Automatically removed |
| **4. AI Processing** | LLM only sees anonymized data | AI never knows "Alice" exists |

### User Controls

Participants can control their data **directly in WhatsApp**:

```
/egregora set alias "Casey"       # Set a display name
/egregora set bio "AI researcher" # Add profile information
/egregora opt-out                 # Exclude from future posts
/egregora opt-in                  # Re-include in posts
```

### Technical Guarantees

- ✅ **Deterministic UUIDs**: Same person = same pseudonym across runs
- ✅ **No API uploads**: All processing happens locally with Gemini API calls
- ✅ **PII scrubbing**: Automatic detection of phone numbers, emails, addresses
- ✅ **No telemetry**: Zero tracking or analytics
- ✅ **Open source**: Audit the code yourself

---

## ❓ FAQ

<details>
<summary><b>How much does this cost?</b></summary>

Egregora uses Google's Gemini API, which has a generous free tier:
- **Free tier**: 15 requests/minute, 1500 requests/day
- **Cost**: A typical 1000-message export uses ~20-50 API calls
- **Estimate**: Most users stay within free tier limits

See [Gemini API pricing](https://ai.google.dev/pricing) for details.
</details>

<details>
<summary><b>What about WhatsApp media (images, videos)?</b></summary>

Currently, Egregora focuses on text conversations:
- **Supported**: Text messages, URLs, quoted messages
- **Experimental**: Image analysis (with enrichment)
- **Not yet**: Videos, voice messages, documents

For privacy, we recommend exporting **without media**.
</details>

<details>
<summary><b>Can I use this with Slack/Discord/Telegram?</b></summary>

Not yet, but it's on the roadmap! The architecture is designed to be platform-agnostic:
- ✅ Currently: WhatsApp
- 🚧 Planned: Telegram, Slack, Discord
- 💡 Want to contribute? See [CONTRIBUTING.md](docs/development/contributing.md)
</details>

<details>
<summary><b>How does the AI decide what to write about?</b></summary>

Egregora uses a "trust the LLM" philosophy:
1. Groups messages by time period (e.g., weekly)
2. Retrieves relevant context from past posts (RAG)
3. Gives the AI complete conversation context
4. **The AI decides**: how many posts (0-N), what themes, what's worth writing

This produces better results than rigid heuristics.
</details>

<details>
<summary><b>Can I customize the AI's writing style?</b></summary>

Yes! Edit `mkdocs.yml` in your blog directory:

```yaml
extra:
  egregora:
    models:
      writer: models/gemini-2.0-flash-exp  # Change model
      tone: "academic"  # Add custom instructions
```

See [Configuration Guide](docs/getting-started/configuration.md) for all options.
</details>

<details>
<summary><b>What if the AI writes something wrong or inappropriate?</b></summary>

You have full control:
1. **Edit posts manually**: They're just Markdown files in `posts/`
2. **Use AI editor**: `egregora edit posts/my-post.md` for interactive refinement
3. **Delete posts**: Remove unwanted `.md` files
4. **Regenerate**: Run `egregora process` again with different settings
</details>

<details>
<summary><b>How do I deploy my blog?</b></summary>

Your blog is a standard MkDocs site. Deploy anywhere:

```bash
# Build static site
mkdocs build

# Deploy to GitHub Pages (built-in)
mkdocs gh-deploy

# Or use: Netlify, Vercel, Cloudflare Pages, etc.
```

See [MkDocs deployment docs](https://www.mkdocs.org/user-guide/deploying-your-docs/).
</details>

---

## 🏗️ Architecture: Staged Pipeline

<details>
<summary><b>Click to expand technical architecture details</b></summary>

Egregora uses a **staged pipeline architecture** that processes conversations through distinct phases:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Ingestion  │ -> │   Privacy   │ -> │ Augmentation│
└─────────────┘    └─────────────┘    └─────────────┘
      ↓                   ↓                   ↓
   Parse ZIP        Anonymize UUIDs     Enrich context
                    Detect PII          Build profiles

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Knowledge  │ <- │ Generation  │ -> │ Publication │
└─────────────┘    └─────────────┘    └─────────────┘
      ↑                   ↓                   ↓
   RAG Index        LLM Writer           MkDocs Site
   Annotations      Tool Calling         Templates
   Rankings
```

### Pipeline Stages

1. **Ingestion** (`ingestion/`)
   - Parse WhatsApp `.zip` exports into structured Ibis tables
   - Extract messages, timestamps, authors, media references

2. **Privacy** (`privacy/`)
   - **Anonymization**: Convert names to deterministic UUIDs
   - **PII Detection**: Scan for sensitive information
   - **Opt-out Management**: Respect user privacy preferences

3. **Augmentation** (`augmentation/`)
   - **Enrichment**: LLM-powered descriptions for URLs and media
   - **Profiling**: Generate author bio/context from conversations

4. **Knowledge** (`knowledge/`)
   - **RAG**: Vector store for retrieving similar past posts
   - **Annotations**: Conversation metadata and threading
   - **Rankings**: Elo-based content quality scoring

5. **Generation** (`generation/`)
   - **Writer**: LLM with tool calling generates 0-N posts per period
   - **Editor**: Interactive AI-powered document refinement

6. **Publication** (`publication/`)
   - **Site Scaffolding**: MkDocs project structure
   - **Templates**: Homepage, about pages, post indexes

### Why Staged Pipeline > ETL?

- **Clearer separation of concerns** - Each stage has focused responsibility
- **Acknowledges feedback loops** - RAG indexes posts for future queries
- **Stateful operations** - Knowledge stage maintains persistent data
- **Better maintainability** - Easier to understand and extend

</details>

---

## ⚙️ Advanced Usage

<details>
<summary><b>Content Ranking with Elo</b></summary>

Identify your best posts using AI-powered pairwise comparisons:

```bash
egregora rank --site-dir=. --comparisons=50
```

This runs an [Elo rating system](https://en.wikipedia.org/wiki/Elo_rating_system) where an AI judge compares posts to determine quality rankings.
</details>

<details>
<summary><b>AI-Powered Post Editing</b></summary>

Interactively refine generated posts with conversational AI:

```bash
egregora edit posts/2025-01-15-my-post.md
```

The editor provides suggestions while you retain full control over the final content.
</details>

<details>
<summary><b>Custom AI Models</b></summary>

Configure different Gemini models in `mkdocs.yml`:

```yaml
extra:
  egregora:
    models:
      writer: models/gemini-2.0-flash-exp      # Blog post generation
      enricher: models/gemini-1.5-flash        # URL/media descriptions
      embedding: models/text-embedding-004     # Vector embeddings
```
</details>

<details>
<summary><b>RAG & Vector Search Configuration</b></summary>

Tune retrieval settings for different environments:

```bash
# Development: Fast exact search (no VSS extension required)
egregora process export.zip --retrieval-mode=exact

# Production: ANN search with quality tuning
egregora process export.zip \
  --retrieval-mode=ann \
  --retrieval-nprobe=10 \        # Higher = better quality, slower
  --embedding-dimensions=768     # Match your embedding model
```
</details>

<details>
<summary><b>Batch Processing & Caching</b></summary>

For large exports, use batch processing and caching:

```bash
# Process with batch API (more efficient for 100+ messages)
egregora process export.zip --batch-size=50

# Enrichment cache survives across runs
# Re-running won't re-enrich already processed URLs/media
```

Cache location: `./.egregora_cache/` (DiskCache format)
</details>

---

## 🧩 Technical Stack

**Core Technologies:**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **DataFrame Engine** | [Ibis](https://ibis-project.org/) | Type-safe data transformations |
| **Database** | [DuckDB](https://duckdb.org/) + VSS | Analytics + vector search |
| **LLM** | [Google Gemini](https://ai.google.dev/) | Content generation & analysis |
| **Site Generator** | [MkDocs](https://www.mkdocs.org/) + Material | Beautiful static blogs |
| **Package Manager** | [uv](https://github.com/astral-sh/uv) | Fast Python dependency management |

**Python 3.12+** required

<details>
<summary><b>Database Schemas</b></summary>

All schemas are defined in `core/database_schema.py` using Ibis for type safety:

```python
from egregora.core import database_schema

# Persistent schemas (saved to DuckDB)
database_schema.RAG_CHUNKS_SCHEMA      # Vector embeddings for retrieval
database_schema.ANNOTATIONS_SCHEMA     # Conversation metadata
database_schema.ELO_RATINGS_SCHEMA     # Post quality rankings

# Ephemeral schemas (in-memory only)
database_schema.CONVERSATION_SCHEMA    # Parsed messages (never persisted)
```

**Key invariant**: All pipeline stages must return tables conforming to `CONVERSATION_SCHEMA`.
</details>

<details>
<summary><b>Runtime Requirements</b></summary>

**DuckDB VSS Extension**

Egregora uses DuckDB's [VSS extension](https://duckdb.org/docs/extensions/vss.html) for vector similarity search:

```bash
# Auto-installed on first run, or manually:
duckdb -c "INSTALL vss; LOAD vss"
```

**Offline/Firewalled Environments:**
- Use `--retrieval-mode=exact` (works without VSS extension)
- Pre-install VSS before going offline

**Gemini API**
- Free tier: 15 req/min, 1500 req/day
- API key required: [Get one free](https://ai.google.dev/gemini-api/docs/api-key)
</details>

---

## 🛠️ Development

**Quick Start for Contributors:**

```bash
# Clone and setup
git clone https://github.com/franklinbaldo/egregora.git
cd egregora
uv sync --all-extras

# Run tests
uv run pytest tests/                            # All tests
uv run pytest tests/test_gemini_dispatcher.py   # Unit tests
uv run pytest tests/test_with_golden_fixtures.py # Integration tests (VCR)

# Lint and format
uv run ruff check src/              # Lint
uv run ruff format src/             # Format
uv run mypy src/                    # Type check
```

### Project Structure

```
src/egregora/
├── ingestion/       # Parse WhatsApp exports
├── privacy/         # Anonymization & PII detection
├── augmentation/    # Enrichment & profiling
├── knowledge/       # RAG, annotations, rankings
├── generation/      # LLM writer & editor
├── publication/     # Site scaffolding
├── core/            # Shared models & schemas
├── orchestration/   # CLI & pipeline coordination
└── utils/           # Batch processing, caching
```

See [`CLAUDE.md`](CLAUDE.md) for detailed architecture and development guidelines.

<details>
<summary><b>Testing with VCR Cassettes</b></summary>

Integration tests use [`pytest-vcr`](https://pytest-vcr.readthedocs.io/) to record/replay Gemini API calls:

**How it works:**
1. First run: Makes real API calls, saves to `tests/cassettes/*.yaml`
2. Subsequent runs: Replays from cassettes (no API key needed)

**Re-recording cassettes:**
```bash
# Delete cassettes and re-run tests with GOOGLE_API_KEY set
rm -rf tests/cassettes/
export GOOGLE_API_KEY="your-key"
uv run pytest tests/test_with_golden_fixtures.py
```

**VSS Extension in Tests:**
Tests use `--retrieval-mode=exact` to avoid VSS extension dependency in CI/CD.

</details>

<details>
<summary><b>Contributing Guidelines</b></summary>

**We welcome contributions!** Here's how:

1. **Check existing issues** or [open a new one](https://github.com/franklinbaldo/egregora/issues/new)
2. **Fork the repository** and create a feature branch
3. **Follow conventions**:
   - Use `ruff` for linting/formatting
   - Write tests for new features
   - Update docs if changing behavior
   - Follow existing code patterns (see `CLAUDE.md`)
4. **Submit a PR** with clear description

**Good first issues:**
- Add support for new chat platforms (Telegram, Discord)
- Improve PII detection patterns
- Add new prompt templates
- Enhance test coverage

See [`docs/development/contributing.md`](docs/development/contributing.md) for details.

</details>

---

## 📚 Documentation

**Comprehensive docs in [`docs/`](docs/):**

| Guide | Description |
|-------|-------------|
| [**Getting Started**](docs/getting-started/) | Installation, configuration, first run |
| [**Architecture**](docs/guide/architecture.md) | Pipeline stages, design decisions |
| [**Privacy Model**](docs/guide/privacy.md) | Anonymization, PII detection |
| [**API Reference**](docs/api/) | Python API for extending Egregora |

---

## 🌟 Philosophy

> **"Trust the LLM"**

Instead of micromanaging with complex heuristics, Egregora:

- Gives AI complete conversation context
- Lets it make editorial decisions (0-N posts, themes, structure)
- Uses tool calling for structured output
- Keeps the pipeline simple and composable

**Result:** Simpler code, better outcomes. The LLM knows what makes good writing—we just provide the right context.

---

## 🤝 Community

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/franklinbaldo/egregora/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/franklinbaldo/egregora/discussions)
- 🌟 **Star the repo** if you find it useful!

---

## 📄 License

**MIT License** - see [`LICENSE`](LICENSE) for details.

---

<div align="center">

**Built with** ❤️ **using** [uv](https://github.com/astral-sh/uv)

*Egregora: Where collective conversations become collective intelligence.*

**[⬆ Back to Top](#egregora--)**

</div>
