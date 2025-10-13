# 🤖 Egregora

> **Automated WhatsApp-to-Post Pipeline with AI Enrichment and RAG Capabilities**

Egregora transforms WhatsApp group conversations into polished, publishable posts with AI-powered enrichment, intelligent privacy controls, and search-ready archives. Perfect for communities, research groups, and content creators who want to preserve and publish their discussions.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/dependency_manager-uv-purple.svg)](https://docs.astral.sh/uv/)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## ✨ Key Features

### 🚀 **Zero-Touch Processing**
- **Automated Discovery**: Finds WhatsApp exports automatically, handles multiple groups, skips duplicates
- **Smart Date Filtering**: Process specific date ranges or recent days with timezone support
- **Batch Processing**: Handle multiple ZIP files and groups in a single command

### 🧠 **AI-Powered Intelligence**
- **Gemini Integration**: Rich link analysis, media descriptions, and content enrichment
- **RAG-Enhanced Posts**: Retrieval-Augmented Generation for contextual, high-quality outputs
- **Participant Profiles**: Automatically generated member dossiers with interaction history

### 🔒 **Privacy-First Design**
- **Deterministic Anonymization**: Consistent, reversible pseudonyms for all participants
- **Safe Content**: No phone numbers or sensitive data in outputs
- **Privacy Controls**: Configurable anonymization levels and output filtering

### 📊 **Enterprise-Ready Architecture**
- **Polars DataFrames**: High-performance data processing for large conversations
- **Intelligent Caching**: Avoid reprocessing with persistent enrichment cache
- **Flexible Output**: Markdown posts, JSON profiles, media galleries

## 🎯 Perfect For

- **Research Communities**: Preserve and publish academic discussions with proper anonymization
- **Content Creators**: Transform group conversations into blog posts or newsletters
- **Knowledge Management**: Create searchable archives of team discussions
- **Community Building**: Share highlights and insights from private group conversations

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** 
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **Gemini API Key** (free tier available at [Google AI Studio](https://aistudio.google.com/app/apikey))

### Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/franklinbaldo/egregora.git
cd egregora
uv sync

# Set your API key
export GEMINI_API_KEY="your-api-key-here"
```

### Your First Posts

```bash
# 1. Add your WhatsApp exports to data/whatsapp_zips/
cp your-whatsapp-export.zip data/whatsapp_zips/

# 2. Preview what would be processed
uv run egregora process data/whatsapp_zips/*.zip --dry-run

# 3. Generate posts for the last 2 days
uv run egregora process data/whatsapp_zips/*.zip --days 2

# 4. Check your outputs in data/
ls data/your-group-slug/posts/daily/

# 5. Build and serve your site
uv run mkdocs serve
```

That's it! Your anonymized, enriched posts are ready in Markdown format and can be viewed at http://127.0.0.1:8000.

## 📖 Usage Guide

### Basic Commands

```bash
# Process all ZIP files for recent days
uv run egregora process data/whatsapp_zips/*.zip --days 3

# Process specific date range
uv run egregora process data/whatsapp_zips/*.zip \
  --from-date 2024-01-01 \
  --to-date 2024-01-31

# Custom output directory and timezone
uv run egregora process data/whatsapp_zips/*.zip \
  --output-dir /path/to/output \
  --timezone America/New_York

# Preview without processing
uv run egregora process data/whatsapp_zips/*.zip --dry-run
```

### Advanced Configuration

```bash
# Full feature example
uv run egregora process data/whatsapp_zips/*.zip \
  --output-dir data/custom-output \
  --model gemini-flash-lite-latest \
  --timezone America/Porto_Velho \
  --days 7 \
  --max-links 50 \
  --relevance-threshold 2 \
  --cache-dir cache \
  --link-member-profiles \
  --profile-base-url "/profiles/"
```

### Profile Management

```bash
# List existing profiles
uv run egregora profiles list

# Show specific member profile
uv run egregora profiles show <member-id>

# Generate profiles from ZIP files
uv run egregora profiles generate <zip-file-path>

# Clean old profiles
uv run egregora profiles clean
```

## 📁 Output Structure

Egregora creates a well-organized directory structure:

```
data/
└── your-group-slug/
    ├── posts/
    │   └── daily/
    │       ├── 2024-01-15.md    # Generated posts
    │       ├── 2024-01-16.md
    │       └── ...
    ├── media/
    │   ├── uuid1.jpg            # Extracted attachments
    │   ├── uuid2.pdf
    │   └── ...
    ├── profiles/
    │   ├── generated/
    │   │   ├── member1.md       # Participant dossiers
    │   │   └── member2.md
    │   └── json/
    │       ├── member1.json     # Machine-readable profiles
    │       └── member2.json
    └── index.md                 # Group overview page

cache/                           # Enrichment cache
├── analyses/                    # Cached AI analyses
├── rag/                        # RAG embeddings
└── system_labels/              # Classification cache

metrics/
└── enrichment_run.csv          # Processing metrics
```

## 🛠 Configuration Options

### Input/Output
- `--output-dir` - Where to save generated content (default: `data/`)
- `--group-name` - Override detected group name
- `--group-slug` - Override generated group slug

### Date Processing  
- `--days` - Process last N days
- `--from-date` - Start date (YYYY-MM-DD)
- `--to-date` - End date (YYYY-MM-DD)  
- `--timezone` - IANA timezone (default: `America/Porto_Velho`)

### AI & Enrichment
- `--model` - Gemini model (default: `gemini-flash-lite-latest`)
- `--disable-enrichment` - Skip link/media analysis
- `--max-links` - Maximum links to analyze per day (default: 50)
- `--relevance-threshold` - Minimum relevance score (default: 2)
- `--safety-threshold` - Gemini safety level (default: `BLOCK_NONE`)
- `--thinking-budget` - Token budget for reasoning (default: -1)

### Profiles & Linking
- `--link-member-profiles` - Link to participant profiles in posts  
- `--profile-base-url` - Base URL for profile links (default: `/profiles/`)
- `--no-link-member-profiles` - Disable profile linking

### Cache & Performance
- `--cache-dir` - Cache directory (default: `cache/`)
- `--disable-cache` - Skip enrichment caching
- `--auto-cleanup-days` - Cache cleanup threshold (default: 90)

### Debug & Preview
- `--dry-run` - Preview without processing
- `--list-groups` - Show discovered groups and exit

Run `uv run egregora process --help` for the complete list.

## 🔧 Advanced Features

### RAG (Retrieval-Augmented Generation)

Egregora includes a powerful RAG system for contextual post generation:

```python
# Rebuild RAG index programmatically
from pathlib import Path
from egregora.rag.config import RAGConfig
from egregora.rag.index import PostRAG

rag = PostRAG(
    posts_dir=Path("data/posts"),
    cache_dir=Path("cache/rag"),
    config=RAGConfig(enabled=True, vector_store_type="chroma"),
)
result = rag.update_index(force_rebuild=True)
print(f"Indexed {result['posts_count']} posts → {result['chunks_count']} chunks")
```

### Custom Prompts

Customize AI behavior by editing prompts in `src/egregora/prompts/`:

- `system_instruction_base.md` - Base system instructions
- `system_instruction_multigroup.md` - Multi-group processing prompts

### Enrichment Metrics

Track processing performance with automatic metrics:

```bash
# View enrichment statistics
cat metrics/enrichment_run.csv
```

Includes timestamps, link counts, domains processed, and error rates.

## 🧪 Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install with development dependencies
uv sync --extra test --extra lint --extra docs

# Install pre-commit hooks
uv run pre-commit install
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/test_privacy.py -v
uv run pytest -k "anonymization" -v

# Test with real data (requires GEMINI_API_KEY)
uv run pytest tests/test_integration.py -v
```

### Code Quality

```bash
# Format and lint
uv run black .
uv run ruff check . --fix

# Run pre-commit hooks
uv run pre-commit run --all-files

# Type checking
uv run mypy src/egregora/
```

### Documentation

```bash
# Serve docs locally
uv run mkdocs serve

# Build static docs
uv run mkdocs build
```

## 🔄 Architecture Overview

### Core Components

- **`UnifiedProcessor`** - Main orchestration engine handling discovery, processing, and output
- **`WhatsAppParser`** - Converts exports to structured Polars DataFrames
- **`Anonymizer`** - Deterministic privacy protection for all participants
- **`EnrichmentEngine`** - AI-powered link and media analysis with caching
- **`RAGSystem`** - Retrieval-Augmented Generation for contextual posts
- **`ProfileUpdater`** - Automated participant profile generation

### Data Flow

```
WhatsApp Exports → Parse → Anonymize → Enrich → Generate Posts
                     ↓         ↓         ↓
                 DataFrames  Privacy  AI Analysis
                     ↓         ↓         ↓  
                Media Files  Profiles  RAG Context
```

### Performance Features

- **Polars DataFrames** for high-speed data processing
- **Persistent caching** to avoid reprocessing
- **Incremental profile updates** for efficiency
- **Batch processing** for multiple groups/dates

## 🤖 AI Agent Integration

Egregora includes built-in support for AI agent collaboration:

### Jules Integration
```bash
# Create Jules session for complex development tasks
curl -X POST "https://jules.googleapis.com/v1alpha/sessions" \
  -H "X-Goog-Api-Key: $JULES_API_KEY" \
  -d '{"title": "Egregora Enhancement", "sourceContext": {"source": "sources/github/franklinbaldo/egregora"}}'
```

### Codex Reviews
```bash
# Trigger automated code review
gh pr comment <PR_NUMBER> --body "@codex code review"
```

See `CLAUDE.md` for detailed agent coordination strategies.

## 📚 Examples

### Daily Newsletter Generation

```bash
# Generate daily newsletter for the last week
uv run egregora process data/whatsapp_zips/*.zip \
  --days 7 \
  --link-member-profiles \
  --model gemini-flash-lite-latest
```

### Research Archive Creation

```bash
# Process academic group discussions with strict privacy
uv run egregora process data/academic-group.zip \
  --from-date 2024-01-01 \
  --to-date 2024-12-31 \
  --output-dir research-archive \
  --disable-enrichment
```

### Content Creator Workflow

```bash
# Transform discussions into blog content
uv run egregora process data/creator-group.zip \
  --days 3 \
  --max-links 100 \
  --output-dir blog-content \
  --link-member-profiles \
  --profile-base-url "https://myblog.com/contributors/"
```

## 🚨 Privacy & Security

### Data Protection
- **No phone numbers** in outputs - all participants anonymized
- **Deterministic pseudonyms** - same person = same anonymous ID
- **Local processing** - your data never leaves your machine
- **Configurable retention** - automatic cache cleanup

### Anonymization Details
- Uses SHA-256 hashing with salt for consistent anonymization
- Preserves conversation flow while protecting identities
- Deterministic pseudonyms ensure same person = same anonymous ID
- Configurable output formats for different privacy levels

### Security Best Practices
- Store API keys in environment variables only
- Use `.gitignore` patterns to avoid committing sensitive data
- Regular cache cleanup with `--auto-cleanup-days`
- Review outputs before publishing to ensure privacy compliance

## 🤝 Contributing

We welcome contributions! Please see our [contribution guidelines](CONTRIBUTING.md).

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the full test suite
5. Submit a pull request

### Code Style
- Follow PEP 8 with Black formatting
- Add type hints for all functions
- Include docstrings for public APIs
- Write tests for new features

### Testing Requirements
- All tests must pass
- New features need test coverage
- Integration tests for AI features
- Performance tests for large datasets

## 📄 License

Egregora is released under the MIT License. See [LICENSE](LICENSE) for details.

## 🎯 Roadmap

### Upcoming Features
- [ ] **Multi-language support** - Process conversations in different languages
- [ ] **Export formats** - PDF, HTML, and JSON output options  
- [ ] **Web interface** - Browser-based processing and preview
- [ ] **Cloud deployment** - Docker containers and cloud templates
- [ ] **Advanced analytics** - Conversation insights and statistics

### Performance Improvements
- [ ] **Streaming processing** - Handle very large exports efficiently
- [ ] **Parallel enrichment** - Concurrent AI analysis for speed
- [ ] **Smart caching** - More intelligent cache invalidation
- [ ] **Memory optimization** - Reduced memory usage for large datasets

## 💬 Support

- **Documentation**: [docs.egregora.dev](https://docs.egregora.dev) (coming soon)
- **Issues**: [GitHub Issues](https://github.com/franklinbaldo/egregora/issues)
- **Discussions**: [GitHub Discussions](https://github.com/franklinbaldo/egregora/discussions)
- **Email**: egregora@franklin.dev

---

<div align="center">

**Made with ❤️ for communities who value their conversations**

[⭐ Star us on GitHub](https://github.com/franklinbaldo/egregora) • [📖 Read the Docs](https://docs.egregora.dev) • [🐛 Report Issues](https://github.com/franklinbaldo/egregora/issues)

</div>