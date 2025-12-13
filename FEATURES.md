# Egregora Features

Complete inventory of features and capabilities in Egregora.

---

## 📥 Input Adapters

Parse and ingest data from various sources into egregora.

### WhatsApp Adapter
- Parse WhatsApp export files (`.txt`, `.zip`)
- Extract messages, media, metadata
- Support for group chats and direct messages
- Media file extraction from `.zip` archives

### Slack Adapter  
- Parse Slack export archives
- Thread reconstruction
- User mapping and profile extraction
- Channel-based organization

### Markdown Adapter
- Ingest existing markdown files
- Preserve frontmatter metadata
- Support for custom schemas

### Self-Reflection
- Import existing blog posts/documents
- Re-process with egregora pipeline
- Update with new enrichments

---

## 🧠 RAG (Retrieval-Augmented Generation)

Semantic search and context retrieval for LLM generation.

### LanceDB Backend
- Vector embeddings storage
- Semantic similarity search
- Document chunking strategies
- Persistent vector database

### Embedding Router
- **Dual-queue architecture** (single + batch endpoints)
- **API key cycling** - rotates through multiple Gemini keys on 429
- Independent rate limit tracking per endpoint
- Automatic fallback between endpoints
- Thread-based concurrent processing

### Search Capabilities
- Keyword search
- Semantic search (vector similarity)
- Hybrid search (keyword + semantic)
- Context window construction
- Relevance scoring

---

## 🤖 Agents

AI-powered workers that process and generate content.

### Writer Agent
- Generate blog posts from conversation windows
- Chat-style interactive prompts
- Support for multiple LLM providers (Gemini, OpenAI, Anthropic, OpenRouter)
- AFC (Agent Function Calling) for structured output
- **Model rotation** on rate limits
- Token counting and budget management

### Enricher Agent
- **URL enrichment** - summarize/analyze web content
- **Media enrichment** - generate descriptions for images/videos
- **3 enrichment strategies**:
  - `batch_all` - all items in one API call (default)
  - `batch_api` - Gemini Batch API  
  - `individual` - one call per item
- **ModelKeyRotator** - exhausts all API keys for each model before rotating
  - Rotation: Model1+Key1→Key2→Key3, then Model2+Key1→Key2→Key3, etc.
  - 5 Gemini models × N API keys attempts before fallback
  - OpenRouter only after all Gemini combinations exhausted
- Jinja2 templates for batch prompts
- Fallback mechanisms on errors

