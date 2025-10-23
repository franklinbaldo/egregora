# 🧠 Egregora v2

> **Agent-based pipeline for transforming WhatsApp conversations into structured blog posts**

Egregora v2 is a complete refactor using autonomous AI agents to process, curate, enrich, and write blog posts from WhatsApp group exports. Simple, functional, and extensible.

---

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/franklinbaldo/egregora
cd egregora

# Run
python run_v2.py process \
  --zip_file=whatsapp-export.zip \
  --output=./blog \
  --gemini_key=YOUR_GEMINI_KEY
```

## ⚡ What's New in v2

### Complete Architecture Refactor

- **Agent-based pipeline**: Each stage is an autonomous AI agent
- **Simple & functional**: No event sourcing, no complexity
- **Pluggable tools**: Easy to extend with RAG, web search, etc
- **Clean codebase**: ~1000 lines, well-organized
- **No backward compatibility**: Fresh start

### Pipeline Flow

```
WhatsApp ZIP → Parse → Anonymize → Curator → Enricher → Writer → Post
                          ↑            ↓
                    PII removed    Profiler → Profiles
```

### 🔒 Privacy-First Design

- **Automatic anonymization**: All names replaced with UUID5 pseudonyms before LLM
- **Deterministic**: Same author always gets same pseudonym (e.g., "João" → `a1b2c3d4`)
- **WhatsApp mentions**: Unicode markers detected and anonymized
- **Privacy validation**: Scans output for phone numbers and PII leaks
- **Early application**: Real names NEVER reach the LLM or agents

See [ANONYMIZATION.md](ANONYMIZATION.md) for details.

## 🧩 Architecture

### Core Components

#### **Agents** (`src/egregora/agents/`)
- **CuratorAgent**: Filters noise and clusters messages into topics using LLM
- **EnricherAgent**: Plans and executes context enrichment with tools
- **WriterAgent**: Generates blog posts from enriched topics
- **ProfilerAgent**: Analyzes participant activity patterns

#### **Tools** (`src/egregora/tools/`)
- **ToolRegistry**: Plugin system for extensibility
- **RAGTool**: Retrieval-augmented generation
- **PrivacyTool**: Content validation

#### **Pipeline** (`src/egregora/pipeline/`)
- **Orchestrator**: Coordinates agent execution
- **Loader**: WhatsApp export parser

### Data Flow

```python
# Input: WhatsApp messages
messages: list[Message]

# Step 1: Curator filters and clusters
topics: list[Topic] = curator.execute(messages)

# Step 2: Enricher adds context
enriched_topics = enricher.execute(topics)

# Step 3: Writer generates post
post: Post = writer.execute(enriched_topics, date)

# Output: Structured blog post
```

## 📖 Usage

### Basic

```bash
python run_v2.py process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY
```

### With RAG

```bash
python run_v2.py process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY \
  --enable_rag
```

### With Profiler

```bash
python run_v2.py process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY \
  --enable_profiler
```

### Debug Mode

```bash
python run_v2.py process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY \
  --debug
```

## ⚙️ Configuration

Create `config.yaml`:

```yaml
llm:
  model: models/gemini-2.5-flash
  temperature: 0.7

curator:
  enabled: true
  min_message_length: 15
  max_topics_per_day: 10

enricher:
  enabled: true
  enable_rag: false

writer:
  language: pt-BR
  max_post_length: 5000

profiler:
  enabled: false
  min_messages: 10
```

## 🛠️ Development

### Structure

```
src/egregora/
├── core/           # Data models & config
│   ├── models.py   # Message, Topic, Post, Profile
│   └── config.py   # YAML configuration
├── agents/         # AI agents
│   ├── base.py     # Base agent class
│   ├── curator.py  # Filter & cluster
│   ├── enricher.py # Add context
│   ├── writer.py   # Generate posts
│   └── profiler.py # Analyze participants
├── tools/          # Pluggable tools
│   ├── registry.py # Plugin system
│   ├── rag_tool.py # RAG integration
│   └── privacy_tool.py
└── pipeline/       # Orchestration
    ├── orchestrator.py
    └── loader.py
```

### Key Design Decisions

- ✅ **No event sourcing** - Simple functional pipeline
- ✅ **No backward compatibility** - Clean slate
- ✅ **No defensive code** - Fail fast, trust inputs
- ✅ **Agent-based** - Autonomous LLM agents
- ✅ **Pluggable** - Easy to extend

## 📚 Documentation

- [Architecture Details](ARCHITECTURE_V2.md)
- [Quick Start Guide](QUICKSTART_V2.md)
- [Example Config](config.example.yaml)

## 🤝 Contributing

This is a clean refactor. The old v1 codebase has been removed. All new development should follow the v2 agent-based architecture.

## 📄 License

MIT

---

**Egregora v2** - From chaos to clarity, one conversation at a time.
