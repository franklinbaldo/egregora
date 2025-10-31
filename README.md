# Egregora 🤖 → 📝

**Emergent Group Reflection Engine Generating Organized Relevant Articles**

Transform your WhatsApp group chats into intelligent, privacy-first blogs where collective conversations emerge as beautifully written articles.

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Powered by uv](https://img.shields.io/badge/uv-powered-FF6C37.svg)](https://github.com/astral-sh/uv)

---

## ✨ Why Egregora?

- **🧠 Emergent Intelligence**: Collective conversations synthesize into coherent articles
- **👥 Group Reflection**: Your community's unique voice and insights are preserved
- **🛡️ Privacy-First**: Automatic anonymization - real names never reach the AI
- **⚙️ Fully Automated**: Stateless pipeline powered by Ibis, DuckDB, and Gemini
- **📊 Smart Context**: RAG retrieval ensures consistent, context-aware writing

## 🚀 Quick Start

### 1. Install `uv`

```bash
# On macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Initialize Your Blog

```bash
# Create a new blog site (zero installation required!)
uvx --from git+https://github.com/franklinbaldo/egregora egregora init my-blog
cd my-blog
```

### 3. Set Up Your API Key

```bash
# Get a free Gemini API key: https://ai.google.dev/gemini-api/docs/api-key
export GOOGLE_API_KEY="your-google-gemini-api-key"

# On Windows (PowerShell):
# $Env:GOOGLE_API_KEY = "your-google-gemini-api-key"
```

### 4. Process Your WhatsApp Export

```bash
# Export your WhatsApp chat (without media for privacy)
# Settings → More → Export chat → Without media

# Process the export
uvx --from git+https://github.com/franklinbaldo/egregora egregora process \
  whatsapp-export.zip \
  --output=. \
  --timezone='America/New_York'
```

### 5. Serve Your Blog

```bash
# Launch local preview (no installation needed!)
uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

Open http://localhost:8000 to see your AI-generated blog! 🎉

---

## 🏗️ Architecture: Staged Pipeline

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

---

## 🛡️ Privacy by Design

Privacy is core to Egregora's architecture:

### Automatic Anonymization
- Real names are converted to deterministic UUIDs **before** any LLM interaction
- Same person always gets the same pseudonym (e.g., `a3f2b91c`)
- AI never sees actual names, only anonymized identifiers

### User Controls
Users can manage their data directly in WhatsApp:

```
/egregora set alias "Casey"      # Set display name
/egregora set bio "AI researcher" # Add profile bio
/egregora opt-out                # Exclude from future posts
/egregora opt-in                 # Include in future posts
```

### PII Detection
- Scans text and media for phone numbers, emails, addresses
- Automatically removes detected PII
- Configurable sensitivity levels

---

## ⚙️ Advanced Features

### Content Ranking

```bash
# Run Elo comparisons to identify your best posts
uvx --from git+https://github.com/franklinbaldo/egregora egregora rank \
  --site-dir=. \
  --comparisons=50
```

### AI-Powered Editing

```bash
# Let the AI refine an existing post
uvx --from git+https://github.com/franklinbaldo/egregora egregora edit \
  posts/2025-01-15-ai-safety.md
```

### Custom Models

```yaml
# In mkdocs.yml
extra:
  egregora:
    models:
      writer: models/gemini-2.0-flash-exp
      enricher: models/gemini-1.5-flash
      embedding: models/gemini-embedding-001  # Default: 3072 dimensions
```

### RAG Configuration

```bash
# Adjust retrieval parameters
egregora process whatsapp.zip \
  --retrieval-mode=ann \          # or 'exact'
  --retrieval-nprobe=10 \         # ANN search quality
  --embedding-dimensions=768      # Model dimensions
```

---

## 🧩 Technical Details

### Runtime Requirements

Egregora uses **DuckDB** with the [VSS extension](https://duckdb.org/docs/extensions/vss.html) for vector search:

```bash
# Auto-installed on first run, or install manually:
duckdb -c "INSTALL vss; LOAD vss"
```

**Offline/Firewalled environments:** Use `--retrieval-mode exact` until VSS is available.

### Stack

- **Ibis**: DataFrame abstraction for data transformations
- **DuckDB**: Fast analytical database with vector search
- **Gemini**: Google's LLM for content generation
- **MkDocs**: Static site generation
- **uv**: Modern Python package management

### Database Schemas

All schemas are defined in `core/database_schema.py` using Ibis:

```python
from egregora.core import database_schema

# Persistent schemas (DuckDB tables)
database_schema.RAG_CHUNKS_SCHEMA
database_schema.ANNOTATIONS_SCHEMA
database_schema.ELO_RATINGS_SCHEMA

# Ephemeral schemas (in-memory transformations)
database_schema.CONVERSATION_SCHEMA
```

---

## 🛠️ Development

### Setup

```bash
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install with all development dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/

# Run specific test suites
uv run pytest tests/test_gemini_dispatcher.py  # Dispatcher tests
uv run pytest tests/test_with_golden_fixtures.py  # VCR integration tests

# Lint code
uv run ruff check src/
uv run black --check src/
```

### Testing Notes

**VCR Tests:** The integration tests use `pytest-vcr` to record and replay API interactions.
They use `retrieval_mode="exact"` to avoid requiring the DuckDB VSS extension in test environments.

**VSS Extension:** For production use, the VSS extension is auto-downloaded at runtime.
In restricted environments (CI/CD), you may need to pre-install it:

```bash
python -c "import duckdb; conn = duckdb.connect(); conn.execute('INSTALL vss'); conn.execute('LOAD vss')"
```

For testing purposes, exact mode (`--retrieval-mode=exact`) works perfectly and requires no additional setup.

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
├── config/          # Configuration management
├── utils/           # Batch processing, caching
└── prompts/         # Jinja2 prompt templates
```

### Contributing

We welcome contributions! Please:

1. Check existing issues or open a new one
2. Fork the repository
3. Create a feature branch
4. Write tests for new functionality
5. Submit a pull request

---

## 📚 Documentation

- **Getting Started**: [`docs/getting-started/`](docs/getting-started/)
- **Architecture Guide**: [`docs/guides/architecture.md`](docs/guides/architecture.md)
- **API Reference**: [`docs/reference/api.md`](docs/reference/api.md)
- **Privacy Model**: [`docs/features/anonymization.md`](docs/features/anonymization.md)

---

## 🤝 Community & Support

- **Issues**: [GitHub Issues](https://github.com/franklinbaldo/egregora/issues) - Bug reports and feature requests
- **Discussions**: [GitHub Discussions](https://github.com/franklinbaldo/egregora/discussions) - Questions and community support
- **Documentation**: Comprehensive guides in [`docs/`](docs/)

---

## 📄 License

MIT License - see [`LICENSE`](LICENSE) file for details.

---

## 🙏 Philosophy

Egregora follows the principle of **"trusting the LLM"** - instead of micromanaging with complex heuristics, we:

- Give the AI complete conversation context
- Let it make editorial decisions (how many posts, what to write)
- Use tool calling for structured output
- Keep the pipeline simple and composable

This results in simpler code and often better outcomes. The LLM knows what makes a good article - our job is to give it the right context.

---

**Built with ❤️ using [uv](https://github.com/astral-sh/uv)**