### Avatar Agent
- Generate profile avatars
- Fallback to [avataaars.io](https://avataaars.io)
- Avatar command processing (`/avatar set`)

### Taxonomy Agent
- Auto-generate semantic topic clusters
- Tag extraction and organization
- Word cloud generation
- Topic-based content organization

---

## 🎯 Models & Rate Limiting

Advanced model management and API resilience.

### ModelKeyRotator
- **Proper rotation order**: exhaust all keys per model before rotating
- Supports 5 Gemini models:
  1. gemini-2.5-flash-lite
  2. gemini-2.0-flash
  3. gemini-2.5-flash
  4. gemini-flash-latest  
  5. gemini-2.5-pro
- Load multiple API keys from `GEMINI_API_KEYS` env var
- Automatic retry with next key/model on 429 errors
- Security: keys masked in logs

### GeminiKeyRotator
- Standalone key rotation for single model
- Comma-separated keys from environment
- Fallback to `GEMINI_API_KEY` or `GOOGLE_API_KEY`

### Google Batch API
- Async batch processing via Gemini Batch API
- Inline request format (no file upload quota)
- Job polling and result retrieval
- Cost optimization for large batches

### Provider Registry
- Multi-provider support (Gemini, OpenAI, Anthropic, OpenRouter)
- Automatic fallback chains
- Model capability detection
- Free model discovery (OpenRouter)

---

## 📊 Orchestration

Pipeline coordination and workflow management.

### Write Pipeline
- Window-based processing (configurable window size)
- Multi-window parallel processing
- **Progress indicators** with Rich library
- Checkpoint/resume support
- Automatic retries and error handling
- Background task processing

### Window Management
- Sliding windows over message streams
- Time-based or message-count-based windows
- Window overlap for context continuity
- Incremental processing

### Task System
- Task queue management
- Priority-based scheduling
- Distributed task execution
- Progress tracking

---

## 💾 Database

DuckDB-based data management.

### DuckDB Manager
- In-process analytical database
- SQL query interface
- Sequence management for IDs
- **Read-only transaction fixes**
- Connection pooling
- Explicit transaction control

### Storage
- Messages table
- Tasks table (URL enrichment, media enrichment)
- Profiles table
- Posts/documents table
- ELO rating storage
- Run history and checkpoints

### Views & Queries
- Virtual views for common queries
- Optimized joins
- Aggregation support

---

## 📝 Output Adapters

Generate final output in various formats.

### MkDocs Adapter
- Generate static blog sites
- Material theme with customization
- **Automatic index page generation**:
  - Journal index
  - Profiles index  
  - Media index
  - Tags page with word cloud
- Profile pages with structured templates
- Media galleries
- **Banner generation** for posts
- Git integration for timestamps
- **Slug-based media naming** with reference updates

### Markdown Exporter
- Export posts as standalone markdown
- Preserve frontmatter
- Relative linking

### JSON/API Export
- Structured data export
- API-ready formats
- Custom schema support

---

## 🔒 Privacy

PII detection and anonymization.

### PII Prevention
- Automatic PII detection (emails, phones, addresses, SSNs, etc.)
- Redaction with placeholder tokens
- Configurable sensitivity levels
- Allowlist for known safe entities

### Phone Number Scrubbing
- Format-agnostic phone detection
- International number support
- Context-aware replacement

### Privacy Controls
- Per-source privacy settings
- Granular redaction controls
- Audit trail of redactions

---

## 🎨 Rendering & Templates

Content generation and formatting.

### Jinja2 Templates
- **10 default prompt templates**:
  - `enrichment.jinja` - URL/media batch modes
  - `writer.jinja` - blog post generation
  - `taxonomy.jinja` - topic clustering
  - `profile.jinja` - user profiles
  - And more...
- Template inheritance
- Custom filters
- Variable interpolation

### Rendering Pipeline
- Markdown processing
- Syntax highlighting
- Math equation rendering (KaTeX)
- Mermaid diagram support
- Custom CSS injection

### Media Handling
- Image optimization
- Video thumbnail generation  
- Media type detection
- Responsive embeds

---

## 🛠 Configuration

Flexible configuration system.

### YAML Configuration
- Site settings (title, description, theme)
- Model providers and API keys
- Rate limiting (per-second, concurrent, daily)
- Enrichment strategy selection
- Privacy controls
- Template paths

### Settings Schema
- Pydantic-based validation
- Type safety
- Default values
- Environment variable overrides
- Nested configuration sections

### Overrides
- CLI flag overrides
- Environment variables
- Config file cascading

---

## 🧪 Testing

Quality assurance and validation.

### Unit Tests
- `test_model_key_rotator.py` - rotation order verification
- Model cycling tests
- Key exhaustion tests

### Integration Tests
- End-to-end pipeline tests
- Multi-adapter tests
- Provider fallback tests

---

## 📦 Knowledge Management

Structured knowledge extraction.

### Profile Generation
- Auto-generate user profiles from messages
- Activity tracking
- Topic expertise detection
- Social graph construction

### Journal Entries
- Chronological event summaries
- Key events extraction
- Timeline reconstruction

### Semantic Taxonomy  
- Clustering analysis
- Topic modeling
- Tag generation
- Hierarchical categorization

---

## 🚀 CLI

Command-line interface for all operations.

### Commands
- `egregora write` - run blog generation pipeline
- `egregora init` - initialize new site
- `egregora read` - query and search content
- `egregora config` - manage configuration
- `egregora runs` - view run history

### Flags
- `--max-windows` - limit processing
- `--refresh` - refresh specific tiers
- `--output` - specify output directory
- `--config` - custom config file
- `--checkpoint` - enable/disable checkpointing

---

## 📈 Diagnostics

Monitoring and debugging tools.

### Logging
- Structured logging with levels
- Rich console output with colors
- Progress bars and spinners
- Agent context in logs

### Metrics
- Token usage tracking
- API call statistics
- Processing time measurements
- Rate limit monitoring

### Error Handling
- Detailed error messages
- Stack trace capture
- Retry logic with backoff
- Graceful degradation

---

## 🔄 Transformations

Data processing and normalization.

### Text Processing
- Markdown parsing
- HTML sanitization
- Unicode normalization
- Whitespace cleanup

### Data Normalization
- Timestamp standardization
- Phone number formatting
- URL canonicalization
- Name deduplication

---

## 🎛 Utilities

Helper functions and tools.

### Environment
- Secure API key loading
- Path resolution
- Config discovery

### Rate Limiting
- Global rate limiter
- Per-provider limits
- Adaptive backoff
- Queue management

### File Operations
- Safe file writes
- Atomic operations
- Temp file handling
- Archive extraction

---

## Summary Stats

- **21 packages** across the codebase
- **100+ Python modules**
- **3 enrichment strategies** (batch_all, batch_api, individual)
- **5 Gemini models** in rotation
- **N API keys** × 5 models = maximum resilience
- **4 input adapters** (WhatsApp, Slack, Markdown, Self-Reflection)
- **Multiple output formats** (MkDocs, Markdown, JSON)
- **Dual-queue RAG** with key cycling
- **10 Jinja2 prompt templates**
